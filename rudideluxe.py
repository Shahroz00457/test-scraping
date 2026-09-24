import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# from utils.browser import get_driver
# from utils.sheets import upload_to_google_sheets
# from utils.helper import clean_price
from utils.util import upload_to_google_sheets, clean_price
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv
import os

# Load env vars
load_dotenv()

SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
CRED_JSON = os.getenv("GOOGLE_SHEETS_CRED_JSON")

extracted_data = []


def get_products(driver):
    results = []
    nav = driver.find_elements(By.CSS_SELECTOR, "nav.elementor-nav-menu--main ul li")

    for li in nav:
        try:
            a = li.find_element(By.TAG_NAME, "a")
            href = a.get_attribute("href")
            if href and href not in results:
                results.append(href)
        except:
            continue

    for url in [
        "https://rudideluxe.de/product-category/shop/offers/",
        "https://rudideluxe.de/product-category/shop/deals/",
        "https://rudideluxe.de/"
    ]:
        if url in results:
            results.remove(url)
    print(results)
    return results


def get_product_links(driver):
    product_page = driver.find_elements(By.CSS_SELECTOR, "a[href*='/produkt/']")
    product_links = []

    for link in product_page:
        url = link.get_attribute("href")
        if url and url not in product_links:
            product_links.append(url)

    return product_links


def get_product_details(driver, product_link):
    driver.execute_script(f"window.open('{product_link}', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])

    try:
        title = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.elementor-widget-woocommerce-product-title")
            )
        ).text
    except:
        title = "N/A"

    try:
        try:
            price_text = driver.find_element(
                By.CSS_SELECTOR, "p.price ins .woocommerce-Price-amount"
            ).text
        except:
            price_text = driver.find_element(By.CSS_SELECTOR, "p.price").text

        if "VB" in price_text.upper():
            product_ex_price = "N/A"
        else:
            product_ex_price = price_text
    except:
        product_ex_price = "N/A"

    try:
        quantity = driver.find_element(By.CSS_SELECTOR, "p.in-stock").text
        quantity = quantity.replace("vorrätig", "").strip()
    except:
        quantity = "N/A"

    try:
        description = driver.find_element(By.ID, "tab-description").text
    except:
        description = "N/A"

    try:
        image_elements = driver.find_elements(By.CSS_SELECTOR, ".woocommerce-product-gallery__image a")
        images = []
        for img in image_elements:
            href = img.get_attribute("href")
            if href and href not in images:
                images.append(href)
    except:
        images = "N/A"

    try:
        breadcrumbs = driver.find_elements(
            By.CSS_SELECTOR, "nav.product-category-breadcrumb a"
        )
        texts = [b.text.strip() for b in breadcrumbs if b.text.strip()]

        category = texts[0] if len(texts) > 0 else "N/A"
        subcategory = texts[1] if len(texts) > 1 else "N/A"
    except:
        category = "N/A"
        subcategory = "N/A"

    product_data = {
        "product_url": product_link,
        "title": title,
        "quantity": quantity,
        "category": category,
        "subcategory": subcategory,
        "ex_vat_price": clean_price(product_ex_price),
        "inc_vat_price": "N/A",
        "brand": "N/A",
        "condition": "N/A",
        "description": description,
        "image": images
    }
    
    print(product_data , "aaa")
    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    return product_data


def extracting_detail(driver):
    categories = get_products(driver)
    # print("Links to fetch:", categories)

    for url in categories:
        driver.get(url)
        product_links = get_product_links(driver)

        for link in product_links:
            data = get_product_details(driver, link)
            if data:
                extracted_data.append(data)


def format_data_for_sheet(data):
    rows = []

    for item in data:
        row = {
            "Website Name": "rudideluxe.de",
            "Product URL": item["product_url"],
            "Product Category": item["category"],
            "Title": item["title"],
            "Quantity": item["quantity"],
            "Ex VAT Price": clean_price(item["ex_vat_price"]),
            "Inc VAT Price": clean_price(item["inc_vat_price"]),
            "Currency": "EUR",
            "Brand": item["brand"],
            "Condition": item["condition"],
            "Product Description": item["description"]
        }

        images = item.get("image", [])
        for i in range(1, 8):
            row[f"Image Src {i}"] = images[i-1] if i-1 < len(images) else ""

        rows.append(row)

    return pd.DataFrame(rows)


def scrape():
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors=yes")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])  

    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://rudideluxe.de/")
    time.sleep(3)

    extracting_detail(driver)

    df = format_data_for_sheet(extracted_data)

    try:
        upload_to_google_sheets(sheet_name="rudideluxe.de", dataset=df)
        print("Data uploaded to Google Sheets")
    except Exception as e:
        print("Upload failed:", e)

    driver.quit()


if __name__ == "__main__":
    scrape()
