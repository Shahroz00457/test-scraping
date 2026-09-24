from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.util import clean_price, upload_to_google_sheets
import time
import pandas as pd
import random
from dotenv import load_dotenv
import os
import re

load_dotenv()
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
CRED_JSON = os.getenv("GOOGLE_SHEETS_CRED_JSON")

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0',
]

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    chrome_prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
        "profile.managed_default_content_settings.media_stream": 2
    }
    chrome_options.add_experimental_option("prefs", chrome_prefs)

    driver = webdriver.Chrome(options=chrome_options)
    return driver

extracted_data = []

def get_products(driver):
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/label"))).click()
    except:
        pass
    try:
        modal_close_button_2 = driver.find_element(By.XPATH, "/html/body/main/div/div/div[1]/div/div/div/div[1]/div/label")
        if modal_close_button_2.is_displayed():
            modal_close_button_2.click()
    except:
        pass
    elem = driver.find_element(By.XPATH, "/html/body/main/header/nav/div/div[2]/div/ul/li[2]")
    elem.click()
    time.sleep(3)

def get_product_links(driver):
    WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/product-detail-page/']")))
    product_page = driver.find_elements(By.CSS_SELECTOR, "a[href*='/product-detail-page/']")
    product_links = list({link.get_attribute("href") for link in product_page if link.get_attribute("href")})
    return product_links

def get_product_details(driver, product_link):
    time.sleep(random.uniform(1, 3))
    driver.execute_script(f"window.open('{product_link}', '_blank');")
    time.sleep(2.5)
    driver.switch_to.window(driver.window_handles[-1])

    def safe_text_flexible(selectors):
        """Multiple selectors try karta hai"""
        for selector_type, selector in selectors:
            try:
                if selector_type == "xpath":
                    element = driver.find_element(By.XPATH, selector)
                elif selector_type == "css":
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                elif selector_type == "class":
                    element = driver.find_element(By.CLASS_NAME, selector)
                
                if element and element.text.strip():
                    return element.text.strip()
            except:
                continue
        return "N/A"

    # Title extraction - Multiple selectors
    title_selectors = [
        ("css", "h1.u-no-margin"),
        ("css", "h1.product__title"),
        ("css", "h1"),
        ("xpath", "//h1[@class='u-no-margin']")
    ]
    title = safe_text_flexible(title_selectors)

    try:
        ex_vat_price = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product__price-wrap.dw-mod div.price.price--product-page.dw-mod"))).text
        ex_price = ex_vat_price.split()
        ex_price.pop(0)
        product_ex_price = str(ex_price[0])
        product_ex_price = clean_price(product_ex_price)
    except Exception:
        product_ex_price = "N/A"

    try:
        inc_vat_price = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product__price-wrap.dw-mod div.vat-price.vat-price--product-page"))).text
        product_inc = inc_vat_price.replace("(", "").replace(")", "")
        product_inc_price = clean_price(product_inc)
    except Exception:
        product_inc_price = "N/A"

    # Brand extraction
    brand_selectors = [
        ("xpath", "//th[contains(text(), 'Brand')]/following-sibling::td"),
        ("css", "table tr:has(th:contains('Brand')) td"),
        ("xpath", "//table//tr[.//th[text()='Brand']]//td")
    ]
    brand = safe_text_flexible(brand_selectors)

    # Condition - Using the custom sticker
    # condition_selectors = [
    #     ("css", "div.stickers-container__tag--custom"),
    #     ("xpath", "//div[contains(@class, 'stickers-container__tag--custom')]")
    # ]
    # condition = safe_text_flexible(condition_selectors)

    try:
        condition = driver.find_element(By.CSS_SELECTOR, "div div.js-variants").text
    except:
        condition = "N/A"

    # Description
    description_selectors = [
        ("css", "div.introduction-text"),
        ("css", "div.introduction-text p"),
        ("xpath", "//div[@class='introduction-text']")
    ]
    description = safe_text_flexible(description_selectors)

    # Item Number extraction
    item_number_selectors = [
        ("css", "div.item-number"),
        ("xpath", "//div[contains(@class, 'item-number')]")
    ]
    item_number = safe_text_flexible(item_number_selectors)

    # Availability extraction
    availability_selectors = [
        ("xpath", "//th[contains(text(), 'Availability')]/following-sibling::td"),
        ("css", "table tr:has(th:contains('Availability')) td")
    ]
    availability = safe_text_flexible(availability_selectors)

    # Images extraction
    try:
        # Main product image
        main_img = driver.find_element(By.CSS_SELECTOR, "img.product__image-container__image")
        main_img_src = main_img.get_attribute("src")
        
        # Gallery images
        gallery_imgs = driver.find_elements(By.CSS_SELECTOR, "img.modal--full__img")
        gallery_img_srcs = [img.get_attribute("data-src") for img in gallery_imgs if img.get_attribute("data-src")]
        
        # Thumbnail images
        thumb_imgs = driver.find_elements(By.CSS_SELECTOR, "img.thumb-list__image")
        thumb_img_srcs = [img.get_attribute("src") for img in thumb_imgs if img.get_attribute("src")]
        
        # Combine all unique images
        all_images = [main_img_src] + gallery_img_srcs + thumb_img_srcs
        all_images = list(dict.fromkeys(all_images))  # Remove duplicates
        
        images = {f"image{i+1}": f"https://secondhand.aedgroup.com{img}" if img and img.startswith("/") else img 
                 for i, img in enumerate(all_images) if img and i < 7}  # Max 7 images
    except Exception as e:
        print(f"Error extracting images: {e}")
        images = {}

    product_data = {
        "product_url": product_link,
        "title": title,
        "ex_vat_price": product_ex_price,
        "inc_vat_price": product_inc_price,
        "brand": brand,
        "condition": condition,
        "description": description,
        "item_number": item_number,
        "availability": availability,
        **images
    }

    # print("1111111111111111111",product_data)

    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return product_data


