import re
import pandas as pd
from pathlib import Path


def clean_price(price_str):
    price_str = price_str.replace(" ", "")
    if not price_str or price_str=="" or price_str==" " or price_str=="N/A":
        return "POA"

    try:
        if float(price_str) == 0:
            return "POA"
    except:
        pass

    if price_str.isalpha():
        return "POA"

    price_str = re.sub(r"[^\d.,]", "", price_str)

    if len(price_str) >= 3 and price_str[-3] in [".", ","] and price_str[-2:].isdigit():
        price_str = price_str.replace(",", ".")
        price_list = price_str.split(".")
        if len(price_list[-1]) == 2:
            price_list.insert(-1,".")
            string_price = "".join(price_list)

        return string_price
    else:
        return price_str.replace(",","").replace(".","")+".00"
    


def upload_to_google_sheets(sheet_name: str, dataset: pd.DataFrame, csv_folder: str = "csv") -> Path:
    folder = Path(csv_folder)
    folder.mkdir(parents=True, exist_ok=True)

    filepath = folder / f"{sheet_name}.csv"
    dataset.to_csv(filepath, index=False, encoding="utf-8-sig")

    return filepath