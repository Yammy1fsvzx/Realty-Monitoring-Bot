from sqlalchemy import create_engine, Column, Integer, String, Float, UniqueConstraint, Index
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path
import datetime

# --- Настройка SQLAlchemy ---

# Путь к файлу базы данных
DB_FILE = Path(__file__).parent.parent / "data" / "realty.db"
# Строка подключения
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_FILE.resolve()}"

# Создаем движок. `check_same_thread` нужен только для SQLite.
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем базовый класс для наших моделей
Base = declarative_base()


# --- Модель данных ---

class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, nullable=False)
    area = Column(Float, nullable=False)
    price = Column(Float)
    url = Column(String, nullable=False, unique=True)
    description = Column(String)
    first_seen_date = Column(String, default=lambda: datetime.datetime.now().isoformat())

    # Уникальность по адресу и площади + индекс для быстрого поиска
    __table_args__ = (
        UniqueConstraint('address', 'area', name='_address_area_uc'),
        Index('ix_address_area', 'address', 'area'),
    )

    def __repr__(self):
        return f"<Listing(address='{self.address}', area={self.area})>"


# --- Функции для работы с БД ---

def init_db():
    """Инициализирует базу данных и создает таблицы."""
    DB_FILE.parent.mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)

def get_db():
    """Генератор сессии БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def is_listing_new(db, address: str, area: float) -> bool:
    """Проверяет, является ли объявление новым (по адресу и площади)."""
    return db.query(Listing).filter_by(address=address, area=area).first() is None

def add_listing(db, ad: dict):
    """Добавляет новое объявление в базу данных."""
    new_listing = Listing(
        address=ad['address'],
        area=ad['area'],
        price=ad['price'],
        url=ad['url'],
        description=ad.get('description', '')
    )
    db.add(new_listing)
    db.commit()
    db.refresh(new_listing)
    return new_listing


# --- Инициализация при первом запуске ---

if __name__ == '__main__':
    print("Инициализация базы данных с использованием SQLAlchemy...")
    init_db()
    print(f"База данных создана и готова к работе: {DB_FILE}")

    # Пример использования
    print("\nПример: Добавление и проверка записи...")
    db_session = next(get_db())
    
    # Проверяем, есть ли уже такое объявление
    is_new = is_listing_new(db_session, "Тестовый адрес, 123", 100.5)
    print(f"Объявление 'Тестовый адрес, 123' новое? -> {is_new}")
    
    if is_new:
        try:
            add_listing(db_session, {
                'address': 'Тестовый адрес, 123',
                'area': 100.5,
                'price': 10000000,
                'url': 'http://example.com/1',
                'description': 'Тестовое описание'
            })
            print("Тестовое объявление успешно добавлено.")
        except Exception as e:
            print(f"Ошибка при добавлении: {e}")
            db_session.rollback()

    # Проверяем еще раз
    is_new_after = is_listing_new(db_session, "Тестовый адрес, 123", 100.5)
    print(f"Объявление 'Тестовый адрес, 123' новое после добавления? -> {is_new_after}")

    db_session.close() 