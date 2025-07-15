import pandas as pd
from pathlib import Path
import datetime
import requests
import io
from urllib.parse import urlparse
from openpyxl import load_workbook
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
import mimetypes
mimetypes.add_type('image/webp', '.webp')
from PIL import Image as PILImage

# Путь для сохранения отчетов
REPORTS_DIR = Path(__file__).parent.parent / "reports"

def _is_valid_url(url):
    """Проверяет, является ли строка валидным URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except (ValueError, AttributeError):
        return False

def _format_price(price: float) -> str:
    """Форматирует цену в удобный для чтения формат (тыс. или млн. руб)."""
    if not isinstance(price, (int, float)) or price == 0:
        return "0 руб."
    
    price = float(price)
    
    if price >= 1_000_000:
        price_in_millions = round(price / 1_000_000)
        return f"{price_in_millions} млн. руб."
    elif price >= 1_000:
        price_in_thousands = round(price / 1_000)
        return f"{price_in_thousands} тыс. руб."
    else:
        return f"{int(price)} руб."

def create_excel_report(listings: list[dict], city: str = "") -> Path | None:
    """
    Создает Excel-отчет, скачивает изображения и вставляет их в ячейки,
    используя openpyxl для финальной обработки.
    city: название города (для имени файла)
    """
    if not listings:
        print("Нет данных для создания Excel-отчета.")
        return None

    REPORTS_DIR.mkdir(exist_ok=True)
    
    df = pd.DataFrame(listings)
    
    # Применяем форматирование к колонкам с ценами
    if 'price_per_sqm' in df.columns:
        df['price_per_sqm'] = df['price_per_sqm'].apply(_format_price)
    if 'price' in df.columns:
        df['price'] = df['price'].apply(_format_price)

    report_df = df.rename(columns={
        'address': 'Адрес', 'area': 'Площадь, кв.м.', 
        'price_per_sqm': 'Цена за кв.м.', 'price': 'Итоговая цена',
        'description': 'Описание', 'url': 'Ссылка на объявление', 'image_url': 'Фото'
    })
    
    # Оставляем только нужные колонки
    report_df = report_df[['Адрес', 'Площадь, кв.м.', 'Цена за кв.м.', 'Итоговая цена', 'Описание', 'Ссылка на объявление', 'Фото']]
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    city_part = f"_{city.lower().replace(' ', '_')}" if city else ""
    file_path = REPORTS_DIR / f"realty_report{city_part}_{timestamp}.xlsx"
    
    # 1. Сохраняем текстовые данные
    report_df.to_excel(file_path, index=False, engine='openpyxl')

    # 2. Открываем файл с помощью openpyxl для вставки изображений
    wb = load_workbook(file_path)
    ws = wb.active

    # --- Поиск колонок и настройка стилей ---
    header = [cell.value for cell in ws[1]]
    try:
        url_col_letter = get_column_letter(header.index('Ссылка на объявление') + 1)
        photo_col_letter = get_column_letter(header.index('Фото') + 1)
    except ValueError:
        print("Критическая ошибка: не найдены колонки 'Ссылка на объявление' или 'Фото'.")
        return file_path

    hyperlink_font = Font(color="0000FF", underline="single")
    center_align = Alignment(horizontal='center', vertical='center')

    # --- Настройка ширины и высоты ---
    ws.column_dimensions[photo_col_letter].width = 30  # Увеличим ширину колонки для фото
    for i, col_name in enumerate(header):
        if col_name != 'Фото':
            # Простой автофит
            max_len = report_df[col_name].astype(str).map(len).max() or len(col_name)
            ws.column_dimensions[get_column_letter(i + 1)].width = max(len(col_name), max_len) + 2

    # --- Итерация по строкам для вставки картинок и ссылок ---
    for row_num in range(2, ws.max_row + 1):
        ws.row_dimensions[row_num].height = 120 # Увеличим высоту строк

        # --- Гиперссылка на объявление ---
        url_cell = ws[f'{url_col_letter}{row_num}']
        if url_cell.value and _is_valid_url(url_cell.value):
            url_cell.hyperlink = url_cell.value
            url_cell.value = "Перейти"
            url_cell.font = hyperlink_font
        
        # --- Вставка изображения ---
        img_cell = ws[f'{photo_col_letter}{row_num}']
        photo_url = img_cell.value

        img_cell.value = "" # Очищаем ячейку от URL
        img_cell.alignment = center_align

        if photo_url and _is_valid_url(photo_url):
            try:
                response = requests.get(photo_url, timeout=15)
                response.raise_for_status()
                img_data = io.BytesIO(response.content)

                # Определяем формат изображения
                img_data.seek(0)
                try:
                    pil_img = PILImage.open(img_data)
                    if pil_img.format and pil_img.format.lower() == "webp":
                        # Конвертируем webp в png
                        png_img_data = io.BytesIO()
                        pil_img.save(png_img_data, format="PNG")
                        png_img_data.seek(0)
                        img = Image(png_img_data)
                    else:
                        img_data.seek(0)
                        img = Image(img_data)
                except Exception as e:
                    print(f"Не удалось обработать изображение (PIL): {e}")
                    img_cell.value = "Ошибка загрузки"
                    continue

                # Масштабируем изображение, чтобы оно вписалось в ячейку с отступами
                cell_height = 150 # ~120*1.25
                cell_width = 200  # ~30*6.5

                scale_h = cell_height / img.height
                scale_w = cell_width / img.width
                scale = min(scale_h, scale_w)

                img.height = img.height * scale
                img.width = img.width * scale

                # Центрируем изображение в ячейке
                img.anchor = f'{photo_col_letter}{row_num}'

                ws.add_image(img)

            except Exception as e:
                print(f"Не удалось вставить изображение из {photo_url}: {e}")
                img_cell.value = "Ошибка загрузки"
        else:
            img_cell.value = "Нет фото"

    # 3. Сохраняем итоговый файл
    wb.save(file_path)

    print(f"Excel-отчет с ВСТРОЕННЫМИ изображениями успешно создан: {file_path}")
    return file_path

if __name__ == '__main__':
    print("Создание тестового Excel-отчета с изображениями...")
    test_listings = [
        {
            'address': 'Тестовый проспект, 1', 'area': 75.5, 'price_per_sqm': 158940.4, 'price': 12000000.0, 
            'description': 'Отличное помещение в центре города.', 'url': 'https://example.com/1',
            'title': 'Помещение 75.5м', 'image_url': 'https://via.placeholder.com/200x150/0000FF/FFFFFF?text=Test1'
        },
        {
            'address': 'Дальняя улица, 42', 'area': 120.0, 'price_per_sqm': 125000.0, 'price': 15000000.0, 
            'description': 'Просторный офис с панорамными окнами.', 'url': 'https://example.com/2',
            'title': 'Офис 120м', 'image_url': 'https://via.placeholder.com/200x150/FF0000/FFFFFF?text=Test2'
        },
        {
            'address': 'Переулок без фото, 3', 'area': 90.0, 'price_per_sqm': 110000.0, 'price': 9900000.0, 
            'description': 'Офис без фото.', 'url': 'https://example.com/3',
            'title': 'Офис 90м', 'image_url': ''
        }
    ]
    report_path = create_excel_report(test_listings)
    if report_path:
        print(f"Тестовый отчет сохранен в: {report_path}") 