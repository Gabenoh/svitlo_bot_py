import json
import os
import logging

logger = logging.getLogger(__name__)

CACHE_FILE_PATH = 'schedule_cache.json' # Змініть шлях, якщо потрібно

def load_schedule_cache():
    """Завантажує кеш графіків з JSON-файлу. Повертає порожній словник, якщо файл не знайдено."""
    if not os.path.exists(CACHE_FILE_PATH):
        return {}
    try:
        with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Помилка декодування JSON у файлі {CACHE_FILE_PATH}. Повертаю порожній кеш.")
        return {}
    except Exception as e:
        logger.error(f"Помилка при читанні файлу кешу {CACHE_FILE_PATH}: {e}")
        return {}

def save_schedule_cache(cache_data):
    """Зберігає кеш графіків у JSON-файл."""
    try:
        with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Помилка при записі файлу кешу {CACHE_FILE_PATH}: {e}")

def get_last_schedule(turn):
    """Отримує останній збережений графік для певної черги."""
    cache = load_schedule_cache()
    return cache.get(turn, None)

def update_last_schedule(turn, schedule_text):
    """Оновлює графік для певної черги і зберігає кеш."""
    cache = load_schedule_cache()
    cache[turn] = schedule_text
    save_schedule_cache(cache)