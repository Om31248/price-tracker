import time
import logging

from app.database import init_db
from app.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("setting up db...")
    init_db()

    scheduler = start_scheduler()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()