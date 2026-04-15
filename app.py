from flask import Flask, render_template, request, url_for, make_response, flash, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'my-secret-key'
db = SQLAlchemy(app)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    description = db.Column(db.String(120), nullable = False)
    amount = db.Column(db.Float, nullable = False)
    category = db.Column(db.String(50), nullable = False, default="Uncategorised")
    date = db.Column(db.Date, nullable = False, default=date.today)


with app.app_context():
    db.create_all()

@app.route("/")
def index():

    expenses = Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    return render_template("index.html", expenses=expenses)

@app.route("/add", methods=['POST'])
def add_expense():

    description =  (request.form.get("description-input") or "").strip()
    amount_str =  (request.form.get("amount-input") or "").strip()
    category =  (request.form.get("category-input") or "").strip()
    date_str =  (request.form.get("date-input") or "").strip()

    if not description or not amount_str or not category:
        flash("Please fill all inputs")
        return redirect(url_for("index"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError

    except ValueError:
        flash("amount must be a postitive number", )
        return redirect(url_for("index"))
    
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    except ValueError:
        d = date.today()

    e = Expense(description=description, amount=amount, category=category, date=d)
    db.session.add(e)
    db.session.commit()

    flash("Expense added", "Success")
    return redirect(url_for("index"))

    print("Form recienved:", dict(request.form))
    return make_response("Form recieved check console")


if __name__ == "__main__":
    app.run(debug=True)