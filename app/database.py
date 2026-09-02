from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def init_db():
    # import models here so they're registered on Base before create_all runs
    import models
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
    print("db initialized")