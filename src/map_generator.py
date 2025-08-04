import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from pathlib import Path
import time
import datetime
import os
import shutil
from config import REGIONS_CONFIG

# --- Общие настройки ---
REPORTS_DIR = Path(__file__).parent.parent / "reports"
# Координаты центра СПб для карты по умолчанию
SPB_CENTER_COORDS = [59.9386, 30.3141]

# Настройка геокодера
geolocator = Nominatim(user_agent="realty_parser_project/1.0")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def _format_price(price: float) -> str:
    """Форматирует цену в удобный для чтения формат (тыс. или млн. руб)."""
    if not isinstance(price, (int, float)) or price == 0:
        return "0 руб."
    
    price = float(price)
    
    if price >= 1_000_000:
        # Округляем до ближайшего миллиона
        price_in_millions = round(price / 1_000_000)
        return f"{price_in_millions} млн. руб."
    elif price >= 1_000:
        # Округляем до ближайшей тысячи
        price_in_thousands = round(price / 1_000)
        return f"{price_in_thousands} тыс. руб."
    else:
        return f"{int(price)} руб."

def _get_coordinates_list(address: str, ad_coords: dict | None) -> list[float] | None:
    """Получает координаты в формате [lat, lon] для folium."""
    if ad_coords and 'lat' in ad_coords and 'lng' in ad_coords:
        try:
            return [float(ad_coords['lat']), float(ad_coords['lng'])]
        except (ValueError, TypeError): pass
    
    print(f"  > Геокодирую адрес (для интерактивной карты): {address}")
    try:
        location = geocode(address)
        return [location.latitude, location.longitude] if location else None
    except Exception as e:
        print(f"Ошибка геокодирования: {e}")
        return None

