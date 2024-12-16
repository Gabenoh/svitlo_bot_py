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


def turn_abbreviated_check(svg_file_path):

    with open(svg_file_path, 'r') as file:
        content = file.read()
    turn_index = content.find('font-size: 30px">')
    turn_index = content[turn_index+17:turn_index+20]
    return turn_index


if __name__ == '__main__':
    print(turn_abbreviated_check('../svg_image/chart.svg'))