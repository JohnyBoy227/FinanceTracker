from sqlalchemy import create_engine, Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import date, datetime
from dotenv import load_dotenv
import os
import csv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Expense(Base):
    __tablename__ = "expense"

    id = Column(Integer, primary_key=True)
    description = Column(String(120), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50), nullable=False, default="Uncategorised")
    date = Column(Date, nullable=False, default=date.today)

Base.metadata.create_all(engine)

try:
    with open("data/exportStatements.csv", "r") as file:
        data = csv.DictReader(file)

        try:
            with Session() as session:
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
                        date = datetime.strptime(row["Transaction date"], "%Y-%m-%d").date()
                    ))
                    print("added to database: [description:", row["Transaction description"], "; amount:", amount, "; date:", row["Transaction date"], "]")
                session.commit()
                print("added to database sucussfully")
        except Exception as e:
            print("error adding to db: ", e)        
except FileNotFoundError:
    print("File not found")
except PermissionError:
    print("Permission denied")
except Exception as e:
    print("An error ocurred: ", e)

