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

class Expense(Base):
    __tablename__ = "expense"

    id = Column(Integer, primary_key=True)
    description = Column(String(120), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    category_id = Column(Integer, ForeignKey('category.id'))

    category = relationship("Category", back_populates="expenses")

Base.metadata.create_all(engine)

def apply_category(description):
    if "aldi" in description.casefold():
        return "Food"
    elif "tesco" in description.casefold():
        return "Food"
    elif "sainsburys" in description.casefold():
        return "Food"
    else:
        return "uncategorised"

with Session() as session:
    query = (
        session.query(Expense)
        .outerjoin(Category)
        .filter(or_(Category.name == "", Category.name == "uncategorised", Expense.category_id == None))
    )
    
    print(query.count(), "uncategorised expenses found")

    for expense in query:
        new_category_name = apply_category(expense.description)
        category = session.query(Category).filter_by(name=new_category_name).first()
        if not category:
            print("Category name not found - adding new category:", new_category_name)
            category = Category(name=new_category_name)
            session.add(category)
            session.flush()
        expense.category = category

    session.commit()



