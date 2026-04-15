from flask import Flask, render_template, request, url_for, make_response, flash, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy import func

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

CATEGORIES = {"Food", "Bills", "Transport", "Random"}

def parse_date_or_none(str):
    if not str:
        return None
    try:
        return datetime.strptime(str, "%Y-%m-%d").date()
    except ValueError:
        return None

@app.route("/")
def index():

    start_date_str = (request.args.get("start-input") or "").strip()
    end_date_str = (request.args.get("end-input") or "").strip()
    selected_category = (request.args.get("category-input") or "").strip()

    start_date = parse_date_or_none(start_date_str)
    end_date = parse_date_or_none(end_date_str)

    if start_date and end_date and end_date < start_date:
        flash("End date cannot be before start date")
        start_date = end_date = None
        start_date_str = end_date_str = ""

    q = Expense.query
    if start_date:
        q = q.filter(Expense.date >= start_date)
    if end_date:
        q = q.filter(Expense.date <= end_date)

    if selected_category:
        q = q.filter(Expense.category == selected_category)

    expenses = q.order_by(Expense.date.desc(), Expense.id.desc()).all()

    total = sum(e.amount for e in expenses)

    cat_q = db.session.query(Expense.category, func.sum(Expense.amount))

    if start_date:
        cat_q = cat_q.filter(Expense.date >= start_date)
    if end_date:
        cat_q = cat_q.filter(Expense.date <= end_date)
    if selected_category:
        cat_q = cat_q.filter(Expense.category == selected_category)

    cat_rows = cat_q.group_by(Expense.category).all()
    cat_labels = [c for c, _ in cat_rows]
    cat_values = [round(float(s or 0), 2) for _, s in cat_rows]

    return render_template("index.html", 
                           expenses=expenses,
                           categories=CATEGORIES,
                           total=total,
                           start_str=start_date_str,
                           end_str=end_date_str,
                           today=date.today().isoformat(),
                           selected_category=selected_category,
                           cat_labels=cat_labels,
                           cat_values=cat_values
                           )

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
        d = datetime.strptime(date_str, "%d-%m-%Y").date()
    
    except ValueError:
        d = date.today()

    e = Expense(description=description, amount=amount, category=category, date=d)
    db.session.add(e)
    db.session.commit()

    flash("Expense added", "Success")
    return redirect(url_for("index"))

@app.route("/delete/<int:expense_id>", methods=['POST'])
def delete(expense_id):
    e = Expense.query.get_or_404(expense_id)
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted", "Success")
    return redirect(url_for("index"))



if __name__ == "__main__":
    app.run(debug=True)