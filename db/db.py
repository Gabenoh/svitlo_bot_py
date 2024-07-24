from typing import List, Dict
from sqlalchemy import Column, Integer, String, create_engine, delete, update, select
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import mysql.connector
import logging
import time
from functools import wraps
from constants import ENGINE

# Створення об'єкта Base
Base = declarative_base()

logging.basicConfig(filename='/home/galmed/svitlograf/logs/svitlo.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Визначення моделі Svitlo
class Svitlo(Base):
    __tablename__ = 'svitlo'
    id = Column(Integer, primary_key=True)
    user = Column(String(255))
    turn = Column(String(255))


# Підключення до бази даних MySQL
engine = create_engine(ENGINE)

# Створення таблиці за допомогою моделі Svitlo
Base.metadata.create_all(engine)

# Створення сесії
SessionLocal = sessionmaker(bind=engine)


def retry_on_failure(retries=3, delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                session = SessionLocal()
                try:
                    return func(session, *args, **kwargs)
                except (OperationalError, mysql.connector.errors.OperationalError) as e:
                    logger.error(f"Помилка при виконанні функції {func.__name__}: {e}")
                    session.close()
                    if attempt < retries - 1:
                        time.sleep(delay)
                    else:
                        raise
                except SQLAlchemyError as e:
                    session.rollback()
                    logger.error(f"SQLAlchemy помилка при виконанні функції {func.__name__}: {e}")
                    raise
                finally:
                    session.close()

        return wrapper

    return decorator


@retry_on_failure()
def add_user(session, user_id: str, turn: str) -> None:
    """Додавання нового користувача"""
    try:
        new_user = Svitlo(user=user_id, turn=turn)
        session.add(new_user)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Помилка при додаванні користувача: {e}")


@retry_on_failure()
def check_user(session, user_id: str, turn: str) -> None:
    """Перевірка користувача"""
    try:
        user = session.query(Svitlo).filter(Svitlo.user == user_id).first()
        if not user:
            add_user(session, user_id, turn)
        else:
            update_user_turn(session, user_id, turn)
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Помилка при перевірці користувача: {e}")


@retry_on_failure()
def update_user_turn(session, user_id: str, turn: str) -> None:
    """Редагування наявного користувача"""
    try:
        stmt = (
            update(Svitlo)
            .where(Svitlo.user == user_id)
            .values(turn=turn)
        )
        session.execute(stmt)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Помилка при оновленні користувача: {e}")


@retry_on_failure()
def get_all_user(session) -> List[Dict[str, str]]:
    """Отримання всіх користувачів з бази даних"""
    try:
        user_list = session.query(Svitlo).all()
        return [{'id': str(user.id), 'user': user.user, 'turn': user.turn} for user in user_list]
    except SQLAlchemyError as e:
        logger.error(f"Помилка при виводу всіх користувачів {e}")
        return []


@retry_on_failure()
def delete_user(session, user_id: int) -> None:
    """Видалення користувача з таблиці за індексом"""
    try:
        stmt = delete(Svitlo).where(Svitlo.id == user_id)
        session.execute(stmt)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Помилка при видаленні користувача: {e}")


# Приклад використання
if __name__ == '__main__':
    user_list = get_all_user()
    for user in user_list:
        print(user)
