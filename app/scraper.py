import re
import time
import random
import logging
import requests
from bs4 import BeautifulSoup

from database import SessionLocal
from models import Product, PriceHistory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# pretend to be a few different browsers so we don't get blocked 
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

DELAY_BETWEEN_REQUESTS = 2  


def get_random_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}


def extract_steam_appid(url):
    # steam urls look not cooked
    match = re.search(r"/app/(\d+)", url)
    if match:
        return match.group(1)
    return None


def scrape_steam_price(url):
    app_id = extract_steam_appid(url)
    if not app_id:
        logger.warning(f"couldn't find app id in url: {url}")
        return None

    api_url = "https://store.steampowered.com/api/appdetails"
    resp = requests.get(api_url, params={"appids": app_id, "cc": "us"}, headers=get_random_headers(), timeout=10)
    resp.raise_for_status()
    data = resp.json()

    app_data = data.get(app_id)
    if not app_data or not app_data.get("success"):
        logger.warning(f"steam api returned no data for app {app_id}")
        return None

    price_overview = app_data["data"].get("price_overview")
    if not price_overview:
        
        logger.warning(f"no price_overview for app {app_id}, might be free")
        return None

    return price_overview["final"] / 100  # steam gives price in cents


def scrape_generic_price(url):
  
    resp = requests.get(url, headers=get_random_headers(), timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    text = soup.get_text()
    match = re.search(r"\$\s?(\d+[.,]\d{2})", text)
    if match:
        return float(match.group(1).replace(",", ""))

    logger.warning(f"generic scraper couldn't find a price on {url}")
    return None


def scrape_price(product):
    if "steampowered.com" in product.url:
        return scrape_steam_price(product.url)
    else:
        return scrape_generic_price(product.url)


def scrape_with_retry(product, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            price = scrape_price(product)
            if price is not None:
                return price
            # got a response but no price found, still worth retrying
            logger.warning(f"attempt {attempt} for {product.name}: no price found")
        except Exception as e:
            logger.error(f"attempt {attempt} for {product.name} failed: {e}")

        if attempt < max_attempts:
            wait = 2 ** attempt  # 2, 4, 8...
            time.sleep(wait)

    logger.error(f"giving up on {product.name} after {max_attempts} attempts")
    return None


def scrape_all_products():
    db = SessionLocal()
    products = db.query(Product).all()

    success_count = 0
    fail_count = 0

    for product in products:
        logger.info(f"scraping {product.name}...")
        price = scrape_with_retry(product)

        if price is not None:
            entry = PriceHistory(product_id=product.id, price=price)
            db.add(entry)
            db.commit()
            logger.info(f"{product.name}: ${price}")
            success_count += 1
        else:
            logger.error(f"skipping {product.name}, scrape failed")
            fail_count += 1

        time.sleep(DELAY_BETWEEN_REQUESTS)

    db.close()
    return success_count, fail_count


if __name__ == "__main__":
    scrape_all_products()