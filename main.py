import logging
import cairosvg
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor, exceptions
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import time
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
    options.add_argument('--headless')  # Запускає браузер у фоновому режимі
    print('створено новий драйвер')
    return webdriver.Chrome(options=options)

# Ініціалізація WebDriver
driver = create_driver()
requests_count = 0
max_requests_before_restart = 100  # Перезапустити WebDriver після 100 запитів

# Створюємо клавіатуру
admin_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
admin_keyboard.add(KeyboardButton('/all_user_list'))
admin_keyboard.add(KeyboardButton('/send_tomorrow_graf_all'))
admin_keyboard.add(KeyboardButton('/send_today_graf_all'))
admin_keyboard.add(KeyboardButton('21010148'))

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
        await send_daily_message()

@dp.message_handler(commands=['send_today_graf_all'])
async def send_all_today_(message: types.Message):
    if await admin(message.from_user.id):
        await send_daily_message(day='todayGraphId')

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
            await bot.send_message(chat_id=user['user'], text='Інформація щодо графіка відключень відсутня на '
                                                              'сайті швидше за все завтра буде світло весь день')
        except Exception as e:
            logger.error(f"Помилка при відправці повідомлень про відсутність графіків.: {e}")

@dp.message_handler()
async def get_schedule(message: types.Message):
    """Отримання номер особового рахунку від користувача додавання його в базу на розсилку графіків"""
    global driver, requests_count
    user_number = message.text.strip()

    logger.info(f'Користувач {message.from_user.first_name, message.from_user.last_name}'
                f'надіслав повідомлення {user_number}')

    # Перевірка, чи введене значення містить тільки цифри та не більше 8 символів
    if not user_number.isdigit():
        await message.reply("Будь ласка, введіть правильний номер особового рахунку, що складається тільки з цифр.")
        return

    if len(user_number) > 8:
        await message.reply("Номер особового рахунку не може бути більше 8 символів. Спробуйте ще раз.")
        return

    if requests_count >= max_requests_before_restart:
        driver.quit()
        driver = create_driver()
        requests_count = 0

    for day_time in ["todayGraphId", 'tomorrowGraphId']:
        try:
            # Відкрийте сайт
            driver.get("https://svitlo.oe.if.ua")
            requests_count += 1

            # Знайдіть поле для введення номера і введіть номер
            number_input = driver.find_element(By.ID, "searchAccountNumber")
            number_input.send_keys(user_number)

            # Натисніть кнопку для отримання графіку
            submit_button = driver.find_element(By.ID, "accountNumberReport")
            submit_button.click()

            time.sleep(5)  # Зачекайте, поки сторінка завантажиться

            # Отримайте результат
            result_element = driver.find_element(By.ID, day_time)
            svg_code = result_element.get_attribute('outerHTML')
            with open('/home/galmed/svitlograf/chart.svg', 'w') as file:
                file.write(svg_code)

            # додавання скороченої черги відключень
            min_turn = turn_abbreviated_check('/home/galmed/svitlograf/chart.svg')
            check_user(message.from_user.id, user_number, min_turn)
            remove_elements_before_first_gt('/home/galmed/svitlograf/chart.svg')

            # Шлях до SVG файлу
            svg_file_path = '/home/galmed/svitlograf/chart.svg'
            png_file_path = '/home/galmed/svitlograf/chart.png'
            if 'інформація щодо Графіка погодинного' in str(svg_code):
                await message.reply(text='Інформація щодо графіка відключень відсутня на '
                                         'сайті швидше за все сьогодні не буде відключень')
                return None
            if 'Графік погодинних вимкнень' in svg_code:
                await message.reply(f'Вашого графіка погодинних відключень на завтра {tomorowdate()} ще немає')
                break
            elif day_time == 'tomorrowGraphId':
                await message.reply(text=f'Ваш графік відключень на завтра {tomorowdate()} 👇')
            elif day_time == 'todayGraphId':
                await message.reply(text=f'Ваш графік відключень на сьогодні {todaydate()} 👇')
            # Конвертація SVG в PNG
            cairosvg.svg2png(url=svg_file_path, write_to=png_file_path)

            # Відправте PNG файл як зображення
            # Створіть InputFile об'єкт для PNG файлу
            png_file = InputFile(png_file_path)
            await message.reply_photo(photo=png_file)

        except NoSuchElementException:
            await message.reply('Номер особового рахунку не коректний або не знайдено графік відключень. '
                                'Перевірте номер і спробуйте ще раз.')
            logger.error("Error in get_schedule: "
                         "Номер особового рахунку не коректний або не знайдено графік відключень.")
        except WebDriverException as e:
            logger.error(f"WebDriver exception: {e}")
            await message.reply("Виникла проблема з обробкою вашого запиту. Спробуйте пізніше.")
        except Exception as e:
            await message.reply('Виникла помилка при отриманні графіку. Спробуйте пізніше.')
            logger.error(f"Error in get_schedule: {e}")

