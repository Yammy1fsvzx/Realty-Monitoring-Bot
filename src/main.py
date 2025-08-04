import requests
import json
import time
import schedule
from config import (
    API_USER, API_TOKEN, API_URL, LIMIT,
    CATEGORIES, NEDVIGIMOST_TYPE, REGIONS_CONFIG,
    SCHEDULE_TIMES, RECIPIENT_EMAIL, FETCH_FOR_YESTERDAY,
    RUN_ONCE
)
import database as db
from excel_generator import create_excel_report
from map_generator import create_map_report
from email_sender import send_email_with_reports, send_no_new_listings_email
from datetime import datetime, timedelta

def fetch_and_filter_ads_by_category(city_name=None, category_config=None):
    """
    Получает и фильтрует объявления с ads-api.ru для конкретной категории
    city_name: название города (строка)
    category_config: конфигурация категории (словарь)
    """
    if not category_config:
        return [], []
    
    params = {
        "user": API_USER,
        "token": API_TOKEN,
        "limit": LIMIT,
        "category_id": category_config["id"]
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
    
    if NEDVIGIMOST_TYPE is not None:
        params["nedvigimost_type"] = NEDVIGIMOST_TYPE
    
    # Параметры площади для категории
    if category_config.get("square_min") is not None:
        # Для земли НЕ используем API фильтры по площади, только внутреннюю фильтрацию
        if category_config["id"] != 5:  # Не для земельных участков
            params["param[7446]"] = category_config["square_min"]  # Площадь от
    if category_config.get("square_max") is not None:
        # Для земли НЕ используем API фильтры по площади, только внутреннюю фильтрацию
        if category_config["id"] != 5:  # Не для земельных участков
            params["param[7486]"] = category_config["square_max"]  # Площадь до

    print(f"Отправка GET-запроса к API для категории '{category_config['name']}' с параметрами")
    
    # Добавляем задержку перед запросом для соблюдения лимита API
    time.sleep(7)
    
    try:
        response = requests.get(API_URL, params=params)
        
        # Обработка ошибки 429 (превышен лимит запросов)
        if response.status_code == 429:
            print(f"Получена ошибка 429 (превышен лимит). Жду 10 секунд и повторяю запрос...")
            time.sleep(10)
            response = requests.get(API_URL, params=params)
        
        response.raise_for_status()  # Проверка на HTTP ошибки
        
        response_json = response.json()

        if 'error' in response_json:
            print(f"API вернуло ошибку: {response_json.get('error')}")
            return [], []

        all_ads_data = response_json.get('data', [])
        
        if not all_ads_data:
            print(f"API не вернуло объявлений для категории '{category_config['name']}' по заданным критериям.")
            return [], []

        print(f"Получено {len(all_ads_data)} объявлений для категории '{category_config['name']}'. Начинаю внутреннюю фильтрацию...")
        
        filtered_ads = []
        for ad in all_ads_data:
            # 1. Фильтрация по типу здания (если список в конфиге не пустой)
            exclude_building_types = category_config.get("exclude_building_types", [])
            if exclude_building_types:
                building_type = ad.get('params', {}).get('Вид объекта')
                if building_type and any(ex_type in building_type for ex_type in exclude_building_types):
                    continue

            # 2. Фильтрация по ключевым словам (если список в конфиге не пустой)
            exclude_keywords = category_config.get("exclude_keywords", [])
            if exclude_keywords:
                title = ad.get('title', '').lower()
                description = ad.get('description', '').lower()
                full_text = title + " " + description
                if any(keyword in full_text for keyword in exclude_keywords):
                    continue

            # 3. Собираем отформатированные данные
            try:
                address = ad.get('address')
                url = ad.get('url')
                if not address or not url:
                    continue

                # Для земли используем поле "Площадь", для коммерческой - "Общая площадь"
                if category_config["id"] == 5:  # Земельные участки
                    area_str = ad.get('params', {}).get('Площадь')
                else:  # Коммерческая недвижимость
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
                    "city": city_name,
                    "category_id": category_config["id"],
                    "category_name": category_config["name"],
                    "category_color": category_config["color"]
                })
            except (ValueError, TypeError) as e:
                print(f"  > Предупреждение: не удалось обработать поле в объявлении {ad.get('url', '')}. Ошибка: {e}")
                continue

        print(f"Найдено {len(filtered_ads)} подходящих объявлений для категории '{category_config['name']}' после внутренней фильтрации.")
        return filtered_ads, all_ads_data

    except requests.exceptions.RequestException as e:
        print(f"Критическая ошибка при запросе к API для категории '{category_config['name']}': {e}")
        if e.response is not None:
            print(f"Ответ от сервера: {e.response.text}")
        return [], []
    except json.JSONDecodeError:
        print(f"Критическая ошибка: не удалось декодировать JSON для категории '{category_config['name']}'. Ответ от API: {response.text}")
        return [], []


