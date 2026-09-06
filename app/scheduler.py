import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from app.scraper import scrape_all_products
from config import SCRAPE_INTERVAL_HOURS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_scrape_job():
    start = datetime.now()
    logger.info(f"scrape job started at {start}")

    success, failed = scrape_all_products()

    end = datetime.now()
    logger.info(f"scrape job finished at {end} (took {end - start})")
    logger.info(f"results: {success} succeeded, {failed} failed")


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scrape_job, "interval", hours=SCRAPE_INTERVAL_HOURS)
    scheduler.start()
    logger.info(f"scheduler started, running every {SCRAPE_INTERVAL_HOURS}h")
    return scheduler