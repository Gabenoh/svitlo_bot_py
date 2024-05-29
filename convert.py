from selenium import webdriver
from selenium.webdriver.common.by import By
import time


options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Запускає браузер у фоновому режимі
driver = webdriver.Chrome(options=options)


def get_schedule():
    user_number = '21010148'

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
        result_element = driver.find_element(By.ID, "tomorrowGraphId")
        svg_code = result_element.get_attribute('outerHTML')
        print(svg_code)
        with open('/home/galmed/svitlograf/chart.svg', 'w') as file:
            file.write(svg_code)

    except Exception as e:
        print('Виникла помилка при отриманні графіку. Спробуйте пізніше.')
        print(f'{e}')

get_schedule()
'Графік погодинних вимкнень буде'