def fetch_and_filter_ads_for_region(region_name, region_config):
    """
    Получает и фильтрует объявления для региона (город + область)
    region_name: название региона (например, "Санкт-Петербург")
    region_config: конфигурация региона с городами
    """
    all_filtered_ads = []
    all_ads_data = []
    
    print(f"Начинаю поиск для региона: {region_name}")
    print(f"Города в регионе: {region_config['cities']}")
    print(f"Категории для поиска: {[cat['name'] for cat in CATEGORIES]}")
    
    for city in region_config["cities"]:
        print(f"\n=== Поиск объявлений для города: {city} ===")
        
        for category_config in CATEGORIES:
            print(f"\n  --- Обработка категории: {category_config['name']} (ID: {category_config['id']}) ---")
            filtered_ads, ads_data = fetch_and_filter_ads_by_category(
                city_name=city, 
                category_config=category_config
            )
            print(f"  Получено {len(filtered_ads)} объявлений для категории '{category_config['name']}' в городе '{city}'")
            all_filtered_ads.extend(filtered_ads)
            all_ads_data.extend(ads_data)
    
    print(f"\n=== ИТОГО для региона {region_name}: {len(all_filtered_ads)} объявлений ===")
    return all_filtered_ads, all_ads_data


def job():
    """
    Основная задача, выполняемая по расписанию.
    Теперь формирует и отправляет отчёты по регионам с множественными категориями.
    """
    # Очищаем папку reports один раз в начале цикла для экономии места
    from excel_generator import _clean_reports_directory
    print("Очистка папки reports для экономии места...")
    _clean_reports_directory()
    
    for region_name, region_config in REGIONS_CONFIG.items():
        print(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Запуск проверки для региона: {region_name} ---")
        
        all_filtered_ads, all_ads_data = fetch_and_filter_ads_for_region(region_name, region_config)

        if not all_filtered_ads:
            print(f"Не найдено объявлений для региона {region_name}.")
            send_no_new_listings_email(
                subject=f"Отчет по недвижимости за {datetime.now().strftime('%d.%m.%Y')} ({region_name}): новых объявлений нет",
                recipient_email=RECIPIENT_EMAIL
            )
            continue

        db_session = next(db.get_db())
        new_listings_added = []

        print(f"Проверка {len(all_filtered_ads)} объявлений на уникальность в БД...")
        for ad in all_filtered_ads:
            try:
                if db.is_listing_new(db_session, address=ad['address'], area=ad['area']):
                    db.add_listing(db_session, ad)
                    new_listings_added.append(ad)
            except Exception as e:
                db_session.rollback()
                print(f"Ошибка при добавлении объявления в БД {ad.get('url')}: {e}")

        db_session.close()

        if new_listings_added:
            print(f"Найдено и добавлено {len(new_listings_added)} новых объявлений для региона {region_name}.")
            excel_path = create_excel_report(new_listings_added, city=region_name)
            map_path = create_map_report(new_listings_added, all_ads_data, city=region_name)

            if excel_path and map_path:
                send_email_with_reports(
                    subject=f"Новые объекты недвижимости - {region_name} - {datetime.now().strftime('%d.%m.%Y')}",
                    recipient_email=RECIPIENT_EMAIL,
                    excel_path=excel_path,
                    map_path=map_path,
                    city=region_name
                )
            else:
                print(f"Отчёты для региона {region_name} созданы не полностью. Письмо не будет отправлено.")
        else:
            print(f"Новых объявлений для региона {region_name} не найдено.")
            send_no_new_listings_email(
                subject=f"Отчет по недвижимости за {datetime.now().strftime('%d.%m.%Y')} ({region_name}): новых объявлений нет",
                recipient_email=RECIPIENT_EMAIL
            )
        print(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Проверка для региона {region_name} завершена ---")


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