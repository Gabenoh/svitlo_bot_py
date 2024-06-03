import logging
import cairosvg
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InputFile
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from selenium import webdriver
from selenium.webdriver.common.by import By
from sqlalchemy.exc import SQLAlchemyError
import schedule
import asyncio
import time
from constants import TOKEN
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


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привіт! Введіть ваш номер особового рахунку для отримання графіку відключень світла.")


@dp.message_handler(commands=['all', 'всі'])
async def add_command(message: types.Message):
    if str(message.from_user.id) == '358330105':
        user_list = get_all_user()
        for row in user_list:
            await message.reply(f"№{row['id']}, user {row['user']}, \n turn - {row['turn']}")


@dp.message_handler()
async def get_schedule(message: types.Message):
    user_number = message.text

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
    content = content.replace('font-size="0.6em"', 'font-size="9px"', 1)

    # Записуємо зміни у вихідний SVG-файл
    with open(svg_file_path, 'w') as file:
        file.write(content)


async def send_daily_message():
    user_list = get_all_user()
    logger.info(f"Початок надсилання графіків користувачам")

    for user in user_list:
        try:
            current_time = datetime.datetime.now().time()
            if current_time.hour >= 23:
                logger.warning("Час перевищує 23:00, зупинка виконання.")
                await bot.send_message(chat_id=user['user'], text='Інформація щодо графіка відключень відсутня на '
                                                                  'сайті швидше за все завтра буде світло весь день')
            else:
                # Відкрийте сайт
                driver.get("https://svitlo.oe.if.ua")

                # Знайдіть поле для введення номера і введіть номер
                number_input = driver.find_element(By.ID, "searchAccountNumber")
                number_input.send_keys(user['turn'])

                # Натисніть кнопку для отримання графіку
                submit_button = driver.find_element(By.ID, "accountNumberReport")
                submit_button.click()

                time.sleep(5)  # Зачекайте, поки сторінка завантажиться

                # Отримайте результат
                result_element = driver.find_element(By.ID, "tomorrowGraphId")
                svg_code = result_element.get_attribute('outerHTML')

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
                await bot.send_photo(chat_id=user['user'], photo=png_file)
                logger.info(f"Щоденне повідомлення відправлено користувачу: {user['user']}")

        except Exception as e:
            logger.error(f"Помилка при відправці щоденного повідомлення: {e}")


async def scheduler():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)


def main():
    # Запланувати завдання на 20:02 кожного дня
    schedule.every().day.at("20:02").do(lambda: asyncio.create_task(send_daily_message()))

    # Запустити планувальник
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())

    # Запустити бота
    executor.start_polling(dp, skip_updates=True)


if __name__ == '__main__':
    main()
