
import os
import time
import csv
import concurrent.futures
import argparse
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_FOLDER = "parsed_data"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

csv_file_path = os.path.join(OUTPUT_FOLDER, "kids_furniture_companies.csv")


def setup_driver():
    logger.info("Инициализация драйвера...")
    chrome_options = Options()

    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-features=NetworkService")
    chrome_options.add_argument("--dns-prefetch-disable")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--enable-features=NetworkServiceInProcess")

    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    )

    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.cookies": 1,
        "profile.managed_default_content_settings.javascript": 1,
        "profile.managed_default_content_settings.plugins": 1,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.media_stream": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    logger.info("Создание экземпляра Chrome...")
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(20)
        logger.info("Драйвер успешно создан")
        return driver
    except Exception as e:
        logger.error("Ошибка при создании драйвера: %s", e)
        raise


def extract_company_basic_data(company_element):
    """Извлекает базовые данные компании из элемента"""
    company_data = {}
    
    try:
        # Добавим небольшую паузу и проверку доступности элемента
        if not company_element.is_displayed():
            raise Exception("Элемент не отображается")

        name_element = company_element.find_element(By.CSS_SELECTOR, "._1rehek")
        company_data["Название"] = name_element.text.strip()
        company_data["Ссылка 2ГИС"] = name_element.get_attribute("href")
    except Exception as e:
        logger.warning("Ошибка при получении названия: %s", e)
        company_data["Название"] = "Н/Д"
        company_data["Ссылка 2ГИС"] = "Н/Д"

    try:
        address = company_element.find_element(By.CSS_SELECTOR, "._14quei").text.strip()
        company_data["Адрес"] = address
    except Exception as e:
        logger.warning("Ошибка при получении адреса: %s", e)
        company_data["Адрес"] = "Н/Д"

    try:
        category = company_element.find_element(By.CSS_SELECTOR, "._4cxmw7").text.strip()
        company_data["Категория"] = category
    except Exception as e:
        logger.warning("Ошибка при получении категории: %s", e)
        company_data["Категория"] = "Н/Д"

    try:
        rating = company_element.find_element(By.CSS_SELECTOR, "._y10azs").text.strip()
        company_data["Рейтинг"] = rating
    except Exception as e:
        logger.warning("Ошибка при получении рейтинга: %s", e)
        company_data["Рейтинг"] = "Н/Д"

    try:
        reviews = company_element.find_element(By.CSS_SELECTOR, "._jspzdm").text.strip()
        company_data["Отзывы"] = reviews
    except Exception as e:
        logger.warning("Ошибка при получении отзывов: %s", e)
        company_data["Отзывы"] = "Н/Д"

    return company_data


def parse_company_data(company_basic_data, driver):
    """Получает детальную информацию о компании"""
    company_data = company_basic_data.copy()
    
    link = company_data.get("Ссылка 2ГИС")
    if link and link != "Н/Д":
        try:
            detailed_info = get_company_details(driver, link)
            
            if detailed_info.get("Веб-сайт") and detailed_info.get("Веб-сайт") != "Н/Д":
                company_data["Ссылка"] = detailed_info["Веб-сайт"]
            else:
                company_data["Ссылка"] = link
            
            company_data.update(detailed_info)
        except Exception as e:
            logger.warning(
                "Ошибка при получении деталей для %s: %s",
                company_data["Название"],
                e,
            )
            company_data["Ссылка"] = link
    else:
        company_data["Ссылка"] = "Н/Д"
    
    return company_data


