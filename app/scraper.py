import re
import time
import random
import logging
import requests
from types import SimpleNamespace
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from app.database import SessionLocal
from app.models import Product, PriceHistory, ProductListing, ListingPrice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

DELAY_BETWEEN_REQUESTS = 2

SITE_SELECTORS = {
    "amazon.": [
        "span.a-price span.a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
    ],
    "ebay.": [
        "div.x-price-primary span.ux-textspans",
        "span#prcIsum",
    ],
    "walmart.": [
        "span[itemprop='price']",
        "span.price-characteristic",
    ],
    "target.com": [
        "span[data-test='product-price']",
    ],
    "bestbuy.com": [
        "div.priceView-hero-price span",
    ],
}

PRICE_PATTERN = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")


def get_random_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}


def parse_price_text(text):
    if not text:
        return None
    match = PRICE_PATTERN.search(text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def extract_steam_appid(url):
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
        logger.warning(f"no price_overview for app {app_id} (likely free-to-play)")
        return None

    return price_overview["final"] / 100


def get_selectors_for_url(url):
    for domain_fragment, selectors in SITE_SELECTORS.items():
        if domain_fragment in url:
            return selectors
    return None


def scrape_with_playwright(url):
    selectors = get_selectors_for_url(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = context.new_page()

        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            if selectors:
                for selector in selectors:
                    try:
                        el = page.query_selector(selector)
                        if el:
                            price = parse_price_text(el.inner_text())
                            if price is not None:
                                return price
                    except Exception:
                        continue

            body_text = page.inner_text("body")
            price = parse_price_text(body_text)
            if price is not None:
                return price

            logger.warning(f"playwright couldn't find a price on {url}")
            return None
        finally:
            browser.close()


def scrape_generic_price(url):
    try:
        resp = requests.get(url, headers=get_random_headers(), timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        price = parse_price_text(soup.get_text())
        if price is not None:
            return price
    except Exception as e:
        logger.info(f"static fetch failed ({e}), will try rendered browser instead")

    return scrape_with_playwright(url)


def scrape_url_price(url):
    if "steampowered.com" in url:
        return scrape_steam_price(url)
    else:
        return scrape_generic_price(url)


def scrape_url_with_retry(url, label, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            price = scrape_url_price(url)
            if price is not None:
                return price
            logger.warning(f"attempt {attempt} for {label}: no price found")
        except Exception as e:
            logger.error(f"attempt {attempt} for {label} failed: {e}")

        if attempt < max_attempts:
            wait = 2 ** attempt
            time.sleep(wait)

    logger.error(f"giving up on {label} after {max_attempts} attempts")
    return None


def scrape_all_products():
    db = SessionLocal()
    products = db.query(Product).all()

    success_count = 0
    fail_count = 0

    for product in products:
        listings = db.query(ProductListing).filter(ProductListing.product_id == product.id).all()

        if not listings:
            listings = [SimpleNamespace(id=None, url=product.url, source=product.source)]

        found_prices = []

        for listing in listings:
            label = f"{product.name} ({listing.source or 'listing'})"
            logger.info(f"scraping {label}...")
            price = scrape_url_with_retry(listing.url, label)

            if price is not None:
                found_prices.append(price)
                logger.info(f"{label}: ${price}")
                if listing.id is not None:
                    db.add(ListingPrice(listing_id=listing.id, price=price))
                    db.commit()
            else:
                logger.error(f"skipping {label}, scrape failed")

            time.sleep(DELAY_BETWEEN_REQUESTS)

        if found_prices:
            best_price = min(found_prices)
            db.add(PriceHistory(product_id=product.id, price=best_price))
            db.commit()
            logger.info(f"{product.name}: best price found ${best_price}")
            success_count += 1
        else:
            fail_count += 1

    db.close()
    return success_count, fail_count


if __name__ == "__main__":
    scrape_all_products()