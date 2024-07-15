import logging
import cairosvg
import datetime
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor, exceptions
from selenium import webdriver
from selenium.webdriver.common.by import By
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from constants import TOKEN
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

# Налаштування Selenium WebDriver
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Запускає браузер у фоновому режимі
driver = webdriver.Chrome(options=options)

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
    if str(message.from_user.id) == '358330105':
        user_list = get_all_user()
        for row in user_list:
            await message.reply(f"№{row['id']}, user {row['user']}, \n turn - {row['turn']}")


@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    if str(message.from_user.id) == '358330105':
        await message.answer("Привіт, адмін!", reply_markup=admin_keyboard)
    else:
        await message.answer("У вас немає доступу до цієї команди.")


@dp.message_handler(commands=['send_tomorrow_graf_all'])
async def send_all_command(message: types.Message):
    if str(message.from_user.id) == '358330105':
        await send_daily_message()


@dp.message_handler(commands=['send_today_graf_all'])
async def send_all_command(message: types.Message):
    if str(message.from_user.id) == '358330105':
        await send_daily_message(day='todayGraphId')


@dp.message_handler()
async def get_schedule(message: types.Message):
    user_number = message.text
    logger.info(f'Користувач {message.from_user.first_name, message.from_user.last_name}'
                f'надіслав повідомлення {user_number}')
    try:
        # Відкрийте сайт
        driver.get("https://svitlo.oe.if.ua")

        # Знайдіть поле для введення номера і введіть номер
        number_input = driver.find_element(By.ID, "searchAccountNumber")
        number_input.send_keys(user_number)

        # Натисніть кнопку для отримання графіку
        submit_button = driver.find_element(By.ID, "accountNumberReport")
        submit_button.click()

        time.sleep(3)  # Зачекайте, поки сторінка завантажиться

        # Отримайте результат
        result_element = driver.find_element(By.ID, "todayGraphId")
        svg_code = result_element.get_attribute('outerHTML')
        with open('/home/galmed/svitlograf/chart.svg', 'w') as file:
            file.write(svg_code)

        check_user(message.from_user.id, user_number)
        remove_elements_before_first_gt('/home/galmed/svitlograf/chart.svg')

        # Шлях до SVG файлу
        svg_file_path = '/home/galmed/svitlograf/chart.svg'
        png_file_path = '/home/galmed/svitlograf/chart.png'
        if 'інформація щодо Графіка погодинного' in str(svg_code):
            await message.reply(text='Інформація щодо графіка відключень відсутня на '
                                     'сайті швидше за все сьогодні не буде відключень')
            return None

        # Конвертація SVG в PNG
        cairosvg.svg2png(url=svg_file_path, write_to=png_file_path)

        # Відправте PNG файл як зображення
        # Створіть InputFile об'єкт для PNG файлу
        png_file = InputFile(png_file_path)
        await message.reply_photo(photo=png_file)

    except Exception as e:
        await message.reply('Виникла помилка при отриманні графіку. Спробуйте пізніше.')
        logger.error(f"Error in get_schedule: {e}")


def remove_elements_before_first_gt(svg_file_path):
    # Відкриваємо SVG-файл для читання
    with open(svg_file_path, 'r') as file:
        content = file.read()

    # Знаходимо позицію першого знака >
    first_gt_index = content.find('<svg')

    # Видаляємо частину рядка до першого знака >
    content = content[first_gt_index:len(content)-12]
    content = content.replace('100%', '350px', 2)
    content = content.replace('font-size="0.6em"', 'font-size="10px"', 1)
    content = content.replace('font-size="0.8em"', 'font-size="15px"', 1)

    # Записуємо зміни у вихідний SVG-файл
    with open(svg_file_path, 'w') as file:
        file.write(content)


async def send_daily_message(day='tomorrowGraphId'):
    user_list = get_all_user()
    logger.info(f"Початок надсилання графіків користувачам")
    if not user_list:
        user_list = get_all_user()
    for user in user_list:
        try:
            if datetime.datetime.now().time().hour >= 23:
                logger.warning("Час перевищує 23:00, зупинка виконання.")
                await bot.send_message(chat_id=user['user'], text='Інформація щодо графіка відключень відсутня на '
                                                                  'сайті швидше за все завтра буде світло весь день')
                continue  # Переходьте до наступного користувача, не виходьте з циклу

            # Відкрийте сайт
            driver.get("https://svitlo.oe.if.ua")
            logger.info(f"Сайт відкрило")

            # Знайдіть поле для введення номера і введіть номер
            number_input = driver.find_element(By.ID, "searchAccountNumber")
            number_input.send_keys(user['turn'])
            logger.info(f"Елемент знайдено")

            # Натисніть кнопку для отримання графіку
            submit_button = driver.find_element(By.ID, "accountNumberReport")
            submit_button.click()
            logger.info(f"На елемент натиснуто")

            time.sleep(5)  # Зачекайте, поки сторінка завантажиться

            # Отримайте результат
            result_element = driver.find_element(By.ID, day)
            svg_code = result_element.get_attribute('outerHTML')

            logger.info(f"Перші рядки сфг файлу: {svg_code[:30]}")

            if 'Графік погодинних' in str(svg_code) or 'інформація щодо' in str(svg_code):
                logger.warning(f"Ще не має графіку відключень для {user['user']}")
                await asyncio.sleep(300)
                await asyncio.create_task(send_daily_message())
                break

            with open('chart.svg', 'w') as file:
                file.write(svg_code)

            remove_elements_before_first_gt('/home/galmed/svitlograf/chart.svg')

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
                                       text=f'Ваш графік відключень на завтра{tomorowdate()}')
            elif day == 'todayGraphId':
                await bot.send_message(chat_id=user['user'],
                                       text=f'Оновлений графік відключень на сьогодні{todaydate()}')
            await bot.send_photo(chat_id=user['user'], photo=png_file)
            logger.info(f"Щоденне повідомлення відправлено користувачу: {user['user']}")

        except exceptions.BotBlocked:
            logger.warning(f"Користувач заблокував бота: {user['user']}")
            continue  # Пропустити цього користувача і перейти до наступного
        except Exception as e:
            logger.error(f"Помилка при відправці щоденного повідомлення: {e}")
            await asyncio.sleep(900)
            await asyncio.create_task(send_daily_message())


def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_message, 'cron', hour=17, minute=22)  # Запланувати завдання на 17:22 кожного дня
    scheduler.start()

    # Запустити бота
    executor.start_polling(dp, skip_updates=True)


if __name__ == '__main__':
    main()
