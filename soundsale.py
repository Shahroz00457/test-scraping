from random import random
import time
from selenium.webdriver.common.by import By
# from utils.browser import get_driver
# from utils.sheets import upload_to_google_sheets
# from utils.helper import clean_price

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import pandas as pd

from dotenv import load_dotenv
import os
from utils.util import clean_price, upload_to_google_sheets

# Load environment variables
# load_dotenv()

# SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
# CRED_JSON = os.getenv("GOOGLE_SHEETS_CRED_JSON")



extracted_data = []


def get_product_links(driver):
    time.sleep(3)
    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='product/']")
    product_link = []
    for link in links:
        try:
            url = link.get_attribute("href")
            if url and "cookieyes.com" not in url and url not in product_link:
                product_link.append(url)
        except:
            continue 
    return product_link


def get_product_details(driver, product_link):
    driver.execute_script(f"window.open('{product_link}', '_blank');")
    WebDriverWait(driver, 7).until(lambda d: len(d.window_handles) > 1)
    driver.switch_to.window(driver.window_handles[-1])

    try:
        title = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product_title"))
        ).text
    except:
        title = "N/A"

    try:
        product_ex_price = driver.find_element(By.CSS_SELECTOR, "p.price ins span.woocommerce-Price-amount").text.strip("€")
    except:
        try:
            product_ex_price = driver.find_element(By.CSS_SELECTOR, "p.price span.woocommerce-Price-amount").text.strip("€")
        except:
            product_ex_price = "N/A"

    try:
        quantity = driver.find_element(By.CSS_SELECTOR, "p.stock.in-stock").text.strip("in stock")
    except:
        quantity = "N/A"
                
    try:
        brand, category = "N/A", "N/A"

        try:
            desc_el = driver.find_element(By.ID, "elementor-tab-content-8381")
        except:
            desc_el = driver.find_element(By.ID, "elementor-tab-content-1191")
        driver.execute_script("arguments[0].style.display='block';", desc_el)
        desc = desc_el.text.strip() if desc_el.text.strip() else "N/A"

        try:
            detail_el = driver.find_element(By.ID, "elementor-tab-content-8383")
        except:
            detail_el = driver.find_element(By.ID, "elementor-tab-content-1193")
        driver.execute_script("arguments[0].style.display='block';", detail_el)
        detail = detail_el.text.strip() if detail_el.text.strip() else "N/A"

        try:
            included_el = driver.find_element(By.ID, "elementor-tab-content-8382")
        except:
            included_el = driver.find_element(By.ID, "elementor-tab-content-1192")
        driver.execute_script("arguments[0].style.display='block';", included_el)
        included = included_el.text.strip() if included_el.text.strip() else "N/A"

        try:
            brand = driver.find_element(By.CSS_SELECTOR,"tr.woocommerce-product-attributes-item--attribute_pa_brand td").text.strip()

            category = driver.find_element(By.CSS_SELECTOR,"tr.woocommerce-product-attributes-item--attribute_pa_product-category td").text.strip()
        except:
            pass

        description = (
            "PRODUCT DESCRIPTION\n" + desc + "\n\n"
            "WHAT'S INCLUDED?\n" + included + "\n\n"
            "PRODUCT DETAILS\n" + detail
        )

    except:
        description = "N/A"


    try:
        image_elements = driver.find_elements(By.CSS_SELECTOR, ".woocommerce-product-gallery__image a")
        image_src = []
        for img in image_elements:
            href = img.get_attribute("href")
            if href and href not in image_src:
                image_src.append(href)
    except:
        image_src = "N/A"



    product_data = {
        "product_url": product_link,
        "title": title,
        "quantity": quantity,
        "category": category,
        "subcategory": "N/A",
        "ex_vat_price": product_ex_price,
        "inc_vat_price": "N/A",
        "brand": brand,
        "condition": "N/A",
        "description": description,
        "image": image_src
    }

    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return product_data


def extracting_detail(driver):
    product = driver.find_element(By.CSS_SELECTOR, "a[href*='shop']").get_attribute("href")
    driver.get(product)
    while True:
        product_links = get_product_links(driver)
        # print(f"Found {len(product_links)} pa-audio.eu products on this page.")
        for link in product_links:
            data = get_product_details(driver, link)
            extracted_data.append(data)

        try:
            next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.next.page-numbers"))
            )
            driver.execute_script("arguments[0].click();", next_btn)
        except:
            break

def format_data_for_sheet(data):
    formatted_data = []
    for item in data:
        row = {
            "Website Name": "soundsale.nl",
            "Product URL": item.get("product_url", ""),
            "Product Category": item.get("category", ""),
            "Title": item.get("title", ""),
            "Quantity": item.get("quantity", ""),
            "Ex VAT Price": clean_price(item.get("ex_vat_price", "")),
            "Inc VAT Price": clean_price( item.get("inc_vat_price", "")),
            "Currency": "EUR",
            "Brand": item.get("brand", ""),
            "Condition": item.get("condition", ""),
            "Product Description": item.get("description", "")
        }

        images = item.get("image", [])
        if not isinstance(images , list):
            images = []
        for i in range(1, 8):
            row[f"Image Src {i}"] = images[i-1] if i-1 < len(images) else "N/A"
            row[f"Image Position {i}"] = i
        formatted_data.append(row)
    df = pd.DataFrame(formatted_data)
    df = df.replace(r'(?i)\bN/A\b', '', regex=True)
    return df


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
    
    driver.get('https://soundsale.nl/')
    time.sleep(4)
    extracting_detail(driver)
    df = format_data_for_sheet(extracted_data)
    try:
        upload_to_google_sheets(sheet_name="soundsale.nl", dataset=df)
    except Exception as e:
        print("Error while uploading to Google Sheets:", e)

    driver.quit()

if __name__ == "__main__":
    scrape()
