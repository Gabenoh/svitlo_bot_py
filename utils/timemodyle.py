import datetime


def todaydate():
    """
    Надсилає тепершню дату у форматі день.місяць.рік
    :return: current_date
    """
    # Отримуємо поточну дату та час
    current_date = datetime.datetime.now()
    # Форматуємо дату у форматі день.місяць.рік
    formatted_date = current_date.strftime("%d.%m.%Y")
    # Виводимо відформатовану дату
    return formatted_date


def tomorowdate():
    """
    Надсилає завтрішню дату у форматі день.місяць.рік
    :return: tomorrow_date
    """
    current_date = datetime.datetime.now()
    # Додаємо один день до поточної дати
    tomorrow = current_date + datetime.timedelta(days=1)

    # Форматуємо дату у форматі день.місяць.рік
    formatted_tomorrow = tomorrow.strftime("%d.%m.%Y")

    # Виводимо відформатовану завтрашню дату
    return formatted_tomorrow


if __name__ == '__main__':
    print(todaydate())
    print(tomorowdate())
