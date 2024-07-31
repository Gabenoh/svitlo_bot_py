from typing import List, Dict
from sqlalchemy import Column, Integer, String, create_engine, delete, update
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
                    return func(session, *args, **kwargs)
                except (OperationalError, mysql.connector.errors.OperationalError) as e:
                    logger.error(f"Помилка при виконанні функції {func.__name__}: {e}")
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
                    session.close()
        return wrapper
    return decorator


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
Session = sessionmaker(bind=engine)


@retry_on_failure()
def add_user(session, user_id: str, turn: str) -> None:
    """Додавання нового користувача"""
    new_user = Svitlo(user=user_id, turn=turn)
    session.add(new_user)


@retry_on_failure()
def check_user(session, user_id: str, turn: str) -> None:
    """Перевірка користувача"""
    user = session.query(Svitlo).filter(Svitlo.user == user_id).first()
    if not user:
        add_user(user_id=user_id, turn=turn)
    else:
        update_user_turn(user_id=user.id, turn=turn)


@retry_on_failure()
def update_user_turn(session, user_id: int, turn: str) -> None:
    """Редагування наявного користувача"""
    stmt = (
        update(Svitlo)
        .where(Svitlo.id == user_id)
        .values(turn=turn)
    )
    session.execute(stmt)


@retry_on_failure()
def get_all_user(session) -> List[Dict[str, str]]:
    """Отримання всіх користувачів з бази даних"""
    user_list = session.query(Svitlo).all()
    return [{'id': str(user.id), 'user': user.user, 'turn': user.turn} for user in user_list]


@retry_on_failure()
def delete_user(session, user_number_id: int) -> None:
    """Видалення користувача з таблиці за індексом"""
    stmt = delete(Svitlo).where(Svitlo.id == user_number_id)
    session.execute(stmt)
    session.commit()


if __name__ == '__main__':
    # delete_user(15)
    user_list = get_all_user()
    check_user(user_id='358330105', turn='21010148')
    for user in user_list:
        print(user)
