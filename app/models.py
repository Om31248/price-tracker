from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    source = Column(String)
    target_price = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    history = relationship("PriceHistory", back_populates="product")
    listings = relationship("ProductListing", back_populates="product")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="history")


class ProductListing(Base):
    __tablename__ = "product_listings"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    url = Column(String, nullable=False)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="listings")
    prices = relationship("ListingPrice", back_populates="listing")


class ListingPrice(Base):
    __tablename__ = "listing_prices"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("product_listings.id"), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    listing = relationship("ProductListing", back_populates="prices")