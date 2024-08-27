import re


def extract_colors_from_svg(file_path:str) -> list[str]:
    """

    :param file_path:
    :return: list of color

    """
    color_mapping = {
        "#fb6666": 'red',
        "#7acd6d": 'green'
    }

    # Змінна для збереження результату
    colors = []

    # Читання SVG файлу
    with open(file_path, 'r') as file:
        content = file.read()

    # Пошук всіх кодів кольорів у SVG файлі
    matches = re.findall(r'#\w{6}', content)

    # Перетворення знайдених кодів кольорів у назви
    for match in matches:
        color_name = color_mapping.get(match, None)
        if color_name:
            colors.append(color_name)

    return colors

if __name__ =='__main__':
    file_path = '/home/galmed/svitlograf/chart.svg'
    colors_list = extract_colors_from_svg(file_path)
    print(colors_list)