def get_company_details(driver, company_url):
    logger.info("Переход на страницу компании: %s", company_url)

    main_window = driver.current_window_handle

    try:
        driver.execute_script(f"window.open('{company_url}', '_blank');")

        driver.switch_to.window(driver.window_handles[-1])

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div._qvsf7z")))

        time.sleep(0.5)

        detailed_info = {}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                show_phones_buttons = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "button._1tkj2hw")))

                if show_phones_buttons:
                    WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "button._1tkj2hw"))).click()

                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div._b0ke8 a")))

                time.sleep(0.2)
                try:
                    phone_elements = WebDriverWait(driver, 3).until(
                        EC.presence_of_all_elements_located(
                            (By.CSS_SELECTOR, "div._b0ke8 a")))
                    
                    phones = driver.execute_script("""
                        var elements = arguments[0];
                        var phones = [];
                        for (var i = 0; i < elements.length; i++) {
                            var text = elements[i].innerText.trim();
                            if (text) phones.push(text);
                        }
                        return phones;
                    """, phone_elements)
                except:
                    phones = []

                if phones:
                    detailed_info["Телефоны"] = "; ".join(phones)
                    break

            except Exception as e:
                logger.debug(
                    "Попытка %s/%s. Ошибка при получении телефонов: %s",
                    attempt + 1,
                    max_retries,
                    e,
                )
                time.sleep(1)

        if "Телефоны" not in detailed_info:
            detailed_info["Телефоны"] = "Н/Д"

        try:
            website_link_elements = driver.find_elements(
                By.CSS_SELECTOR, "div._49kxlr a[href*='link.2gis.ru']")
            for link_element in website_link_elements:
                href = link_element.get_attribute("href")
                if "http" in href and "/firm/" not in href and "tel:" not in href:
                    if "link.2gis.ru" in href:
                        try:
                            driver.execute_script(
                                f"window.open('{href}', '_blank');")
                            driver.switch_to.window(driver.window_handles[-1])
                            time.sleep(1.5)
                            final_url = driver.current_url
                            driver.close()
                            driver.switch_to.window(driver.window_handles[-1])
                            detailed_info["Веб-сайт"] = final_url
                            break
                        except:
                            detailed_info["Веб-сайт"] = href
                            break
                    else:
                        detailed_info["Веб-сайт"] = href
                        break

            if "Веб-сайт" not in detailed_info:
                website_elements = driver.find_elements(
                    By.XPATH, "//div[contains(@class, '_49kxlr')]//a")
                for element in website_elements:
                    href = element.get_attribute("href")
                    if href and "http" in href and "tel:" not in href and "/firm/" not in href:
                        detailed_info["Веб-сайт"] = href
                        break

            if "Веб-сайт" not in detailed_info:
                detailed_info["Веб-сайт"] = "Н/Д"
        except Exception as e:
            logger.warning("Ошибка при получении веб-сайта: %s", e)
            detailed_info["Веб-сайт"] = "Н/Д"

        try:
            working_hours_element = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div._ksc2xc")))
            detailed_info["Режим работы"] = working_hours_element.text.split(
                "\n")[0]
        except:
            detailed_info["Режим работы"] = "Н/Д"
            
        try:
            detailed_info["Тип предприятия"] = "Н/Д"
            
            try:
                info_tab = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@class, '_2lcm958') and contains(text(), 'Инфо')]"))
                )
                if info_tab:
                    info_tab.click()
                    logger.debug("Переключились на вкладку Инфо")
                    time.sleep(1)
            except:
                logger.warning("Не удалось найти или переключиться на вкладку Инфо")
            
            try:
                business_type_block = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@data-rack='true' and contains(., 'Тип предприятия')]"))
                )
                
                if business_type_block:
                    business_type_buttons = business_type_block.find_elements(By.XPATH, ".//button[contains(@class, '_1rehek')]")
                    if business_type_buttons:
                        types = [btn.text.strip() for btn in business_type_buttons if btn.text.strip()]
                        detailed_info["Тип предприятия"] = "; ".join(types)
                        logger.debug(
                            "Найден тип предприятия: %s", detailed_info["Тип предприятия"]
                        )
                work_mode = determine_work_mode(detailed_info['Тип предприятия'])
                logger.debug("Определен режим работы: %s", work_mode)
            except Exception as e:
                logger.debug("Способ 1 не удался: %s", e)
            
            if detailed_info["Тип предприятия"] == "Н/Д":
                try:
                    company_type_spans = driver.find_elements(By.XPATH, "//span[contains(text(), 'Тип предприятия')]")
                    
                    for span in company_type_spans:
                        parent_div = span.find_element(By.XPATH, "./ancestor::div[contains(@class, '_172gbf8')]")
                        next_div = parent_div.find_element(By.XPATH, "following-sibling::div")
                        type_buttons = next_div.find_elements(By.XPATH, ".//button[contains(@class, '_1rehek')]")
                        if type_buttons:
                            types = [btn.text.strip() for btn in type_buttons if btn.text.strip()]
                            detailed_info["Тип предприятия"] = "; ".join(types)
                            logger.debug(
                                "Найден тип предприятия (способ 2): %s",
                                detailed_info["Тип предприятия"],
                            )
                            break
                except Exception as e:
                    logger.debug("Способ 2 не удался: %s", e)
            
            if detailed_info["Тип предприятия"] == "Н/Д":
                try:
                    elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Тип предприятия')]/ancestor::div[contains(@class, '_172gbf8')]")
                    
                    for element in elements:
                        full_text = element.text
                        if "Тип предприятия" in full_text:
                            next_div = element.find_element(By.XPATH, "following-sibling::div")
                            business_types = next_div.text.strip()
                            if business_types:
                                detailed_info["Тип предприятия"] = business_types
                                logger.debug(
                                    "Найден тип предприятия (способ 3): %s",
                                    detailed_info["Тип предприятия"],
                                )
                                break
                except Exception as e:
                    logger.debug("Способ 3 не удался: %s", e)
            
            if detailed_info["Тип предприятия"] == "Н/Д":
                try:
                    all_text_blocks = driver.find_elements(By.XPATH, "//div[contains(text(), 'Тип предприятия') or .//span[contains(text(), 'Тип предприятия')]]")
                    
                    for block in all_text_blocks:
                        parent_container = block.find_element(By.XPATH, "ancestor::div[contains(@data-rack, 'true')]")
                        buttons = parent_container.find_elements(By.XPATH, ".//button[contains(@class, '_1rehek')]")
                        if buttons:
                            types = [btn.text.strip() for btn in buttons if btn.text.strip()]
                            detailed_info["Тип предприятия"] = "; ".join(types)
                            logger.debug(
                                "Найден тип предприятия (способ 4): %s",
                                detailed_info["Тип предприятия"],
                            )
                            break
                except Exception as e:
                    logger.debug("Способ 4 не удался: %s", e)
                
        except Exception as e:
            logger.warning("Ошибка при получении типа предприятия: %s", e)
            detailed_info["Тип предприятия"] = "Н/Д"

        try:
            social_networks = {
                "ВКонтакте": "Н/Д", "YouTube": "Н/Д", "WhatsApp": "Н/Д",
                "Telegram": "Н/Д", "Instagram": "Н/Д", "Facebook": "Н/Д",
                "Одноклассники": "Н/Д", "Twitter": "Н/Д", "Другие соцсети": "Н/Д"
            }
            
            try:
                social_networks_script = """
                    const socialPatterns = {
                        'ВКонтакте': ['vk.com', 'vkontakte'],
                        'YouTube': ['youtube.com', 'youtu.be'],
                        'WhatsApp': ['wa.me', 'whatsapp'],
                        'Telegram': ['t.me', 'telegram'],
                        'Instagram': ['instagram.com'],
                        'Facebook': ['facebook.com', 'fb.com'],
                        'Одноклассники': ['ok.ru', 'odnoklassniki'],
                        'Twitter': ['twitter.com']
                    };
                    
                    const results = {};
                    const otherSocials = [];
                    
                    const links = document.querySelectorAll('a[href*="http"]');
                    
                    for (const link of links) {
                        const href = link.href || '';
                        if (!href) continue;
                        
                        let matched = false;
                        for (const [network, patterns] of Object.entries(socialPatterns)) {
                            if (patterns.some(pattern => href.includes(pattern))) {
                                results[network] = href;
                                matched = true;
                                break;
                            }
                        }
                        
                        if (!matched && (href.includes('social') || href.includes('share'))) {
                            const text = link.innerText.trim();
                            if (text) {
                                otherSocials.push(`${text}: ${href}`);
                            }
                        }
                    }
                    
                    if (otherSocials.length > 0) {
                        results['Другие соцсети'] = otherSocials.join('; ');
                    }
                    
                    return results;
                """
                
                social_links = driver.execute_script(social_networks_script)
                
                if social_links and isinstance(social_links, dict):
                    for network, url in social_links.items():
                        if network in social_networks:
                            social_networks[network] = url
                
            except Exception as e:
                logger.debug("Ошибка при поиске соцсетей через JavaScript: %s", e)
            
            if all(value == "Н/Д" for key, value in social_networks.items() if key != "Другие соцсети"):
                try:
                    contact_tabs = driver.find_elements(By.XPATH, "//a[contains(@class, '_rdxuhv3') or contains(@class, '_12jewu69') and contains(text(), 'Контакты')]")
                    
                    if contact_tabs:
                        contact_tabs[0].click()
                        logger.debug("Переключились на вкладку Контакты")
                        time.sleep(0.5)
                        
                        social_links = driver.execute_script(social_networks_script)
                        
                        if social_links and isinstance(social_links, dict):
                            for network, url in social_links.items():
                                if network in social_networks:
                                    social_networks[network] = url
                                    
                except Exception as e:
                    logger.debug("Ошибка при поиске соцсетей на вкладке Контакты: %s", e)
            
            detailed_info.update(social_networks)
            
        except Exception as e:
            logger.warning("Ошибка при получении социальных сетей: %s", e)
            detailed_info.update({
                "ВКонтакте": "Н/Д", "YouTube": "Н/Д", "WhatsApp": "Н/Д",
                "Telegram": "Н/Д", "Instagram": "Н/Д", "Facebook": "Н/Д",
                "Одноклассники": "Н/Д", "Twitter": "Н/Д", "Другие соцсети": "Н/Д"
            })

    except Exception as e:
        logger.error("Критическая ошибка при получении данных компании: %s", e)
        return {
            "Телефоны": "Н/Д",
            "Веб-сайт": "Н/Д",
            "Режим работы": "Н/Д",
            "Тип предприятия": "Н/Д",
            "ВКонтакте": "Н/Д",
            "YouTube": "Н/Д",
            "WhatsApp": "Н/Д",
            "Telegram": "Н/Д",
            "Instagram": "Н/Д",
            "Facebook": "Н/Д",
            "Одноклассники": "Н/Д",
            "Twitter": "Н/Д",
            "Другие соцсети": "Н/Д"
        }

    finally:
        try:
            driver.close()
            driver.switch_to.window(main_window)
        except Exception as e:
            logger.warning("Ошибка при закрытии вкладки: %s", e)

        time.sleep(2)

    return detailed_info


