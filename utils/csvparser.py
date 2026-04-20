from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import date, datetime
from dotenv import load_dotenv
import os
import csv
from werkzeug.security import generate_password_hash

load_dotenv()

username = os.getenv("APP_USERNAME")
email = os.getenv("APP_EMAIL")
password = os.getenv("APP_PASSWORD")

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    username = Column(String(), nullable=False)
    email = Column(String(), nullable=False)
    password = Column(Text, nullable=False)

    categories = relationship("Category", back_populates='user')
    expenses = relationship("Expense", back_populates='user')
    rules = relationship("Rule", back_populates='user')

    def set_password(self, password):
        self.password = generate_password_hash(password)

class Category(Base):
    __tablename__ = "category"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    parent_id = Column(Integer, ForeignKey('category.id'), nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)

    parent = relationship("Category", back_populates="children", remote_side="Category.id")
    children = relationship("Category", back_populates="parent")
    expenses = relationship("Expense", back_populates="category")
    rules = relationship("Rule", back_populates="category")
    user = relationship("User", back_populates='categories')

class Expense(Base):
    __tablename__ = "expense"

    id = Column(Integer, primary_key=True)
    description = Column(String(120), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    category_id = Column(Integer, ForeignKey('category.id'))
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)

    category = relationship("Category", back_populates="expenses")
    user = relationship("User", back_populates='expenses')

class Rule(Base):
    __tablename__ = "rule"

    id = Column(Integer, primary_key=True)
    pattern = Column(String(120), nullable=False)
    priority = Column(Integer, nullable=False, default=0)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)

    category_id = Column(Integer, ForeignKey('category.id'), nullable=False)
    category = relationship("Category", back_populates="rules")
    user = relationship("User", back_populates='rules')

Base.metadata.create_all(engine)

with Session() as session:
    user_query = session.query(User).filter_by(email=email).first()
    if not user_query:
        print("No user found - creating new user")
        new_user = User(
            username=username,
            email=email
        )
        session.add(new_user)
        new_user.set_password(password=password)
        session.commit()
    else:
        print(f"User found: {username}")
    id_query = session.query(User).filter_by(email=email).first()
    user_id = id_query.id

    try:
        with open("data/exportStatements.csv", "r") as file:
            data = csv.DictReader(file)

            try:
                counter = 0
                for row in data:
                    if row["Debit Amount"] != "":
                        amount = float(row["Debit Amount"].strip()) * -1
                    elif row["Credit amount"] != "":
                        amount = float(row["Credit amount"].strip())
                    else:
                        amount = 0
                        print("Both credit and debit amount == \"\"")
                    session.add(Expense(
                        description = row["Transaction description"],
                        amount = amount,
                        date = datetime.strptime(row["Transaction date"], "%Y-%m-%d").date(),
                        user_id=user_id
                    ))
                    counter += 1
                session.commit()
                print(f"Added {counter} entries to database sucussfully")
            except Exception as e:
                print("error adding to db: ", e)        
    except FileNotFoundError:
        print("File not found")
    except PermissionError:
        print("Permission denied")
    except Exception as e:
        print("An error ocurred: ", e)

