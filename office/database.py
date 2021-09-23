import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session as ORMSession
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("USING TEMP DB, не задан $DATABASE_URL")
    DATABASE_URL = "sqlite:///temp.db"
engine = create_engine(DATABASE_URL)


def create_schema():
    Base.metadata.create_all(engine, checkfirst=True)


class Session:
    session = None

    def __init__(self) -> None:
        self.session_class = sessionmaker(bind=engine)

    def __enter__(self) -> ORMSession:
        self.session = self.session_class()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not exc_type:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()
        self.session = None