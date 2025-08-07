import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .driver import setup_driver

logger = logging.getLogger(__name__)


def extract_company_basic_data(company_element):
    """Извлекает базовые данные компании из элемента"""
    company_data = {}

    try:
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
            detailed_info["Режим работы"] = working_hours_element.text.split("\n")[0]
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
            "Другие соцсети": "Н/Д",
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
