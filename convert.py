from selenium import webdriver
from selenium.webdriver.common.by import By
import cairosvg
import time


options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Запускає браузер у фоновому режимі
driver = webdriver.Chrome(options=options)


def get_schedule(user_number = '21010148'):
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
        print(svg_code)
        with open('/logs/chart.svg', 'w') as file:
            file.write(svg_code)
        svg_file_path = '/home/galmed/svitlograf/svg_image/chart.svg'
        png_file_path = '/home/galmed/svitlograf/svg_image/chart.png'
        remove_elements_before_first_gt(svg_file_path)
        cairosvg.svg2png(url=svg_file_path, write_to=png_file_path)

    except Exception as e:
        print('Виникла помилка при отриманні графіку. Спробуйте пізніше.')
        print(f'{e}')


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


get_schedule()
