import requests
import json
import time
import schedule
from config import (
    API_USER, API_TOKEN, API_URL, LIMIT,
    CITY_NAME, CATEGORY_ID, NEDVIGIMOST_TYPE, SQUARE_MIN, SQUARE_MAX,
    EXCLUDE_KEYWORDS, EXCLUDE_BUILDING_TYPES,
    SCHEDULE_TIMES, RECIPIENT_EMAIL, FETCH_FOR_YESTERDAY,
    RUN_ONCE
)
import database as db
from excel_generator import create_excel_report
from map_generator import create_map_report
from email_sender import send_email_with_reports, send_no_new_listings_email
from datetime import datetime, timedelta

def fetch_and_filter_ads(city_name=None):
    """
    Получает и фильтрует объявления с ads-api.ru на основе настроек в config.py
    city_name: название города (строка)
    """
    params = {
        "user": API_USER,
        "token": API_TOKEN,
        "limit": LIMIT
    }

    if FETCH_FOR_YESTERDAY:
        yesterday = datetime.now() - timedelta(days=1)
        date1 = yesterday.strftime('%Y-%m-%d 00:00:00')
        date2 = yesterday.strftime('%Y-%m-%d 23:59:59')
        params['date1'] = date1
        params['date2'] = date2
        print(f"Включен фильтр по дате. Ищем объявления за {yesterday.strftime('%Y-%m-%d')}.")

    # Город теперь передаём явно
    if city_name:
        params["city"] = city_name
    elif CITY_NAME:
        params["city"] = CITY_NAME
    if CATEGORY_ID is not None:
        params["category_id"] = CATEGORY_ID
    if NEDVIGIMOST_TYPE is not None:
        params["nedvigimost_type"] = NEDVIGIMOST_TYPE
    if SQUARE_MIN is not None:
        params["param[7446]"] = SQUARE_MIN
    if SQUARE_MAX is not None:
        params["param[7486]"] = SQUARE_MAX

    print(f"Отправка GET-запроса к API с параметрами: {params}")
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()  # Проверка на HTTP ошибки
        
        response_json = response.json()

        if 'error' in response_json:
            print(f"API вернуло ошибку: {response_json.get('error')}")
            return [], []

        all_ads_data = response_json.get('data', [])
        
        if not all_ads_data:
            print("API не вернуло объявлений по заданным критериям.")
            return [], []

        print(f"Получено {len(all_ads_data)} объявлений. Начинаю внутреннюю фильтрацию...")
        
        filtered_ads = []
        for ad in all_ads_data:
            # 1. Фильтрация по типу здания (если список в конфиге не пустой)
            if EXCLUDE_BUILDING_TYPES:
                building_type = ad.get('params', {}).get('Вид объекта')
                if building_type and any(ex_type in building_type for ex_type in EXCLUDE_BUILDING_TYPES):
                    continue

            # 2. Фильтрация по ключевым словам (если список в конфиге не пустой)
            if EXCLUDE_KEYWORDS:
                title = ad.get('title', '').lower()
                description = ad.get('description', '').lower()
                full_text = title + " " + description
                if any(keyword in full_text for keyword in EXCLUDE_KEYWORDS):
                    continue

            # 3. Собираем отформатированные данные
            try:
                address = ad.get('address')
                url = ad.get('url')
                if not address or not url:
                    continue

                area_str = ad.get('params', {}).get('Общая площадь')
                if area_str is None: continue

                area = float(str(area_str).replace(',', '.'))
                price = float(ad.get('price', 0))
                images = ad.get('images', [])
                image_url = images[0]['imgurl'] if images and isinstance(images, list) and images[0].get('imgurl') else ''

                filtered_ads.append({
                    "address": address,
                    "area": area,
                    "price": price,
                    "price_per_sqm": round(price / area, 2) if area > 0 else 0,
                    "url": url,
                    "description": ad.get('description', '').strip(),
                    "title": ad.get('title', ''),
                    "image_url": image_url,
                    "city": city_name or CITY_NAME
                })
            except (ValueError, TypeError) as e:
                print(f"  > Предупреждение: не удалось обработать поле в объявлении {ad.get('url', '')}. Ошибка: {e}")
                continue

        print(f"Найдено {len(filtered_ads)} подходящих объявлений после внутренней фильтрации.")
        return filtered_ads, all_ads_data

    except requests.exceptions.RequestException as e:
        print(f"Критическая ошибка при запросе к API: {e}")
        if e.response is not None:
            print(f"Ответ от сервера: {e.response.text}")
        return [], []
    except json.JSONDecodeError:
        print(f"Критическая ошибка: не удалось декодировать JSON. Ответ от API: {response.text}")
        return [], []