async def send_daily_message(day='tomorrowGraphId'):
    global driver, requests_count
    user_list = get_all_user()
    logger.info(f"Початок надсилання графіків користувачам")
    for user in user_list:
        try:
            if datetime.datetime.now().time().hour >= 22:
                logger.warning("Час перевищує 22:00, зупинка виконання.")
                await send_message_to_all()
                return None

            if requests_count >= max_requests_before_restart:
                driver.quit()
                driver = create_driver()
                requests_count = 0

            # Відкрийте сайт
            driver.get("https://svitlo.oe.if.ua")
            requests_count += 1

            # Знайдіть поле для введення номера і введіть номер
            number_input = driver.find_element(By.ID, "searchAccountNumber")
            number_input.send_keys(user['turn'])

            # Натисніть кнопку для отримання графіку
            submit_button = driver.find_element(By.ID, "accountNumberReport")
            submit_button.click()

            time.sleep(5)  # Зачекайте, поки сторінка завантажиться

            # Отримайте результат
            result_element = driver.find_element(By.ID, day)
            svg_code = result_element.get_attribute('outerHTML')

            if 'Графік погодинних' in str(svg_code) or 'інформація щодо' in str(svg_code):
                logger.warning(f"Ще не має графіку відключень для {user['user']}")
                await asyncio.sleep(300)
                await asyncio.create_task(send_daily_message())
                break

            with open('chart.svg', 'w') as file:
                file.write(svg_code)

            remove_elements_before_first_gt('/home/galmed/svitlograf/chart.svg')

            # Додавання скороченої черги
            turn_abbreviated = turn_abbreviated_check('/home/galmed/svitlograf/chart.svg')
            add_users_turn_abbreviated(user_id=user['id'], turn_abbreviated=turn_abbreviated)

            # Шлях до SVG файлу
            svg_file_path = '/home/galmed/svitlograf/chart.svg'
            png_file_path = '/home/galmed/svitlograf/chart.png'

            # Конвертація SVG в PNG
            cairosvg.svg2png(url=svg_file_path, write_to=png_file_path)

            # Відправте PNG файл як зображення
            # Створіть InputFile об'єкт для PNG файлу
            png_file = InputFile(png_file_path)
            if day == 'tomorrowGraphId':
                await bot.send_message(chat_id=user['user'],
                                       text=f'Ваш графік відключень на завтра {tomorowdate()} 👇')
            elif day == 'todayGraphId':
                await bot.send_message(chat_id=user['user'],
                                       text=f'Оновлений графік відключень на сьогодні {todaydate()} 👇')
            await bot.send_photo(chat_id=user['user'], photo=png_file)
            logger.info(f"Щоденне повідомлення відправлено користувачу: {user['user']}, з ID: {user['id']}")

        except exceptions.BotBlocked:
            logger.warning(f"Користувач заблокував бота: {user['user']}")
            continue  # Пропустити цього користувача і перейти до наступного
        except WebDriverException as e:
            logger.error(f"WebDriver exception: {e}")
            await asyncio.sleep(900)
            await asyncio.create_task(send_daily_message())
        except Exception as e:
            logger.error(f"Помилка при відправці щоденного повідомлення: {e}")
            await asyncio.sleep(900)
            await asyncio.create_task(send_daily_message())