def extracting_detail(driver):
    get_products(driver)

    try:
        cookie_modal = driver.find_element(By.XPATH, "/html/body/div[2]/div/label")
        cookie_modal.click()
    except:
        pass

    scraped_urls = set()

    while True:
        time.sleep(3)
        all_links = get_product_links(driver)
        new_links = [link for link in all_links if link not in scraped_urls]

        if not new_links:
            print("No new links found. Exiting.")
            break

        # print(f"Found {len(new_links)} new products to scrape.")

        for link in new_links:
            try:
                data = get_product_details(driver, link)
                if data and data.get("title") != "N/A":
                    extracted_data.append(data)
                    scraped_urls.add(link)
                    # print(f"Successfully scraped: {link}")
                else:
                    print(f"Failed to get valid data for: {link}")
            except Exception as e:
                print(f"Error scraping {link}: {e}")

        try:
            next_page = driver.find_element(By.ID, "LoadMoreButton")
            next_page.click()
            print("Clicked 'Load More', waiting for next batch...")
            time.sleep(3)
        except:
            print("No more pages to load. Finished scraping.")
            break


def format_data_for_sheet(data):
    formatted_data = []
    for item in data:
        url = item.get("product_url", "")
        product_category = ""
        try:
            if "/shop/product-detail-page/" in url:
                category_part = url.split("/shop/product-detail-page/")[1]
                product_category = category_part.split("/")[0]  # First part is category
        except Exception:
            product_category = ""
        
        row = {
            "Website Name": "secondhand.aedgroup.com",
            "Product URL": url,
            "Product Category": product_category,
            "Title": item.get("title", ""),
            "Quantity": "N/A",  
            "Ex VAT Price": item.get("ex_vat_price", ""),
            "Inc VAT Price": item.get("inc_vat_price", ""),  
            "Currency": "EUR",
            "Brand": item.get("brand", ""),
            "Condition": item.get("condition", ""),
            "Product Description": item.get("description", ""),
        }
        
        for i in range(1, 8):
            img_key = f"image{i}"
            img = item.get(img_key, "")
            row[f"Image Src {i}"] = img if img else "N/A"
            row[f"Image Position {i}"] = i
            
        formatted_data.append(row)
    
    df = pd.DataFrame(formatted_data)
    df = df.replace(r'(?i)\bN/A\b', '', regex=True)
    return df

def scrape():
    driver = init_driver()
    try:
        driver.get('https://secondhand.aedgroup.com/home')
        # time.sleep(5)
        extracting_detail(driver)

        if extracted_data:
            df = format_data_for_sheet(extracted_data)
            if not df.empty:
                try:
                    upload_to_google_sheets(sheet_name="secondhand.aedgroup.com", dataset=df)
                except Exception as e:
                    print("Error uploading to Google Sheets:", e)
            else:
                print("No valid data to upload")
        else:
            print("No data scraped")

    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    scrape()
