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

def apply_category(description, session):
    rules = session.query(Rule).order_by(Rule.priority.desc()).all()
    
    for rule in rules:
        if rule.pattern.casefold() in description.casefold():
            return rule.category
    
    return None

with Session() as session:
    query = (session.query(Expense).filter(Expense.category_id == None))
    
    print(query.count(), "uncategorised expenses found")

    for expense in query:
        category = apply_category(expense.description, session)
        if category:
            expense.category = category
        else:
            print("No rule matched:", expense.description)

    session.commit()
