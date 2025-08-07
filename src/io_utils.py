import csv
import os

from .parser import determine_work_mode


def save_to_csv(data, file_path):
    if data:
        for company in data:
            company["Режим работы (тип)"] = determine_work_mode(company.get("Тип предприятия", "Н/Д"))

        fieldnames = [
            "Название", "Адрес", "Категория", "Рейтинг", "Отзывы", "Ссылка",
            "Телефоны", "Веб-сайт", "Режим работы", "Режим работы (тип)", "Тип предприятия",
            "ВКонтакте", "YouTube", "WhatsApp", "Telegram", "Instagram", "Facebook",
            "Одноклассники", "Twitter", "Другие соцсети", "Ссылка 2ГИС",
        ]

        for company in data:
            for field in fieldnames:
                if field not in company:
                    company[field] = "Н/Д"
    else:
        fieldnames = [
            "Название", "Адрес", "Категория", "Рейтинг", "Отзывы", "Ссылка",
            "Телефоны", "Веб-сайт", "Режим работы", "Режим работы (тип)", "Тип предприятия",
            "ВКонтакте", "YouTube", "WhatsApp", "Telegram", "Instagram", "Facebook",
            "Одноклассники", "Twitter", "Другие соцсети", "Ссылка 2ГИС",
        ]

    file_exists = os.path.isfile(file_path)

    with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')

        if not file_exists:
            writer.writeheader()

        for company in data:
            writer.writerow(company)