def create_interactive_map(listings: list[dict], city: str = "") -> Path:
    """
    Создает интерактивную HTML карту с помощью Folium.
    Возвращает путь к созданной карте.
    city: название города (для имени файла)
    """
    # Определяем центр карты на основе региона или первого объявления
    map_center = SPB_CENTER_COORDS
    if city and city in REGIONS_CONFIG:
        map_center = REGIONS_CONFIG[city]["center_coords"]
    elif listings:
        map_center = listings[0]['coords']
    
    m = folium.Map(location=map_center, zoom_start=11)

    # Создаем легенду для категорий
    legend_html = '''
    <div style="position: fixed;
                top: 10px;
                left: 50px;
                width: 200px;
                background-color: white;
                border: 1px solid grey;
                z-index: 9999;
                font-size: 14px;
                padding: 10px;
                height: 150px;
                border-radius: 10px">
    <p><b>Категории недвижимости:</b></p>
    <p><i class="fa fa-circle" style="color:red"></i> Коммерческая недвижимость</p>
    <p><i class="fa fa-circle" style="color:green"></i> Земельные участки</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    for loc in listings:
        # Определяем цвет маркера на основе категории
        marker_color = loc.get('category_color', 'blue')
        
        folium.Marker(
            location=loc['coords'],
            popup=loc['popup'],
            tooltip=loc['address'],
            icon=folium.Icon(color=marker_color, icon='info-sign')
        ).add_to(m)

    REPORTS_DIR.mkdir(exist_ok=True)
    # Имя файла теперь только дата и время
    map_filename = f"{time.strftime('%Y-%m-%d_%H%M%S')}.html"
    map_path = REPORTS_DIR / map_filename
    m.save(map_path)
    print(f"Интерактивная карта создана: {map_path}")
    return map_path


def create_map_report(listings: list[dict], all_ads_data: list[dict], city: str = "") -> str | None:
    """
    Главная функция: создает интерактивную карту.
    Возвращает путь к интерактивной карте.
    city: название города (для имени файла)
    """
    if not listings:
        print("Нет данных для создания карты.")
        return None

    REPORTS_DIR.mkdir(exist_ok=True)
    
    listings_with_coords_and_popup = []

    print("Подготовка координат для карты...")
    for ad in listings:
        full_ad_data = next((item for item in all_ads_data if item.get('url') == ad['url']), None)
        coords_list = _get_coordinates_list(ad['address'], full_ad_data.get('coords') if full_ad_data else None)
        
        if coords_list:
            formatted_price_per_sqm = _format_price(ad['price_per_sqm'])
            formatted_price = _format_price(ad['price'])
            description = ad.get('description', '')
            image_html = ''
            if ad.get('image_url'):
                image_html = f'''
                <div style="width: 48%; float: right;">
                    <a href="{ad["image_url"]}" target="_blank" title="Нажмите для увеличения">
                        <img src="{ad["image_url"]}" alt="Фото" style="width: 100%; height: auto; max-height: 200px; object-fit: cover; border-radius: 5px;">
                    </a>
                </div>
                '''
            
            # Добавляем информацию о категории в popup
            category_info = f'<p style="margin: 5px 0; color: {ad.get("category_color", "blue")};"><b>Категория:</b> {ad.get("category_name", "Неизвестно")}</p>'
            
            # Определяем правильную единицу измерения площади
            category_name = ad.get('category_name', '').lower()
            area_unit = "сотки" if 'земельные' in category_name or 'земельный' in category_name else "м²"
            
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; width: 450px;">
                <div style="width: {'50%' if image_html else '100%'}; float: left; padding-right: {'10px' if image_html else '0'}; box-sizing: border-box;">
                    <p style="margin: 0; padding-bottom: 5px; border-bottom: 1px solid #eee;"><b>Адрес:</b> {ad['address']}</p>
                    {category_info}
                    <p style="margin: 5px 0 0 0;"><b>Площадь:</b> {ad['area']} {area_unit}</p>
                    <p style="margin: 5px 0;"><b>Цена за {area_unit}:</b> {formatted_price_per_sqm}</p>
                    <p style="margin: 5px 0; font-weight: bold;"><b>Итоговая цена:</b> {formatted_price}</p>
                    <div style="max-height: 80px; overflow-y: auto; margin-top: 8px; border-top: 1px solid #eee; padding-top: 8px;">
                        {description}
                    </div>
                    <a href="{ad['url']}" target="_blank"
                       style="display: block; width: 95%; background-color: #007bff; color: white; padding: 10px 0; text-align: center; text-decoration: none; border-radius: 5px; margin: 12px auto 0 auto; font-weight: bold;">
                       Перейти к объявлению
                    </a>
                </div>
                {image_html}
                <div style="clear: both;"></div>
            </div>
            """
            listings_with_coords_and_popup.append({
                "coords": coords_list,
                "popup": folium.Popup(popup_html, max_width=500),
                "address": ad['address'],
                "category_color": ad.get('category_color', 'blue')
            })

    if not listings_with_coords_and_popup:
        print("Не удалось определить координаты ни для одного объекта. Карта не будет создана.")
        return None

    interactive_map_path = create_interactive_map(listings_with_coords_and_popup, city=city)
    
    return str(interactive_map_path)

if __name__ == '__main__':
    print("Создание тестовой карты...")
    test_listings = [
        {
            'address': 'Санкт-Петербург, Невский проспект, 28', 
            'area': 150.0, 
            'price_per_sqm': 200000.0, 
            'price': 30000000.0, 
            'url': 'http://example.com/nevsky',
            'category_name': 'Коммерческая недвижимость',
            'category_color': 'red'
        },
        {
            'address': 'Санкт-Петербург, ул. Рубинштейна, 1', 
            'area': 80.0, 
            'price_per_sqm': 250000.0, 
            'price': 20000000.0, 
            'url': 'http://example.com/rubinshteina',
            'category_name': 'Коммерческая недвижимость',
            'category_color': 'red'
        },
        { # Пример земли
            'address': 'Ленинградская область, Всеволожский район, д. Кудрово', 
            'area': 1500.0, 
            'price_per_sqm': 50000.0, 
            'price': 75000000.0, 
            'url': 'http://example.com/kudrovo',
            'category_name': 'Земельные участки',
            'category_color': 'green'
        }
    ]
    # В реальном сценарии здесь были бы полные данные от API
    test_all_ads = [
        {'url': 'http://example.com/nevsky', 'address': 'Санкт-Петербург, Невский проспект, 28', 'coords': {'lat': '59.9355', 'lng': '30.3200'}, 'image_url': 'https://via.placeholder.com/150'},
        {'url': 'http://example.com/rubinshteina', 'address': 'Санкт-Петербург, ул. Рубинштейна, 1', 'coords': None, 'image_url': 'https://via.placeholder.com/150'}, # <-- Координат нет
        {'url': 'http://example.com/kudrovo', 'address': 'Ленинградская область, Всеволожский район, д. Кудрово', 'coords': None, 'image_url': ''}
    ]

    report_path = create_map_report(test_listings, test_all_ads)
    if report_path:
        print(f"Тестовая карта сохранена в: {report_path}") 