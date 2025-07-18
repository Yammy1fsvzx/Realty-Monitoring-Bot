# Realty Monitoring Bot

Программа для автоматического мониторинга объявлений о продаже коммерческой недвижимости. Скрипт по расписанию обращается к API, отбирает новые объявления по заданным критериям, сохраняет их в локальную базу данных и отправляет отчеты на E-mail.

## Основные возможности

- **Гибкая фильтрация:** отбор объявлений по городу, категории, типу недвижимости, площади. Дополнительная внутренняя фильтрация по ключевым словам в тексте.
- **Отслеживание уникальности:** программа ведет собственную базу данных SQLite, чтобы гарантировать, что в отчет попадают только действительно новые объявления, которые вы еще не видели.
- **Автоматическая отчетность:** при нахождении новых объектов, скрипт формирует:
  - **Excel-файл (`.xlsx`)** с детальной информацией.
  - **Интерактивную карту (`.html`)** с метками объектов.
- **Работа по расписанию:** автоматический запуск в любое заданное время (один или несколько раз в день).
- **E-mail уведомления:** отправка отчетов на почту в виде вложений, а также отправка уведомлений, если новых объявлений не найдено.

## Установка и запуск

### 1. Предварительные требования

- Python 3.8+
- Менеджер пакетов `pip`
6Yd_rH0xQ5ia
### 2. Установка

```bash
# 1. Клонируйте репозиторий (или просто скачайте файлы проекта)
# git clone ...

# 2. Перейдите в папку проекта
cd path/to/your/project

# 3. Создайте и активируйте виртуальное окружение (рекомендуется)
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 4. Установите все необходимые зависимости
pip install -r requirements.txt
```

### 3. Настройка

Основной файл для настройки — `src/config.py`. Откройте его и задайте нужные параметры.

#### `[API]`
- `API_USER`: Ваш логин для доступа к `ads-api.ru`.
- `API_TOKEN`: Ваш токен для доступа к `ads-api.ru`.

#### `[Параметры поиска]`
- `CITY_NAME`: Город для поиска (например, `"Санкт-Петербург"`).
- `CATEGORY_ID`: ID категории. Установите `None` для поиска по всем категориям.
- `NEDVIGIMOST_TYPE`: ID типа недвижимости. Установите `None` для поиска по всем типам.
- `SQUARE_MIN`, `SQUARE_MAX`: Диапазон площади в кв.м.
- `EXCLUDE_KEYWORDS`: Список слов. Если любое из них есть в объявлении, оно будет проигнорировано.
- `EXCLUDE_BUILDING_TYPES`: Список типов объектов. Если "Вид объекта" содержит одно из этих значений, объявление будет проигнорировано.

> **Как отключить фильтр?**
> - Для числовых параметров (`CATEGORY_ID`, `SQUARE_MIN` и т.д.): установите значение `None`.
> - Для списков (`EXCLUDE_KEYWORDS`, `EXCLUDE_BUILDING_TYPES`): оставьте пустой список `[]`.

#### `[Расписание]`
- `SCHEDULE_TIMES`: Список времен запуска в формате `"ЧЧ:ММ"`.
  - `["09:00"]` — запуск раз в день в 9 утра.
  - `["09:00", "21:00"]` — запуск дважды в день.
  - `[]` — если оставить список пустым, скрипт выполнит проверку один раз и завершит работу.

#### `[Email]`
- `SMTP_SERVER`: Адрес почтового сервера. В файле есть примеры для `mail.ru` и `yandex.ru`.
- `SMTP_PORT`: Порт почтового сервера (обычно `465` для SSL).
- `EMAIL_SENDER`: Ваш e-mail адрес, с которого будут отправляться письма.
- `EMAIL_PASSWORD`: **Пароль для внешних приложений**, который нужно сгенерировать в настройках вашего почтового ящика (`Mail.ru`, `Yandex` и др.). **Это не ваш обычный пароль от почты!**
- `RECIPIENT_EMAIL`: E-mail адрес, на который будут приходить отчеты.

> **Как настроить Яндекс.Почту?**
>
> 1.  **Разрешите доступ почтовым клиентам:**
>     - Зайдите в вашу почту, справа сверху нажмите на шестерёнку (⚙️) и выберите пункт "Почтовые программы".
>     - Поставьте галочку "С сервера imap.yandex.ru по протоколу IMAP" и сохраните изменения.
>
> 2.  **Создайте пароль для приложения:**
>     - Перейдите по ссылке: [id.yandex.ru/security/app-passwords](https://id.yandex.ru/security/app-passwords)
>     - Нажмите "Создать новый пароль", выберите тип "Почта" и придумайте имя.
>     - Сгенерированный пароль скопируйте и вставьте в поле `EMAIL_PASSWORD` в `config.py`.

### 4. Запуск программы

После установки и настройки, запустите главный скрипт из корневой папки проекта:

```bash
python src/main.py
```

Программа выведет в консоль информацию о настройке расписания и перейдет в режим ожидания. Для остановки нажмите `Ctrl+C`.

## Структура проекта

- `/data/realty.db`: Локальная база данных SQLite. Создается автоматически.
- `/reports/`: Папка для сохранения сгенерированных отчетов. Создается автоматически.
- `/src/`: Основной исходный код.
  - `main.py`: Главный файл для запуска.
  - `config.py`: Файл конфигурации.
  - `database.py`: Модуль для работы с базой данных.
  - `excel_generator.py`: Модуль для создания Excel-отчетов.
  - `map_generator.py`: Модуль для создания интерактивных карт.
  - `email_sender.py`: Модуль для отправки E-mail.
- `requirements.txt`: Список зависимостей.
- `README.md`: Этот файл. 