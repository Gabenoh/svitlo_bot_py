import datetime

# Отримуємо поточну дату та час
current_date = datetime.datetime.now()


def todaydate():
    # Форматуємо дату у форматі день.місяць.рік
    formatted_date = current_date.strftime("%d.%m.%Y")
    # Виводимо відформатовану дату
    return formatted_date


def tomorowdate():
    # Додаємо один день до поточної дати
    tomorrow = current_date + datetime.timedelta(days=1)

    # Форматуємо дату у форматі день.місяць.рік
    formatted_tomorrow = tomorrow.strftime("%d.%m.%Y")

    # Виводимо відформатовану завтрашню дату
    return formatted_tomorrow


if __name__ == '__main__':
    print(todaydate())
    print(tomorowdate())
