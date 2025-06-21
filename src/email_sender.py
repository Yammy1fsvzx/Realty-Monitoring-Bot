import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
from config import EMAIL_SENDER, EMAIL_PASSWORD, RECIPIENT_EMAIL, SMTP_SERVER, SMTP_PORT
from pathlib import Path

def send_email_with_reports(subject, recipient_email, excel_path, map_path):
    """
    Отправляет email с отчетами (Excel и карта) в виде вложений.
    """
    try:
        # --- Создание сообщения ---
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = recipient_email
        msg['Subject'] = subject

        html_body = f"""
        <html>
            <body>
                <p>Здравствуйте!</p>
                <p>Новые объявления о продаже коммерческой недвижимости в Санкт-Петербурге.</p>
                <p>Отчет с детальной информацией (Excel) и интерактивная карта (HTML) приложены к этому письму.</p>
                <p>Для просмотра карты, пожалуйста, скачайте приложенный файл <b>{Path(map_path).name}</b> и откройте его в вашем веб-браузере.</p>
                <br>
                <p>С уважением,<br>Ваш скрипт-помощник</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        # --- Прикрепление Excel файла ---
        with open(excel_path, 'rb') as f:
            part = MIMEApplication(f.read(), Name=Path(excel_path).name)
        part['Content-Disposition'] = f'attachment; filename="{Path(excel_path).name}"'
        msg.attach(part)

        # --- Прикрепление HTML карты ---
        with open(map_path, 'rb') as f:
            part = MIMEApplication(f.read(), Name=Path(map_path).name)
        part['Content-Disposition'] = f'attachment; filename="{Path(map_path).name}"'
        msg.attach(part)


        # --- Отправка письма ---
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        print(f"Письмо с отчетами успешно отправлено на {recipient_email}")
        return True

    except Exception as e:
        print(f"Ошибка при отправке письма: {e}")
        return False

def send_no_new_listings_email(subject, recipient_email):
    """
    Отправляет email-уведомление об отсутствии новых объявлений.
    """
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Текст письма
        body = "На данный момент нет новых объявлений, соответствующих вашим критериям."
        msg.attach(MIMEText(body, 'plain'))

        # Отправка письма
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        print(f"Письмо с уведомлением успешно отправлено на {recipient_email}")

    except Exception as e:
        print(f"Ошибка при отправке письма с уведомлением: {e}")

# Для тестирования модуля
if __name__ == '__main__':
    # Этот блок остается пустым или содержит только безопасные примеры,
    # которые не будут исполняться при импорте.
    pass 