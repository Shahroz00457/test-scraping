import os
import time

import pandas as pd
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.util import clean_price, upload_to_google_sheets
import re

load_dotenv()

SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
CRED_JSON = os.getenv("GOOGLE_SHEETS_CRED_JSON")

BASE_URL = "https://cuesale.com"
COLLECTION_URL = f"{BASE_URL}/shop/?per_page=36"

increment = 1


def init_driver():
    options = Options()
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors=yes")
    options.add_argument("--log-level=3")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless=new")
    options.add_experimental_option(
        "prefs",
        {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.managed_default_content_settings.media_stream": 2,
        },
    )
    return webdriver.Chrome(options=options)


def get_product_links(driver):
    links = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/product/']"))
    )

    product_links = []
    seen = set()
    for link in links:
        try:
            url = link.get_attribute("href")
            if not url or "cookieyes.com" in url or url in seen:
                continue
            seen.add(url)
            product_links.append(url)
        except Exception:
            continue

    return product_links


def get_product_details(driver, product_link):
    global increment

    original_window = driver.current_window_handle
    driver.execute_script("window.open(arguments[0], '_blank');", product_link)
    WebDriverWait(driver, 5).until(lambda current_driver: len(current_driver.window_handles) > 1)
    driver.switch_to.window(driver.window_handles[-1])

    try:
        try:
            title = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product_title"))
            ).text
        except Exception:
            title = "N/A"

        try:
            brand = driver.find_element(
                By.CSS_SELECTOR,
                "tr.woocommerce-product-attributes-item--attribute_pa_brand td",
            ).text
        except Exception:
            brand = "N/A"

        try:
            condition_raw = driver.find_element(
                By.CSS_SELECTOR,
                "tr.woocommerce-product-attributes-item--attribute_pa_condition-used td p",
            ).text.strip()
            condition_clean = condition_raw.replace("★", "").replace("✰", "").strip()
            if not condition_clean:
                condition_clean = driver.find_element(
                    By.CSS_SELECTOR,
                    "tr.woocommerce-product-attributes-item--attribute_pa_condition td",
                ).text.strip()
        except Exception:
            condition_clean = "N/A"

        try:
            product_ex_price = driver.find_element(By.CSS_SELECTOR, "p.price ins span.woocommerce-Price-amount").text.strip("€")
        except:
            try:
                product_ex_price = driver.find_element(By.CSS_SELECTOR, "p.price span.woocommerce-Price-amount").text.strip("€")
            except:
                product_ex_price = "N/A"

        try:
            quantity = driver.find_element(By.CSS_SELECTOR, "p.in-stock").text
            quantity = quantity.replace("in stock", "").strip()
        except Exception:
            quantity = "N/A"

        try:
            description = driver.find_element(By.ID, "tab-description").text.strip()
        except Exception:
            description = "N/A"

        try:
            image_src = ["N/A"]
            for attempt in range(3):
                try:
                    images = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".woocommerce-product-gallery__image a")))
                    image_src = []
                    for img in images:
                        href = img.get_attribute("href")
                        if href:
                            href = re.sub(r"-\d+x\d+(?=\.[a-zA-Z]+$)", "", href)
                            if href not in image_src:
                                image_src.append(href)
                    image_src = image_src or ["N/A"]
                    break
                except Exception as e:
                    print(f"Image fetch attempt {attempt + 1} failed: {e}")
                    time.sleep(2)
        except Exception:
            image_src = ["N/A"]

        try:
            category_block = driver.find_element(By.CSS_SELECTOR, "span.posted_in")
            category_links = category_block.find_elements(By.TAG_NAME, "a")
            category = category_links[0].text if len(category_links) > 0 else "N/A"
            subcategory = category_links[1].text if len(category_links) > 1 else "N/A"
        except Exception:
            category, subcategory = "N/A", "N/A"

        product_data = {
            "product_url": product_link,
            "title": title,
            "quantity": quantity,
            "category": category,
            "subcategory": subcategory,
            "ex_vat_price": clean_price(product_ex_price),
            "inc_vat_price": "N/A",
            "brand": brand,
            "condition": condition_clean,
            "description": description,
            "image": image_src,
        }

        print(
            increment,
            "\t",
            product_data["product_url"],
            product_data["title"],
            product_data["ex_vat_price"],
        )
        increment += 1
        return product_data
    finally:
        driver.close()
        driver.switch_to.window(original_window)


def extracting_detail(driver):
    extracted_data = []
    seen_links = set()
    COUNT = 0
    try:
        cookie = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.cky-btn-accept"))
        )
        cookie.click()
    except Exception:
        pass

    while True:
        try:
            time.sleep(3)
            product_links = get_product_links(driver)

            for link in product_links:
                if link in seen_links:
                    continue
                seen_links.add(link)
                if COUNT >= 150:
                    print("Reached 100 products, stopping extraction.")
                    return extracted_data
                COUNT += 1
                try:
                    data = get_product_details(driver, link)
                    extracted_data.append(data)
                except Exception as exc:
                    print(f"Failed to scrape {link}: {exc}")
            try:
                next_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.next.page-numbers"))
                )
                driver.execute_script("arguments[0].click();", next_btn)
            except TimeoutException:
                break
        except Exception as exc:
            print(f"Error: {exc}")
            break

    return extracted_data


def format_data_for_sheet(data):
    formatted = []

    for item in data:
        row = {
            "Website Name": "cuesale.com",
            "Product URL": item["product_url"],
            "Product Category": item["category"],
            "Title": item["title"],
            "Quantity": item["quantity"],
            "Ex VAT Price": clean_price(item["ex_vat_price"]),
            "Inc VAT Price": clean_price(item["inc_vat_price"]),
            "Currency": "EUR",
            "Brand": item["brand"],
            "Condition": item["condition"],
            "Product Description": item["description"],
        }

        images = item.get("image", [])
        for index in range(1, 8):
            row[f"Image Src {index}"] = images[index - 1] if index - 1 < len(images) else "N/A"
            row[f"Image Position {index}"] = index

        formatted.append(row)

    df = pd.DataFrame(formatted)
    df = df.replace(r"(?i)\bN/A\b", "", regex=True)
    return df


def scrape():
    driver = init_driver()
    try:
        driver.get(COLLECTION_URL)
        data = extracting_detail(driver)
        df = format_data_for_sheet(data)
        if not df.empty:
            upload_to_google_sheets(sheet_name="cuesale", dataset=df)
        else:
            print("No data to upload.")
    finally:
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    scrape()