def determine_work_mode(business_type):
    if business_type == "Н/Д":
        return "Н/Д"
        
    business_type = business_type.lower()
    
    online_indicators = ["интернет-магазин", "интернет магазин", "онлайн"]
    
    offline_indicators = ["розница", "опт", "оптовая", "производство", 
                         "магазин", "шоурум", "салон", "студия", "офис"]
    
    has_online = any(indicator in business_type for indicator in online_indicators)
    has_offline = any(indicator in business_type for indicator in offline_indicators)
    
    if has_online and has_offline:
        return "Онлайн/Оффлайн"
    elif has_online:
        return "Онлайн"
    elif has_offline:
        return "Оффлайн"
    else:
        return "Не определено"

def save_to_csv(data, file_path):
    if data:
        for company in data:
            company["Режим работы (тип)"] = determine_work_mode(company.get("Тип предприятия", "Н/Д"))
        
        fieldnames = [
            "Название", "Адрес", "Категория", "Рейтинг", "Отзывы", "Ссылка",
            "Телефоны", "Веб-сайт", "Режим работы", "Режим работы (тип)", "Тип предприятия", 
            "ВКонтакте", "YouTube", "WhatsApp", "Telegram", "Instagram", "Facebook", 
            "Одноклассники", "Twitter", "Другие соцсети", "Ссылка 2ГИС"
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
            "Одноклассники", "Twitter", "Другие соцсети", "Ссылка 2ГИС"
        ]

    file_exists = os.path.isfile(file_path)

    with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')

        if not file_exists:
            writer.writeheader()

        for company in data:
            writer.writerow(company)


def process_company_batch(companies_basic_data):
    try:
        driver = setup_driver()
        companies_data = []
        for company_basic_data in companies_basic_data:
            try:
                company_data = parse_company_data(company_basic_data, driver)
                companies_data.append(company_data)
                logger.info("Обработана компания: %s", company_data["Название"])
            except Exception as e:
                logger.error("Ошибка при обработке компании: %s", e)
        driver.quit()
        return companies_data
    except Exception as e:
        logger.error("Ошибка в потоке обработки компаний: %s", e)
        return []

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
            "16": ("volgograd", "Волгоград")
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

            company_elements = driver.find_elements(By.CSS_SELECTOR,
                                                    "div._1kf6gff")

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
            
            batches = [companies_basic_data[i:i+BATCH_SIZE] for i in range(0, len(companies_basic_data), BATCH_SIZE)]
            
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
                        f"//div//span[contains(@class, '_19xy60y') and text()='{current_page + 1}']"
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