async def check_website_updates(last_color_list=None, turn='4.1'):
    global driver, requests_count
    check_number = get_first_user_with_turn_abbreviated(turn_abbreviated_value=turn)
    logger.info(f"Перевірку оновлень графіку запущено для черги {turn}, з номером рахунку {check_number}")
    while True:
        try:
            if requests_count >= max_requests_before_restart:
                driver.quit()
                driver = create_driver()
                requests_count = 0

            # Відкрийте сайт
            driver.get("https://svitlo.oe.if.ua")
            requests_count += 1

            number_input = driver.find_element(By.ID, "searchAccountNumber")
            number_input.send_keys(check_number)

            # Натисніть кнопку для отримання графіку
            submit_button = driver.find_element(By.ID, "accountNumberReport")
            submit_button.click()

            time.sleep(10)  # Зачекайте, поки сторінка завантажиться

            # Отримайте результат
            result_element = driver.find_element(By.ID, 'todayGraphId')
            svg_code = result_element.get_attribute('outerHTML')
            color_list = extract_colors_from_svg(svg_code)


            if last_color_list is None:
                last_color_list = color_list

            if last_color_list != color_list:
                logger.info("Знайдено оновлення на сайті, розсилаємо графік")
                with open(f'/home/galmed/svitlograf/chart{turn}.svg', 'w') as file:
                    file.write(svg_code)
                last_color_list = color_list
                await send_update_graph(turn=turn,svg_file_path=f'/home/galmed/svitlograf/chart{turn}.svg')

        except Exception as e:
            logger.error(f"Помилка при перевірці оновлень сайту: {e}")

        await asyncio.sleep(300)  # Перевіряти оновлення кожні 5 хвилин


async def send_update_graph(day='todayGraphId',turn=None,svg_file_path=None):
    global driver, requests_count
    user_list = get_all_user_with_turn(turn)
    logger.info(f"Початок надсилання ОНОВЛЕНИХ графіків користувачам")
    remove_elements_before_first_gt(svg_file_path)
    for user in user_list:
        try:
            if datetime.datetime.now().time().hour <= 6:
                logger.warning("Занадто рано для зміни графіків.")
                return None

            if requests_count >= max_requests_before_restart:
                driver.quit()
                driver = create_driver()
                requests_count = 0

            # Шлях до SVG файлу
            png_file_path = f'/home/galmed/svitlograf/chart{turn}.png'

            # Конвертація SVG в PNG
            cairosvg.svg2png(url=svg_file_path, write_to=png_file_path)

            # Відправте PNG файл як зображення
            # Створіть InputFile об'єкт для PNG файлу
            png_file = InputFile(png_file_path)

            if day == 'todayGraphId':
                await bot.send_message(chat_id=user['user'],
                                       text=f'Оновлений графік відключень на сьогодні {todaydate()} 👇')
            await bot.send_photo(chat_id=user['user'], photo=png_file)
            logger.info(f"Оновлене повідомлення відправлено користувачу: {user['user']}, з ID: {user['id']}"
                        f" чергою - {user['turn_abbreviated']}")
        except exceptions.BotBlocked:
            logger.warning(f"Користувач заблокував бота: {user['user']}")
            continue  # Пропустити цього користувача і перейти до наступного
        except WebDriverException as e:
            logger.error(f"WebDriver exception: {e}")
            await asyncio.sleep(900)
        except Exception as e:
            logger.error(f"Помилка при відправці оновленого повідомлення: {e}")
            break

def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_message, 'cron', hour=17, minute=22)  # Запланувати завдання на 17:22 кожного дня
    scheduler.start()

    # Запустити перевірку сайту на оновлення
    loop = asyncio.get_event_loop()
    turn_list = get_unique_abbreviated_turns()
    for i in turn_list:
        loop.create_task(check_website_updates(turn=i))


    # Запустити бота
    executor.start_polling(dp, skip_updates=True)

if __name__ == '__main__':
    main()
