import os
import time
import concurrent.futures
import argparse
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .driver import setup_driver
from .parser import extract_company_basic_data, process_company_batch
from .io_utils import save_to_csv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_FOLDER = "parsed_data"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

csv_file_path = os.path.join(OUTPUT_FOLDER, "kids_furniture_companies.csv")


def main():
    try:
        # Интерактивный ввод параметров
        logger.info("=== Настройка парсинга 2ГИС ===")

        # Словарь доступных городов
        cities = {
            "1": ("spb", "Санкт-Петербург"),
            "2": ("moscow", "Москва"),
            "3": ("novosibirsk", "Новосибирск"),
            "4": ("ekaterinburg", "Екатеринбург"),
            "5": ("kazan", "Казань"),
            "6": ("n_novgorod", "Нижний Новгород"),
            "7": ("krasnoyarsk", "Красноярск"),
            "8": ("chelyabinsk", "Челябинск"),
            "9": ("samara", "Самара"),
            "10": ("ufa", "Уфа"),
            "11": ("krasnodar", "Краснодар"),
            "12": ("omsk", "Омск"),
            "13": ("perm", "Пермь"),
            "14": ("rostov", "Ростов-на-Дону"),
            "15": ("voronezh", "Воронеж"),
            "16": ("volgograd", "Волгоград"),
        }

        logger.info("\nДоступные города:")
        for key, (alias, name) in cities.items():
            logger.info("%s. %s", key, name)

        while True:
            city_choice = input("\nВыберите город (введите номер): ").strip()
            if city_choice in cities:
                city_alias, city_name = cities[city_choice]
                break
            else:
                logger.warning("Неверный выбор. Попробуйте снова.")

        search_query = input(f"\nВведите поисковый запрос для {city_name}: ").strip()

        if not search_query:
            search_query = "детская мебель"
            logger.info("Используется запрос по умолчанию: '%s'", search_query)

        safe_query = "".join(c for c in search_query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_city = city_name.replace("-", "_").replace(" ", "_")
        global csv_file_path
        csv_file_path = os.path.join(OUTPUT_FOLDER, f"{safe_city}_{safe_query.replace(' ', '_')}.csv")

        logger.info("\nНачинаем парсинг:")
        logger.info("Город: %s", city_name)
        logger.info("Запрос: %s", search_query)
        logger.info("Файл результатов: %s", csv_file_path)
        logger.info("=" * 50)

        driver = setup_driver()

        MAX_WORKERS = 4
        BATCH_SIZE = 3

        logger.info("Открытие сайта 2ГИС...")
        driver.get(f"https://2gis.ru/{city_alias}")
        logger.info("Открыт 2ГИС для города %s", city_name)

        search_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input._cu5ae4")))

        search_input.send_keys(search_query)
        search_input.send_keys(Keys.ENTER)
        logger.info("Введен запрос: '%s'", search_query)

        WebDriverWait(driver, 7).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div._1kf6gff")))

        time.sleep(3)

        current_page = 1
        max_pages = 100

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

        while current_page <= max_pages:
            logger.info("Обработка страницы %s", current_page)

            time.sleep(1.5)

            company_elements = driver.find_elements(By.CSS_SELECTOR, "div._1kf6gff")

            if not company_elements:
                logger.info("Компании не найдены на этой странице")
                break

            logger.info("Обработка %s компаний на странице", len(company_elements))

            companies_basic_data = []
            for i, element in enumerate(company_elements):
                try:
                    try:
                        current_elements = driver.find_elements(By.CSS_SELECTOR, "div._1kf6gff")
                        if i < len(current_elements):
                            element = current_elements[i]
                        else:
                            logger.debug("Элемент %s больше не доступен", i)
                            continue
                    except:
                        logger.warning("Не удалось повторно найти элемент %s", i)
                        continue

                    basic_data = extract_company_basic_data(element)
                    companies_basic_data.append(basic_data)
                except Exception as e:
                    logger.warning(
                        "Ошибка при извлечении базовых данных для элемента %s: %s",
                        i,
                        e,
                    )
                    continue

            logger.info(
                "Извлечены базовые данные для %s компаний",
                len(companies_basic_data),
            )

            batches = [companies_basic_data[i:i + BATCH_SIZE] for i in range(0, len(companies_basic_data), BATCH_SIZE)]

            futures = []
            for batch in batches:
                future = executor.submit(process_company_batch, batch)
                futures.append(future)

            all_companies_data = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    batch_data = future.result()
                    all_companies_data.extend(batch_data)
                except Exception as e:
                    logger.warning("Ошибка при получении результатов из потока: %s", e)

            if all_companies_data:
                save_to_csv(all_companies_data, csv_file_path)
                logger.info(
                    "Данные с страницы %s сохранены в CSV", current_page
                )

            try:
                next_page_found = False

                try:
                    xpaths = [
                        f"//span[contains(@class, '_19xy60y') and text()='{current_page + 1}']",
                        f"//div[contains(@class, '_l934xo5')]/span[text()='{current_page + 1}']",
                        f"//div[contains(@class, '_l934xo5')]//span[text()='{current_page + 1}']",
                        f"//div//span[contains(@class, '_19xy60y') and text()='{current_page + 1}']",
                    ]

                    for xpath in xpaths:
                        try:
                            next_page_buttons = driver.find_elements(By.XPATH, xpath)
                            if next_page_buttons:
                                driver.execute_script("arguments[0].scrollIntoView(true);", next_page_buttons[0])
                                time.sleep(0.5)
                                driver.execute_script("arguments[0].click();", next_page_buttons[0])
                                next_page_found = True
                                logger.debug(
                                    "Найдена кнопка для страницы %s (способ 1, xpath: %s)",
                                    current_page + 1,
                                    xpath,
                                )
                                break
                        except Exception as e_sub:
                            continue

                    if not next_page_found:
                        raise Exception("Ни один xpath не сработал")

                except Exception as e1:
                    logger.debug("Способ 1 не удался: %s", str(e1)[:100])

                if not next_page_found:
                    try:
                        page_elements = driver.find_elements(By.XPATH, f"//*[text()='{current_page + 1}']")
                        for element in page_elements:
                            try:
                                if element.is_displayed():
                                    parent = element.find_element(By.XPATH, "./ancestor::*[self::button or self::div][1]")
                                    driver.execute_script("arguments[0].scrollIntoView(true);", parent)
                                    time.sleep(0.5)
                                    driver.execute_script("arguments[0].click();", parent)
                                    next_page_found = True
                                    logger.debug(
                                        "Найдена кнопка для страницы %s (способ 2)",
                                        current_page + 1,
                                    )
                                    break
                            except:
                                continue
                    except Exception as e2:
                        logger.debug("Способ 2 не удался: %s", str(e2)[:100])

                if not next_page_found:
                    try:
                        next_buttons = driver.find_elements(By.XPATH,
                            "//button[contains(@aria-label, 'Следующ') or contains(@aria-label, 'Next') or contains(@aria-label, 'вперед') or contains(@aria-label, 'Вперед')]")
                        if next_buttons:
                            driver.execute_script("arguments[0].scrollIntoView(true);", next_buttons[0])
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", next_buttons[0])
                            next_page_found = True
                            logger.debug(
                                "Найдена кнопка 'Вперед/Следующая' для перехода на следующую страницу (способ 3)"
                            )
                    except Exception as e3:
                        logger.debug("Способ 3 не удался: %s", str(e3)[:100])

                if not next_page_found and current_page >= 67:
                    try:
                        screenshot_path = f"pagination_debug_page_{current_page}.png"
                        driver.save_screenshot(screenshot_path)
                        logger.warning(
                            "Сохранен скриншот пагинации: %s", screenshot_path
                        )

                        pagination_html = driver.execute_script("""
                            var elements = document.querySelectorAll('div[class*="_l934xo5"], div[class*="_19xy60y"], div[class*="pagination"]');
                            return Array.from(elements).map(el => el.outerHTML).join('\\n');
                        """)
                        logger.debug("HTML пагинации:\n%s", pagination_html)

                        try:
                            driver.execute_script(f"""
                                var nextPage = {current_page + 1};
                                var allElements = document.querySelectorAll('*');
                                for(var i=0; i<allElements.length; i++) {{
                                    if(allElements[i].textContent == nextPage &&
                                      (allElements[i].classList.contains('_19xy60y') ||
                                       allElements[i].parentElement.classList.contains('_l934xo5'))) {{
                                        allElements[i].click();
                                        return true;
                                    }}
                                }}
                                return false;
                            """)
                            time.sleep(2)
                            new_company_elements = driver.find_elements(By.CSS_SELECTOR, "div._1kf6gff")
                            if new_company_elements and len(new_company_elements) > 0:
                                next_page_found = True
                                logger.debug(
                                    "Переход на страницу %s выполнен через JavaScript",
                                    current_page + 1,
                                )
                        except Exception as e_js:
                            logger.debug(
                                "JavaScript переход не удался: %s",
                                str(e_js)[:100],
                            )
                    except Exception as e4:
                        logger.debug("Способ 4 не удался: %s", str(e4)[:100])

                if next_page_found:
                    current_page += 1
                    logger.info("Успешный переход на страницу %s", current_page)
                    time.sleep(2)
                    continue
                else:
                    raise Exception("Не удалось найти кнопку следующей страницы")

            except Exception as e:
                logger.warning(
                    "Не удалось перейти на следующую страницу: %s",
                    str(e)[:100],
                )
                logger.info("Проверка наличия кнопки 'Показать ещё'...")

                try:
                    show_more_buttons = driver.find_elements(By.XPATH,
                        "//button[contains(text(), 'Показать ещё') or contains(text(), 'больше') or contains(text(), 'еще') or contains(@class, '_14xje6l')]")
                    if show_more_buttons and show_more_buttons[0].is_displayed():
                        logger.info(
                            "Найдена кнопка 'Показать ещё'. Нажимаем для загрузки следующей порции результатов."
                        )
                        driver.execute_script("arguments[0].scrollIntoView(true);", show_more_buttons[0])
                        time.sleep(0.5)
                        show_more_buttons[0].click()
                        current_page += 1
                        time.sleep(2)
                        continue
                except Exception as e_show_more:
                    logger.warning(
                        "Не удалось найти или нажать кнопку 'Показать ещё': %s",
                        str(e_show_more)[:100],
                    )

                logger.info(
                    "Достигнута последняя страница результатов или произошла ошибка пагинации."
                )
                logger.info("Парсинг завершен на странице %s", current_page)
                break

        executor.shutdown()
        logger.info(
            "Парсинг завершен. Данные сохранены в %s", csv_file_path
        )

    except Exception as e:
        logger.error("Произошла ошибка: %s", e)

    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="2ГИС парсер")
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    main()
