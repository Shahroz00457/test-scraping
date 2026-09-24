
from selenium.webdriver.common.by import By
import time
from utils.util import clean_price, upload_to_google_sheets
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import pandas as pd

from dotenv import load_dotenv
import os

load_dotenv()

SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
CRED_JSON = os.getenv("GOOGLE_SHEETS_CRED_JSON")



extracted_data = []
visited_products = set() 

def get_products(driver):
    menu_items = driver.find_elements(By.CSS_SELECTOR, "nav.elementor-nav-menu--main > ul > li")
    selected_items = menu_items[1:4:2]
    results = []
    exclude_links = [
        "https://www.soundwall.info/gebrauchte-produkte/",
        "https://www.soundwall.info/gebrauchte-produkte/audio/ton-anlagen/",
        "https://www.soundwall.info/gebrauchte-produkte/audio/mischpulte/",
        "https://www.soundwall.info/gebrauchte-produkte/audio/mikrofone/",
        "https://www.soundwall.info/gebrauchte-produkte/audio/sonstiges/",
        "https://www.soundwall.info/shop-small-stuff/shop-ton/",  
        "https://www.soundwall.info/shop-small-stuff/shop-licht/",
        "https://www.soundwall.info/shop-small-stuff/shop-cases/"
    ]
    for li in selected_items:
        a = li.find_element(By.TAG_NAME, "a")
        href = a.get_attribute("href")
        if href not in exclude_links:
            results.append(href)
        try:
            sub_links = li.find_elements(By.CSS_SELECTOR, "ul.sub-menu a")
            for s in sub_links:
                sub_href = s.get_attribute("href")
                if sub_href not in exclude_links:
                    results.append(sub_href)
        except:
            pass
    return results


def get_product_links(driver):
    product_page = driver.find_elements(By.CSS_SELECTOR, "div.uael-woo-products-thumbnail-wrap a[href*='/produkt/']")
    product_link = []
    for link in product_page:
        url = link.get_attribute("href")
        if url and url not in product_link:
            product_link.append(url)
    return product_link


def get_product_details(driver , product_link):
    if product_link in visited_products:
        return None
    visited_products.add(product_link)

    driver.execute_script(f"window.open('{product_link}', '_blank');")
    time.sleep(5)
    driver.switch_to.window(driver.window_handles[-1])  

    try:
        title = driver.find_element(By.CSS_SELECTOR, "div.elementor-widget-woocommerce-product-title").text
        parts = title.split()
        brand = parts[2] if len(parts) >= 3 else "N/A"
    except:
        title, brand = "N/A", "N/A"
        
    try:
        product_ex_price = driver.find_element(By.CSS_SELECTOR, "p.price").text
        product_ex_price = product_ex_price.replace("€", "").replace("exkl. MwSt.", "").strip()
        product_ex_price = product_ex_price.replace(".", "").replace(",", ".")
    except:
        product_ex_price = None

    try:
        description_div = driver.find_element(By.ID, "tab-description")
        elements = description_div.find_elements(By.TAG_NAME, "li")
        if not elements:
            elements = description_div.find_elements(By.TAG_NAME, "p")
        if elements:
            condition = elements[0].text.strip()
            for sep in [",", "–", "-"]:
                if sep in condition:
                    condition = condition.split(sep)[-1].strip()
                    break
        else:
            condition = "N/A"
    except:
        condition = "N/A"

    try:
        list_items = driver.find_elements(By.CSS_SELECTOR, "#tab-description li")
        quantity = "N/A"
        for li in list_items:
            text = li.text.strip()
            if "available" in text.lower() or "pieces" in text.lower():
                for word in text.split():
                    if word.isdigit():
                        quantity = word
                        break
            if quantity != "N/A":
                break
    except:
        quantity = "N/A"

    try:
        description = driver.find_element(By.ID, "tab-description").text
    except:
        description = "N/A"
        
    try:
        links = driver.find_elements(By.CSS_SELECTOR, ".elementor-image-carousel .swiper-slide:not(.swiper-slide-duplicate) a")
        image_src = [a.get_attribute('href') for a in links]
    except:
        image_src = "N/A"

    try:
        breadcrumbs = driver.find_elements(By.CSS_SELECTOR, "span.posted_in.detail-container span.detail-content a")
        breadcrumb_texts = [b.text.strip() for b in breadcrumbs if b.text.strip()]
        
        if len(breadcrumb_texts) >= 3:
            category = breadcrumb_texts[0]
            subcategory = breadcrumb_texts[2]
        elif len(breadcrumb_texts) == 2:
            category = breadcrumb_texts[0]
            subcategory = breadcrumb_texts[1]
        elif len(breadcrumb_texts) == 1:
            category = breadcrumb_texts[0]
            subcategory = "N/A"
        else:
            category = "N/A"
            subcategory = "N/A"
            
    except Exception as e:
        print(f"Error extracting breadcrumbs: {e}")
        category, subcategory = "N/A", "N/A"

    product_data = {
        "product_url" : product_link,
        "title" : title,
        "quantity": quantity,
        "category": category,
        "subcategory": subcategory,
        "ex_vat_price" : product_ex_price,
        "inc_vat_price" : "N/A",
        "brand" : brand,
        "condition" : condition,
        "description" : description,
        "image" : image_src
    }

    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return product_data


def extracting_detail(driver):
    results = get_products(driver)  
    for url in results:
        try:
            driver.get(url)
            time.sleep(4)  

            product_links = get_product_links(driver)  
            print(f"Found {len(product_links)} soundwall products on this page.")

            for link in product_links:
                try:
                    data = get_product_details(driver, link)
                    if data:
                        extracted_data.append(data)
                except Exception as e:
                    print(f"Error scraping product {link}: {e}")

            time.sleep(3) 

        except Exception as e:
            print(f"Error loading page {url}: {e}")


def format_data_for_sheet(data):
    formatted_data = []
    for item in data:
        row = {
            "Website Name": "soundwall.info",
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
    driver.get("https://www.soundwall.info")
    time.sleep(4)
    extracting_detail(driver)
    df = format_data_for_sheet(extracted_data)
    try:
        upload_to_google_sheets(sheet_name="soundwall", dataset=df)
    except Exception as e:
        print("Error while uploading in sheet fileS", str(e))
    

    driver.quit()

if __name__ == "__main__":
    scrape()


