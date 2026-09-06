import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import plotly.express as px

from app.database import SessionLocal
from app.models import Product, PriceHistory, ProductListing
from app.analysis import get_price_trend, get_biggest_drops, summary_stats
from app.scraper import scrape_all_products

st.set_page_config(page_title="Price Tracker", page_icon="📉", layout="wide")

st.title("📉 Price Tracker Dashboard")

stats = summary_stats()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Products Tracked", stats["total_products"])
col2.metric("Price Checks Logged", stats["total_checks"])
col3.metric("Drops Detected", stats["total_drops"])
col4.metric("Estimated Savings", f"${stats['estimated_savings']}")

if st.button("🔄 Scrape Now"):
    with st.spinner("Scraping all tracked products..."):
        success, fail = scrape_all_products()
    st.success(f"Done — {success} succeeded, {fail} failed.")
    st.rerun()

st.divider()

st.subheader("Add a Product to Track")

with st.form("add_product_form", clear_on_submit=True):
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        new_name = st.text_input("Product name", placeholder="e.g. Counter-Strike 2")
        new_url = st.text_input("Product URL", placeholder="https://store.steampowered.com/app/...")
    with fcol2:
        new_source = st.selectbox("Source", ["steam", "other"])
        new_target = st.number_input("Target price ($)", min_value=0.0, step=1.0)

    submitted = st.form_submit_button("Add Product")

    if submitted:
        if not new_name or not new_url:
            st.error("Name and URL are required.")
        else:
            db = SessionLocal()
            db.add(Product(name=new_name, url=new_url, source=new_source, target_price=new_target))
            db.commit()
            db.close()
            st.success(f"Added {new_name}! It'll get picked up on the next scrape cycle.")
            st.rerun()

st.divider()

st.subheader("Add Another Seller for an Existing Product")
st.caption("Track the same item across multiple sites — the dashboard will keep the lowest price found.")

db = SessionLocal()
all_products = db.query(Product).all()
db.close()

if all_products:
    with st.form("add_listing_form", clear_on_submit=True):
        lcol1, lcol2, lcol3 = st.columns(3)
        with lcol1:
            listing_product_name = st.selectbox(
                "Which product?", [p.name for p in all_products], key="listing_product_select"
            )
        with lcol2:
            listing_url = st.text_input("Additional URL", placeholder="https://www.walmart.com/ip/...")
        with lcol3:
            listing_source = st.selectbox("Source", ["amazon", "walmart", "ebay", "target", "bestbuy", "other"])

        listing_submitted = st.form_submit_button("Add Listing")

        if listing_submitted:
            if not listing_url:
                st.error("URL is required.")
            else:
                target_product = next(p for p in all_products if p.name == listing_product_name)
                db = SessionLocal()
                db.add(ProductListing(product_id=target_product.id, url=listing_url, source=listing_source))
                db.commit()
                db.close()
                st.success(f"Added a new listing for {listing_product_name}. It'll be checked on the next scrape.")
                st.rerun()

st.divider()

st.subheader("Price History")

db = SessionLocal()
products = db.query(Product).all()
db.close()

if not products:
    st.info("No products tracked yet. Add one above to get started.")
else:
    product_names = {p.name: p.id for p in products}
    hcol1, hcol2 = st.columns([3, 1])
    with hcol1:
        selected_name = st.selectbox("Select a product", list(product_names.keys()))
    selected_id = product_names[selected_name]

    with hcol2:
        st.write("")
        st.write("")
        if st.button("🗑️ Delete this product"):
            db = SessionLocal()
            db.query(PriceHistory).filter(PriceHistory.product_id == selected_id).delete()
            db.query(ProductListing).filter(ProductListing.product_id == selected_id).delete()
            db.query(Product).filter(Product.id == selected_id).delete()
            db.commit()
            db.close()
            st.success(f"Deleted {selected_name}.")
            st.rerun()

    trend = get_price_trend(selected_id)

    if trend.empty:
        st.info("No price history yet for this product. It'll show up after the next scrape.")
    else:
        fig = px.line(trend, x="date", y="avg_price", markers=True)
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Avg Price ($)",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Biggest Drops This Week")

drops = get_biggest_drops(days=7)

if drops.empty:
    st.info("No drops in the last 7 days.")
else:
    drops_display = drops.copy()
    drops_display["pct_drop"] = drops_display["pct_drop"].round(1).astype(str) + "%"
    drops_display = drops_display.rename(columns={
        "name": "Product",
        "first_price": "Price 7d Ago",
        "last_price": "Current Price",
        "pct_drop": "% Drop",
    })
    st.dataframe(
        drops_display[["Product", "Price 7d Ago", "Current Price", "% Drop"]],
        use_container_width=True,
        hide_index=True,
    )