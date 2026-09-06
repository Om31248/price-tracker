import pandas as pd

from app.database import SessionLocal
from app.models import Product, PriceHistory


def _load_history_df(product_id=None):
    db = SessionLocal()

    query = db.query(PriceHistory)
    if product_id is not None:
        query = query.filter(PriceHistory.product_id == product_id)

    rows = query.all()
    db.close()

    data = [{"product_id": r.product_id, "price": r.price, "timestamp": r.timestamp} for r in rows]
    df = pd.DataFrame(data)

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    return df


def get_price_trend(product_id):
    df = _load_history_df(product_id)
    if df.empty:
        return pd.DataFrame(columns=["date", "avg_price"])

    df["date"] = df["timestamp"].dt.date
    trend = df.groupby("date")["price"].mean().reset_index()
    trend.columns = ["date", "avg_price"]
    return trend


def get_biggest_drops(days=7):
    db = SessionLocal()
    products = db.query(Product).all()
    db.close()

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)

    results = []

    for product in products:
        df = _load_history_df(product.id)
        if df.empty:
            continue

        recent = df[df["timestamp"] >= cutoff]
        if recent.empty:
            continue

        first_price = recent.sort_values("timestamp").iloc[0]["price"]
        last_price = recent.sort_values("timestamp").iloc[-1]["price"]

        if first_price == 0:
            continue

        pct_drop = (first_price - last_price) / first_price * 100

        results.append({
            "product_id": product.id,
            "name": product.name,
            "first_price": first_price,
            "last_price": last_price,
            "pct_drop": pct_drop,
        })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        return result_df

    return result_df.sort_values("pct_drop", ascending=False).reset_index(drop=True)


def get_volatility(product_id):
    df = _load_history_df(product_id)
    if df.empty or len(df) < 2:
        return 0.0

    return df["price"].std()


def summary_stats():
    db = SessionLocal()
    products = db.query(Product).all()
    total_products = len(products)
    total_checks = db.query(PriceHistory).count()
    db.close()

    total_drops = 0
    total_savings = 0.0

    for product in products:
        df = _load_history_df(product.id)
        if df.empty or len(df) < 2:
            continue

        df = df.sort_values("timestamp")
        first_price = df.iloc[0]["price"]
        lowest_price = df["price"].min()

        if lowest_price < first_price:
            total_drops += 1
            total_savings += (first_price - lowest_price)

    return {
        "total_products": total_products,
        "total_checks": total_checks,
        "total_drops": total_drops,
        "estimated_savings": round(total_savings, 2),
    }


if __name__ == "__main__":
    print(summary_stats())