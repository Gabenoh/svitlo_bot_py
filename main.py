import logging
import datetime
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor, exceptions
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.common.exceptions import TimeoutException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from constants import TOKEN, admin
from utils import *
from db import *

# Налаштування логування
logging.basicConfig(filename='/home/galmed/svitlograf/logs/svitlo.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ініціалізація бота та диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())


# Функція для створення WebDriver
def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    print('створено новий драйвер')
    return webdriver.Chrome(options=options)


# Ініціалізація WebDriver
driver = create_driver()
requests_count = 0
max_requests_before_restart = 100
WAIT_TIMEOUT = 25  # Загальний таймаут для WebDriverWait

# --- ГЛОБАЛЬНІ ЛОКАТОРИ (ОСТАТОЧНІ РОБОЧІ) ---
INPUT_FIELD_LOCATOR = (By.NAME, "personalAccount")
SUBMIT_BUTTON_LOCATOR = (By.XPATH, "//button[contains(., 'Дізнатись чергу')]")
DIALOG_LOCATOR = (By.XPATH, "//div[contains(@class, 'MuiDialog-root') and contains(., 'Графік погодинних')]")
TODAY_CONTAINER_XPATH = "//div[contains(@class, 'MuiDialogContent-root')]//div[contains(@class, '_graph_qwrgv')][1]"
TOMORROW_CONTAINER_XPATH = "//div[contains(@class, 'MuiDialogContent-root')]//div[contains(@class, '_graph_qwrgv')][2]"

# НАЙБІЛЬШ УНІВЕРСАЛЬНИЙ ЛОКАТОР ЗАГОЛОВКА
DIALOG_HEADER_LOCATOR = (By.XPATH, f"{DIALOG_LOCATOR[1]}//div[contains(., 'Станом на')]")


# === ОНОВЛЕНА УНІВЕРСАЛЬНА ФУНКЦІЯ СЕЛЕНІУМУ ===
def get_schedule_from_site(user_number: str):
    """
    Виконує всі кроки Selenium: ВІДКРИТТЯ САЙТУ З НУЛЯ, введення номера, натискання
    та очікування модального вікна.
    """
    global driver, requests_count

    wait_local = WebDriverWait(driver, WAIT_TIMEOUT)

    # 1. ПЕРЕВІРКА І ПЕРЕЗАПУСК ДРАЙВЕРА (за необхідності)
    if requests_count >= max_requests_before_restart:
        driver.quit()
        driver = create_driver()
        requests_count = 0

    # 2. ВІДКРИТТЯ САЙТУ З НУЛЯ (КОЖНОГО РАЗУ)
    driver.get("https://svitlo.oe.if.ua")
    requests_count += 1

    # 3. ВВЕДЕННЯ НОМЕРА
    number_input = wait_local.until(EC.element_to_be_clickable(INPUT_FIELD_LOCATOR))
    slow_type(number_input, user_number, delay=0.1)

    # 4. НАТИСКАННЯ КНОПКИ
    submit_button = wait_local.until(EC.element_to_be_clickable(SUBMIT_BUTTON_LOCATOR))
    submit_button.click()

    # 5. ОЧІКУВАННЯ МОДАЛЬНОГО ВІКНА
    wait_local.until(EC.visibility_of_element_located(DIALOG_LOCATOR))
    time.sleep(2)  # Даємо час на рендеринг контенту

    # Драйвер знаходиться у відкритому модальному вікні


def parse_schedule(driver, container_xpath, day_name, known_turn=None):
    """
    Витягує інтервали часу та парсить чергу.
    Якщо known_turn передано, заголовок не шукається.
    """
    # Довгий таймаут для пошуку черги, якщо вона невідома
    local_wait_header = WebDriverWait(driver, 20)
    # Довгий таймаут для очікування вмісту контейнера Завтра
    local_wait_content = WebDriverWait(driver, 15)

    CONTAINER_LOCATOR = (By.XPATH, container_xpath)

    # REGEX для часу (підтверджено, що працює з '——' або '--')
    RE_TIME_INTERVAL_FINAL = re.compile(r"(\d{2}:\d{2})\s*[—\-]{2,}\s*(\d{2}:\d{2})")

    min_turn = known_turn if known_turn is not None else "N/A"

    try:
        # --- 1. ПАРСИНГ ЧЕРГИ З ЗАГОЛОВКА (ТІЛЬКИ ЯКЩО ЧЕРГА НЕ ВІДОМА) ---
        if known_turn is None:
            header_element = local_wait_header.until(EC.presence_of_element_located(DIALOG_HEADER_LOCATOR))
            header_text = header_element.text

            # ВИПРАВЛЕННЯ: Нормалізуємо лапки
            normalized_text = header_text.replace('\u2019', "'").replace('\x27', "'")

            # Використовуємо split за символом одинарної лапки "'"
            if normalized_text.count("'") >= 4:
                min_turn = normalized_text.split("'")[3]
                min_turn = min_turn.strip().rstrip('.')

        # --- 2. ПАРСИНГ ГРАФІКУ З КОНТЕЙНЕРА ---
        container_element = local_wait_content.until(EC.presence_of_element_located(CONTAINER_LOCATOR))
        full_text = container_element.text.replace('\n', ' ').strip()

        # Перевірка на відсутність відключень (Не застосовується)
        if "Не застосовується" in full_text:
            return f"🟢 Відключення {day_name} не застосовується.", min_turn

        # Перевірка на "Інформація відсутня"
        if "Інформація відсутня" in full_text:
            return f"❌ Графік на {day_name} відсутній. Ймовірно, світло буде.", min_turn

        # 3. Парсинг інтервалів часу
        matches_time = RE_TIME_INTERVAL_FINAL.findall(full_text)

        if matches_time:
            schedule_times = [f"{start_time} — {end_time}" for start_time, end_time in matches_time]
            formatted_times = "\n".join(schedule_times)
            return f"Черга {min_turn} ({day_name.capitalize()}):\n{formatted_times}", min_turn
        else:
            # Якщо немає ні часу, ні напису про відсутність інформації
            return f"💡 Графік на {day_name} порожній або невідомий. Перевірте вручну.", min_turn

    except TimeoutException:
        logger.error(f"Timeout при пошуку заголовка/контейнера {day_name}. Локатор контейнера: {CONTAINER_LOCATOR}")
        return f"❌ Не вдалося витягнути графік на {day_name} з модального вікна (Timeout).", "N/A"
    except Exception as e:
        logger.error(f"Загальна помилка парсингу {day_name}: {e}")
        return f"❌ Виникла помилка під час парсингу даних ({day_name}).", "N/A"

# --- ХЕНДЛЕРИ БОТА ---

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привіт! Введіть ваш номер особового рахунку для отримання графіку відключень світла.")


@dp.message_handler(commands=['all_user_list', 'всі'])
async def add_command(message: types.Message):
    if await admin(message.from_user.id):
        user_list = get_all_user()
        for row in user_list:
            await message.reply(f"№{row['id']}, user {row['user']}, \n turn - {row['turn']}")


@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    if await admin(message.from_user.id):
        await message.answer("Привіт, адмін!", reply_markup=admin_keyboard)
    else:
        await message.answer("У вас немає доступу до цієї команди.")


@dp.message_handler(commands=['send_tomorrow_graf_all'])
async def send_all_tomorrow(message: types.Message):
    if await admin(message.from_user.id):
        await send_daily_message(day='tomorrow')
        await message.reply("Розсилка графіків на завтра запущена.")


@dp.message_handler(commands=['send_today_graf_all'])
async def send_all_today_(message: types.Message):
    if await admin(message.from_user.id):
        await send_daily_message(day='today')
        await message.reply("Розсилка графіків на сьогодні запущена.")


@dp.message_handler(commands=['send_message_all'])
async def send_all_message(message: types.Message):
    if await admin(message.from_user.id):
        try:
            message_text = message.get_args()
            if not message_text:
                await message.reply("Будь ласка, введіть текст повідомлення після команди /send_message_all")
                return

            user_list = get_all_user()

            for user in user_list:
                try:
                    await bot.send_message(chat_id=user['user'], text=message_text)
                    logger.info(f"Повідомлення {message_text} відправлено користувачу: {user['user']}")
                except Exception as e:
                    logger.error(f"Не вдалося відправити повідомлення користувачу {user['user']}: {e}")
            await message.reply("Повідомлення успішно відправлено всім користувачам.")
        except Exception as e:
            logger.error(f"Помилка при відправці повідомлень: {e}")
            await message.reply("Сталася помилка при відправці повідомлень.")

async def send_message_to_all():
    user_list = get_all_user()
    logger.info(f"Початок надсилання повідомлень про відсутність відключень")
    for user in user_list:
        try:
            await bot.send_message(chat_id=user['user'], text='Інформація щодо графіка відключень💡 відсутня на '
                                                              'сайті, швидше за все завтра буде світло весь день')
        except Exception as e:
            logger.error(f"Помилка при відправці повідомлень про відсутність графіків.: {e}")


@dp.message_handler()
async def get_schedule(message: types.Message):
    """Отримання номера особового рахунку, парсинг та відправка графіку з модального вікна."""
    user_number = message.text.strip()
    user_number_str = str(user_number)

    logger.info(f'Користувач {message.from_user.first_name, message.from_user.last_name}'
                f' надіслав повідомлення {user_number}')

    if not user_number.isdigit() or len(user_number) > 8:
        await message.reply("Будь ласка, введіть правильний номер особового рахунку (до 8 цифр).")
        return

    final_min_turn = "N/A"
    schedule_results = []

    try:
        # === КРОК 1-3: ВХІД НА САЙТ ТА ОЧІКУВАННЯ МОДАЛЬНОГО ВІКНА (Рефакторинг) ===
        get_schedule_from_site(user_number_str)

        # === КРОК 4: ПАРСИНГ ГРАФІКІВ ===

        # Сьогодні (Вперше шукаємо чергу)
        today_text, min_turn = parse_schedule(driver, TODAY_CONTAINER_XPATH, "Сьогодні")
        schedule_results.append((f'Ваш графік відключень💡 на сьогодні {todaydate()} 👇', today_text))
        final_min_turn = min_turn

        # Завтра (Черга вже відома, передаємо її)
        tomorrow_text, _ = parse_schedule(driver, TOMORROW_CONTAINER_XPATH, "Завтра", known_turn=final_min_turn)
        schedule_results.append((f'Ваш графік відключень💡 на завтра {tomorowdate()} 👇', tomorrow_text))

        # === КРОК 6: ВІДПРАВКА РЕЗУЛЬТАТІВ ===
        if final_min_turn != "N/A":
            check_user(message.from_user.id, user_number, final_min_turn)  # Зберігаємо чергу в базу

        for prefix, schedule_text in schedule_results:
            await message.reply(text=f'{prefix}\n\n{schedule_text}')

    except NoSuchElementException:
        await message.reply('Номер особового рахунку не коректний або не знайдено графік відключень. '
                            'Перевірте номер і спробуйте ще раз.')
        logger.error("Error in get_schedule: Номер особового рахунку не коректний або не знайдено графік відключень.")
    except TimeoutException:
        await message.reply('Таймаут: Не вдалося отримати графік. Можливо, сайт перевантажений. Спробуйте пізніше.')
        logger.error("Error in get_schedule: Timeout when loading schedule.")
    except WebDriverException as e:
        logger.error(f"WebDriver exception: {e}")
        await message.reply("Виникла проблема з обробкою вашого запиту. Спробуйте пізніше.")
    except Exception as e:
        await message.reply('Виникла помилка при отриманні графіку. Спробуйте пізніше.')
        logger.error(f"Error in get_schedule: {e}")


async def process_and_update_turn(user_data):
    """Отримує чергу для одного користувача і оновлює її в базі даних."""
    global driver
    user_number_str = user_data['turn']
    user_id = user_data['user']
    db_id = user_data['id']  # Внутрішній ID запису

    final_min_turn = "N/A"

    try:
        # === КРОК 1-3: ВХІД НА САЙТ ТА ОЧІКУВАННЯ МОДАЛЬНОГО ВІКНА (Рефакторинг) ===
        get_schedule_from_site(user_number_str)

        # === КРОК 4: ПАРСИНГ ЧЕРГИ (тільки для Сьогодні) ===
        # Ми передаємо known_turn=None, щоб форсувати пошук заголовка
        _, min_turn = parse_schedule(driver, TODAY_CONTAINER_XPATH, "Сьогодні", known_turn=None)
        final_min_turn = min_turn

        # === КРОК 6: ОНОВЛЕННЯ В БАЗІ ДАНИХ ===
        if final_min_turn != "N/A" and final_min_turn != user_data.get('turn_abbreviated'):
            add_users_turn_abbreviated(user_id=db_id, turn_abbreviated=final_min_turn)
            logger.info(f"Оновлено чергу для користувача {user_id}: {user_number_str} -> {final_min_turn}")
            return f"✅ {user_number_str}: {final_min_turn}"

        return f"ℹ️ {user_number_str}: Черга вже встановлена або не знайдена."

    except Exception as e:
        logger.error(f"Помилка оновлення черги для {user_number_str} ({user_id}): {e}")
        return f"❌ {user_number_str}: Помилка ({e.__class__.__name__})"


@dp.message_handler(commands=['update_all_turns'])
async def update_all_turns_command(message: types.Message):
    """Команда адміністратора для масового оновлення скорочених черг."""
    if await admin(message.from_user.id):
        await message.reply("🚀 Розпочато масове оновлення скорочених черг користувачів. Це може зайняти час...")

        user_list = get_all_user()  # Отримуємо всіх користувачів
        results = []

        for user in user_list:
            await asyncio.sleep(5)

            result = await process_and_update_turn(user)
            results.append(result)

            if len(results) % 10 == 0:
                await message.answer(f"Проміжний звіт ({len(results)}/{len(user_list)}):\n" + "\n".join(results[-10:]))

        await message.answer(
            f"✅ Масове оновлення завершено. Оновлено {len([r for r in results if r.startswith('✅')])} записів з {len(user_list)}.")
    else:
        await message.answer("У вас немає доступу до цієї команди.")


async def send_daily_message(day='tomorrow'):
    """Надсилає графік всім користувачам (текстом)"""
    global driver
    user_list = get_all_user()
    logger.info(f"Початок надсилання графіків користувачам на {day}")

    if day == "today":
        container_xpath = TODAY_CONTAINER_XPATH
        message_prefix = f'Оновлений графік відключень💡 на сьогодні {todaydate()} 👇'
        day_name = "Сьогодні"
    else:
        container_xpath = TOMORROW_CONTAINER_XPATH
        message_prefix = f'Ваш графік відключень💡 на завтра {tomorowdate()} 👇'
        day_name = "Завтра"

    for user in user_list:
        try:
            user_number_str = user['turn']
            known_turn = user.get('turn_abbreviated')

            # === КРОК 1-3: ВХІД НА САЙТ ТА ОЧІКУВАННЯ МОДАЛЬНОГО ВІКНА (Рефакторинг) ===
            get_schedule_from_site(user_number_str)

            # === КРОК 4: ПАРСИНГ ГРАФІКУ ===
            schedule_text, turn_abbreviated = parse_schedule(driver, container_xpath, day_name, known_turn=known_turn)

            # === КРОК 6: ВІДПРАВКА ===
            if "❌ Графік на" in schedule_text or "💡 Графік на" in schedule_text:
                logger.info(f"Графік відсутній/невизначений для {user['user']}")
                continue

            # Оновлюємо чергу в базі, якщо вона була визначена під час парсингу
            if turn_abbreviated != "N/A" and known_turn is None:
                # Використовуємо внутрішній id, а не телеграм id
                add_users_turn_abbreviated(user_id=user['id'], turn_abbreviated=turn_abbreviated)

            await bot.send_message(chat_id=user['user'],
                                   text=f'{message_prefix}\n\n{schedule_text}')

            logger.info(f"Щоденне повідомлення відправлено користувачу: {user['user']}")

        except exceptions.BotBlocked:
            logger.warning(f"Користувач заблокував бота: {user['user']}")
            continue
        except WebDriverException as e:
            logger.error(f"WebDriver exception для користувача {user['user']}: {e}")
            continue
        except Exception as e:
            logger.error(f"Помилка при відправці щоденного повідомлення користувачу {user['user']}: {e}")
            continue


async def check_website_updates(turn='4.2'):  # last_schedule_text видалено!
    """Перевіряє оновлення графіку на сьогодні, використовуючи модальне вікно."""
    global driver
    check_number = get_first_user_with_turn_abbreviated(turn_abbreviated_value=turn)
    logger.info(f"Перевірку оновлень графіку запущено для черги {turn}, з номером рахунку {check_number}")

    # Завантажуємо останній збережений графік з JSON
    last_schedule_text = get_last_schedule(turn)
    if last_schedule_text is None:
        logger.info(f"Кеш для черги {turn} порожній. Перший запуск.")

    while True:
        try:
            # 1. ВХІД НА САЙТ ТА ОЧІКУВАННЯ МОДАЛЬНОГО ВІКНА
            get_schedule_from_site(check_number)

            # 2. Отримайте результат (ТЕКСТ)
            schedule_text, _ = parse_schedule(driver, TODAY_CONTAINER_XPATH, "Сьогодні", known_turn=turn)

            current_schedule_text = schedule_text

            # Нормалізація для надійного порівняння
            normalized_text = " ".join(current_schedule_text.split()).strip()
            # Для порівняння, ми також нормалізуємо останній збережений текст
            normalized_last_text = " ".join(last_schedule_text.split()).strip() if last_schedule_text else None

            logger.info(f'Актуальний графік для черги {turn} (початок): {normalized_text[:100]}...')

            # --- ЛОГІКА ПОРІВНЯННЯ ТА ОНОВЛЕННЯ ---

            # 1. Якщо це перший запуск (немає кешу) АБО текст змінився
            is_changed = normalized_text != normalized_last_text

            # 2. Ігноруємо "порожні" або помилкові графіки для оновлення
            is_valid_schedule = "❌ Графік на" not in normalized_text and "💡 Графік на" not in normalized_text

            if is_valid_schedule and (last_schedule_text is None or is_changed):
                logger.info(f"Знайдено оновлення на сайті для черги {turn}, розсилаємо графік")

                # Оновлюємо кеш
                update_last_schedule(turn, current_schedule_text)
                last_schedule_text = current_schedule_text  # Оновлюємо локально для наступної ітерації

                # Надсилаємо повідомлення
                await send_update_graph(turn=turn, schedule_text=current_schedule_text)

            # Якщо графік недійсний, але був збережений дійсний, не оновлюємо кеш і не розсилаємо
            elif not is_valid_schedule and last_schedule_text is not None:
                logger.warning(f"Графік для {turn} недійсний, але кеш не оновлюємо.")

        except Exception as e:
            logger.error(f"Помилка при перевірці оновлень сайту для черги {turn}: {e}")

        await asyncio.sleep(300)  # Перевірка кожні 5 хвилин

async def send_update_graph(turn=None, schedule_text=None):
    """Надсилає оновлений графік на сьогодні (текстом)"""
    user_list = get_all_user_with_turn(turn)
    logger.info(f"Початок надсилання ОНОВЛЕНИХ графіків користувачам (Черга {turn})")

    message_prefix = f'Оновлений графік відключень💡 на сьогодні {todaydate()} 👇'

    for user in user_list:
        try:
            # Обмеження на ранкові години (можна прибрати або змінити)
            if datetime.datetime.now().time().hour <= 6:
                logger.warning("Занадто рано для зміни графіків.")
                return None

            await bot.send_message(chat_id=user['user'],
                                   text=f'{message_prefix}\n\n{schedule_text}')

            logger.info(f"Оновлене повідомлення відправлено користувачу: {user['user']}")
        except exceptions.BotBlocked:
            logger.warning(f"Користувач заблокував бота: {user['user']}")
            continue
        except Exception as e:
            logger.error(f"Помилка при відправці оновленого повідомлення користувачу {user['user']}: {e}")
            continue


def main():
    scheduler = AsyncIOScheduler()
    # Щоденна розсилка графіку на завтра о 17:22
    scheduler.add_job(send_daily_message, trigger='cron', hour=17, minute=22, misfire_grace_time=15)
    # Щоденна розсилка оновленого графіку на сьогодні о 6:00
    scheduler.add_job(send_daily_message, trigger='cron', hour=6, minute=0, misfire_grace_time=15,
                      kwargs={'day': 'today'})
    scheduler.start()

    loop = asyncio.get_event_loop()
    turn_list = get_unique_abbreviated_turns()
    for i in turn_list:
        # Створюємо окремий таск для моніторингу кожної черги
        loop.create_task(check_website_updates(turn=i))

    executor.start_polling(dp, skip_updates=True)


# Створюємо клавіатуру (потрібно додати її перед main, щоб вона була доступна)
admin_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
admin_keyboard.add(KeyboardButton('/all_user_list'))
admin_keyboard.add(KeyboardButton('/send_tomorrow_graf_all'))
admin_keyboard.add(KeyboardButton('/send_today_graf_all'))
admin_keyboard.add(KeyboardButton('/update_all_turns'))
admin_keyboard.add(KeyboardButton('21010148'))

if __name__ == '__main__':
    main()