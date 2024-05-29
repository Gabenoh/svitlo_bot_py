from typing import List, Dict
from sqlalchemy import Column, Integer, String, create_engine, delete, update
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from constants import ENGINE
# Створення об'єкта Base
Base = declarative_base()


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


def add_user(user_id: str, turn: str) -> None:
    """Додавання нового користувача"""
    session = Session()
    try:
        new_user = Svitlo(user=user_id, turn=turn)
        session.add(new_user)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error adding user: {e}")
    finally:
        session.close()


def check_user(user_id: str, turn: str) -> None:
    """Перевірка користувача"""
    session = Session()
    try:
        user = session.query(Svitlo).filter(Svitlo.user == user_id).first()
        if not user:
            add_user(user_id, turn)
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error checking user: {e}")
    finally:
        session.close()


def update_user_turn(user_id: int, turn: str) -> None:
    """Редагування існуючого користувача"""
    session = Session()
    try:
        stmt = (
            update(Svitlo)
            .where(Svitlo.id == user_id)
            .values(turn=turn)
        )
        session.execute(stmt)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error updating user: {e}")
    finally:
        session.close()


def get_all_user() -> List[Dict[str, str]]:
    """Отримання всіх користувачів з бази даних"""
    session = Session()
    try:
        user_list = session.query(Svitlo).all()
        return [{'id': str(user.id), 'user': user.user, 'turn': user.turn} for user in user_list]
    except SQLAlchemyError as e:
        print(f"Error retrieving users: {e}")
        return []
    finally:
        session.close()


def delete_user(user_id: int) -> None:
    """Видалення користувача з таблиці за індексом"""
    session = Session()
    try:
        stmt = delete(Svitlo).where(Svitlo.id == user_id)
        session.execute(stmt)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error deleting user: {e}")
    finally:
        session.close()
