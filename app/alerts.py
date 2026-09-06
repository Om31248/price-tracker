import logging
import smtplib
from email.mime.text import MIMEText

import requests

from app.database import SessionLocal
from app.models import Product, PriceHistory
import config

logger = logging.getLogger(__name__)


def send_discord_alert(product, price):
    if not config.DISCORD_WEBHOOK_URL:
        logger.info("no discord webhook set, skipping")
        return

    msg = f"🔥 **{product.name}** dropped to ${price} (target: ${product.target_price})\n{product.url}"

    try:
        resp = requests.post(config.DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=10)
        resp.raise_for_status()
        logger.info(f"discord alert sent for {product.name}")
    except Exception as e:
        logger.error(f"failed to send discord alert for {product.name}: {e}")


def send_email_alert(product, price):
    if not getattr(config, "EMAIL_ENABLED", False):
        return

    subject = f"Price drop: {product.name}"
    body = f"{product.name} is now ${price} (target was ${product.target_price})\n\n{product.url}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = config.EMAIL_TO

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"email alert sent for {product.name}")
    except Exception as e:
        logger.error(f"failed to send email alert for {product.name}: {e}")


def check_alerts():
    db = SessionLocal()
    products = db.query(Product).all()

    alert_count = 0

    for product in products:
        latest = (
            db.query(PriceHistory)
            .filter(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.timestamp.desc())
            .first()
        )

        if latest is None:
            continue

        if product.target_price is None:
            continue

        if latest.price <= product.target_price:
            logger.info(f"{product.name} hit target price, sending alerts")
            send_discord_alert(product, latest.price)
            send_email_alert(product, latest.price)
            alert_count += 1

    db.close()
    return alert_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = check_alerts()
    print(f"sent {n} alerts")