def job():
    """
    Основная задача, выполняемая по расписанию.
    Теперь формирует и отправляет отчёты по нескольким городам.
    """
    cities = [
        {"name": "Санкт-Петербург", "api_name": "Санкт-Петербург"},
        {"name": "Москва", "api_name": "Москва"},
    ]

    for city in cities:
        print(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Запуск проверки для города: {city['name']} ---")
        filtered_ads, all_ads_data = fetch_and_filter_ads(city_name=city["api_name"])

        if not filtered_ads:
            print(f"Не найдено объявлений для {city['name']}.")
            send_no_new_listings_email(
                subject=f"Отчет по недвижимости за {datetime.now().strftime('%d.%m.%Y')} ({city['name']}): новых объявлений нет",
                recipient_email=RECIPIENT_EMAIL
            )
            continue

        db_session = next(db.get_db())
        new_listings_added = []

        print(f"Проверка {len(filtered_ads)} объявлений на уникальность в БД...")
        for ad in filtered_ads:
            try:
                if db.is_listing_new(db_session, address=ad['address'], area=ad['area']):
                    db.add_listing(db_session, ad)
                    new_listings_added.append(ad)
            except Exception as e:
                db_session.rollback()
                print(f"Ошибка при добавлении объявления в БД {ad.get('url')}: {e}")

        db_session.close()

        if new_listings_added:
            print(f"Найдено и добавлено {len(new_listings_added)} новых объявлений для {city['name']}.")
            excel_path = create_excel_report(new_listings_added, city=city['name'])
            map_path = create_map_report(new_listings_added, all_ads_data, city=city['name'])

            if excel_path and map_path:
                send_email_with_reports(
                    subject=f"Новые объекты недвижимости - {city['name']} - {datetime.now().strftime('%d.%m.%Y')}",
                    recipient_email=RECIPIENT_EMAIL,
                    excel_path=excel_path,
                    map_path=map_path,
                    city=city['name']
                )
            else:
                print(f"Отчёты для {city['name']} созданы не полностью. Письмо не будет отправлено.")
        else:
            print(f"Новых объявлений для {city['name']} не найдено.")
            send_no_new_listings_email(
                subject=f"Отчет по недвижимости за {datetime.now().strftime('%d.%m.%Y')} ({city['name']}): новых объявлений нет",
                recipient_email=RECIPIENT_EMAIL
            )
        print(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Проверка для {city['name']} завершена ---")


if __name__ == "__main__":
    print("--- Запуск скрипта мониторинга недвижимости ---")
    db.init_db()
    print("База данных готова.")

    if RUN_ONCE:
        print("Режим: однократный запуск. Формирую отчёт сразу и завершаю работу.")
        job()
    else:
        print("Режим: работа по расписанию.")
        if not SCHEDULE_TIMES:
            print("В конфигурационном файле не указано время запуска (SCHEDULE_TIMES). Скрипт завершает работу.")
        else:
            print("Настройка расписания...")
            for run_time in SCHEDULE_TIMES:
                schedule.every().day.at(run_time).do(job)
            print(f"Скрипт настроен на запуск в следующее время: {SCHEDULE_TIMES}")
            print("Первая проверка начнется в указанное время. Для немедленного запуска - запустите скрипт с параметром RUN_ONCE=True")
            while True:
                schedule.run_pending()
                time.sleep(1) 