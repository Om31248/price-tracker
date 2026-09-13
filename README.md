# Price Tracker

Tracks prices for products you care about across multiple sellers, and tells you when they drop.

## What it does

- Add any product with a URL and a target price
- Track the same product across multiple sellers (Amazon, Walmart, eBay, Target, Best Buy, Steam, and so on) and it keeps the lowest price found
- Scrapes prices on a schedule automatically
- Logs price history over time
- Shows you the biggest price drops from the last 7 days
- Dashboard with charts, estimated savings, and a manual "scrape now" button

## Tech stack

Python, SQLAlchemy, Streamlit, Plotly, pandas

## How it works

1. A background scheduler runs on an interval (6 hours by default) and scrapes every tracked product's current price
2. Each price check gets logged to a database so you can see trends over time
3. If a product has multiple listings across different sellers, the dashboard shows the lowest one
4. The Streamlit dashboard reads straight from the database: current stats, price history charts, and a table of the week's biggest drops
5. You can add new products or additional sellers for existing products directly from the dashboard, no need to touch the code

## Running it locally

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project folder. At minimum:
```
DB_PATH=prices.db
SCRAPE_INTERVAL_HOURS=6
```

Start the background scraper (runs continuously, checks prices on the interval above):
```bash
python main.py
```

In a separate terminal, start the dashboard:
```bash
streamlit run streamlit_app.py
```

## Notes

- Deleting a product also removes its price history and any additional seller listings for it
