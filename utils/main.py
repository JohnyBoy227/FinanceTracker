from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, or_
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import date, datetime
from dotenv import load_dotenv
import os
import pandas as pd

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Category(Base):
    __tablename__ = "category"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    parent_id = Column(Integer, ForeignKey('category.id'), nullable=True)

    parent = relationship("Category", back_populates="children", remote_side="Category.id")
    children = relationship("Category", back_populates="parent")
    expenses = relationship("Expense", back_populates="category")
    rules = relationship("Rule", back_populates="category")

class Expense(Base):
    __tablename__ = "expense"

    id = Column(Integer, primary_key=True)
    description = Column(String(120), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    category_id = Column(Integer, ForeignKey('category.id'))

    category = relationship("Category", back_populates="expenses")

class Rule(Base):
    __tablename__ = "rule"

    id = Column(Integer, primary_key=True)
    pattern = Column(String(120), nullable=False)
    priority = Column(Integer, nullable=False, default=0)

    category_id = Column(Integer, ForeignKey('category.id'), nullable=False)
    category = relationship("Category", back_populates="rules")

Base.metadata.create_all(engine)

with Session() as session:
    query = (session.query(Expense))
    
    print(query.count(), "expenses found")

    for expense in query:
        if expense.category.name == "uncategorised":
            expense.category = None

    session.commit()