from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, create_engine, delete, update, select, distinct
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import mysql.connector
from constants import ENGINE
import logging
import time
from functools import wraps

# Створення об'єкта Base
Base = declarative_base()

logging.basicConfig(filename='/home/galmed/svitlograf/logs/svitlo.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def retry_on_failure(retries=3, delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                session = Session()
                try:
                    result = func(session, *args, **kwargs)
                    session.commit() # Фіксація транзакції тут
                    return result
                except (OperationalError, mysql.connector.errors.OperationalError) as e:
                    logger.error(f"Помилка БД ({e.__class__.__name__}) при виконанні функції {func.__name__}: {e}")
                    session.rollback()
                    if attempt < retries - 1:
                        time.sleep(delay)
                    else:
                        raise
                except SQLAlchemyError as e:
                    session.rollback()
                    logger.error(f"SQLAlchemy помилка при виконанні функції {func.__name__}: {e}")
                    raise
                finally:
                    session.close() # Закриття сесії
        return wrapper
    return decorator


# Визначення моделі Svitlo
class Svitlo(Base):
    __tablename__ = 'svitlo'
    id = Column(Integer, primary_key=True)
    user = Column(String(255))
    turn = Column(String(255))
    turn_abbreviated = Column(String(255))


# Підключення до бази даних MySQL
engine = create_engine(ENGINE)

# Створення таблиці за допомогою моделі Svitlo
Base.metadata.create_all(engine)

# Створення сесії
Session = sessionmaker(bind=engine)


@retry_on_failure()
def add_user(session, user_id: str, turn: str, turn_abbreviated: str) -> None:
    """Додавання нового користувача"""
    new_user = Svitlo(user=user_id, turn=turn, turn_abbreviated=turn_abbreviated)
    session.add(new_user)
    # Зверніть увагу: commit робиться в декораторі


@retry_on_failure()
def update_user_turn(session, user_id: int, turn: str, turn_abbreviated: str) -> None:
    """
    Редагування наявного користувача (turn) та його скороченої черги (turn_abbreviated).
    user_id - це Svitlo.id (внутрішній ID).
    """
    update_values = {'turn': turn}
    # Оновлюємо turn_abbreviated, якщо він коректний
    if turn_abbreviated and '.' in turn_abbreviated:
        update_values['turn_abbreviated'] = turn_abbreviated

    stmt = (
        update(Svitlo)
        .where(Svitlo.id == user_id)
        .values(**update_values)
    )
    session.execute(stmt)
    # Зверніть увагу: commit робиться в декораторі


@retry_on_failure()
def check_user(session, user_id: str, turn: str, turn_abbreviated: str) -> None:
    """
    Перевірка користувача (за Telegram ID). Якщо існує - оновлює, якщо ні - додає.
    """
    user = session.query(Svitlo).filter(Svitlo.user == user_id).first()
    if not user:
        add_user(user_id=user_id, turn=turn, turn_abbreviated=turn_abbreviated)
    else:
        # Передаємо внутрішній Svitlo.id
        update_user_turn(user_id=user.id, turn=turn, turn_abbreviated=turn_abbreviated)


@retry_on_failure()
def get_all_user_with_turn(session, turn_abbreviated: str) -> list[dict[str, str | Any]]:
    """Перевірка користувача"""
    user_list = session.query(Svitlo).filter(Svitlo.turn_abbreviated == turn_abbreviated).all()
    return [{'id': str(user.id), 'user': user.user, 'turn': user.turn, 'turn_abbreviated': user.turn_abbreviated}
            for user in user_list]


@retry_on_failure()
def add_users_turn_abbreviated(session, user_id: str, turn_abbreviated: str) -> None:
    """
    Додавання скороченої черги до наявного користувача.
    user_id - це Svitlo.id (внутрішній ID). Ця функція більше не потрібна, але залишимо для сумісності.
    """
    if turn_abbreviated and '.' in turn_abbreviated:
        stmt = (
            update(Svitlo)
            .where(Svitlo.id == user_id)
            .values(turn_abbreviated=turn_abbreviated)
        )
        session.execute(stmt)


@retry_on_failure()
def get_all_user(session) -> List[Dict[str, str]]:
    """Отримання всіх користувачів з бази даних"""
    user_list = session.query(Svitlo).all()
    return [{'id': str(user.id), 'user': user.user, 'turn': user.turn, 'turn_abbreviated': user.turn_abbreviated}
            for user in user_list]

@retry_on_failure()
def get_unique_abbreviated_turns(session) -> List[str]:
    """
    Повертає list унікальних, НЕ-NULL та НЕ-ПОРОЖНІХ скорочених черг.
    """
    # Фільтруємо порожні/NULL записи
    result = (session.query(distinct(Svitlo.turn_abbreviated))
              .filter(Svitlo.turn_abbreviated != None)
              .filter(Svitlo.turn_abbreviated != '')
              .all())
    # Отримуємо тільки значення з результату
    unique_turns = [row[0] for row in result]
    return unique_turns

@retry_on_failure()
def get_first_user_with_turn_abbreviated(session, turn_abbreviated_value: str) -> str:
    """
    Отримати перший turn для якого turn_abbreviated дорівнює певному значенню.
    """
    # Використовуємо SQLAlchemy для пошуку першого значення turn, яке відповідає умові
    result = session.query(Svitlo.turn).filter(Svitlo.turn_abbreviated == turn_abbreviated_value).first()
    if result:
        return result[0]
    else:
        return None


@retry_on_failure()
def delete_user(session, user_number_id: int) -> None:
    """Видалення користувача з таблиці за індексом"""
    stmt = delete(Svitlo).where(Svitlo.id == user_number_id)
    session.execute(stmt)

if __name__ == '__main__':
    try:
        print(get_unique_abbreviated_turns())

    except Exception as e:
        logger.error(f"Error in main execution: {e}")