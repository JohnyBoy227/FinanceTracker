from flask import Flask, render_template, request, url_for, make_response, flash, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy import func
import os
from dotenv import load_dotenv
from flask_migrate import Migrate

app = Flask(__name__)

load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SECRET_KEY'] = os.getenv("DB_SECRET_KEY")
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(120), nullable = False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)

    parent = db.relationship("Category", backref="children", remote_side="Category.id")
    expenses = db.relationship('Expense', backref='category')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    description = db.Column(db.String(120), nullable = False)
    amount = db.Column(db.Float, nullable = False)
    date = db.Column(db.Date, nullable = False, default=date.today)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=0)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship('Category', backref='rules')

with app.app_context():
    db.create_all()

def get_categories():
    return Category.query.all()

def get_rules():
    return Rule.query.all()

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
        if selected_category == "None":
            q = q.join(Category).filter(Category.name.is_(None))
        else:
            q = q.join(Category).filter(Category.name == selected_category)

    expenses = q.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total = sum(e.amount for e in expenses)

    # pie chart
    cat_q = db.session.query(Category.name, func.sum(Expense.amount)).join(Expense, Expense.category_id == Category.id)

    if start_date:
        cat_q = cat_q.filter(Expense.date >= start_date)
    if end_date:
        cat_q = cat_q.filter(Expense.date <= end_date)
    if selected_category:
        cat_q = cat_q.filter(Category.name == selected_category)

    cat_rows = cat_q.group_by(Category.name).all()
    cat_labels = [c for c, _ in cat_rows]
    cat_values = [round(float(s or 0), 2) for _, s in cat_rows]

    # day chart
    day_q = db.session.query(Expense.date, func.sum(Expense.amount))

    if start_date:
        day_q = day_q.filter(Expense.date >= start_date)
    if end_date:
        day_q = day_q.filter(Expense.date <= end_date)
    if selected_category:
        day_q = day_q.join(Category).filter(Category.name == selected_category)

    day_rows = day_q.group_by(Expense.date).order_by(Expense.date).all()
    day_labels = [d.isoformat() for d, _ in day_rows]
    day_values = [round(float(s or 0), 2) for _, s in day_rows]

    return render_template(
        "index.html", 
        expenses=expenses,
        categories=get_categories(),
        total=total,
        start_str=start_date_str,
        end_str=end_date_str,
        today=date.today().isoformat(),
        selected_category=selected_category,
        cat_labels=cat_labels,
        cat_values=cat_values,
        day_labels=day_labels,
        day_values=day_values
    )

@app.route("/expenses/add", methods=['POST'])
def add_expense():
    description = (request.form.get("description-input") or "").strip()
    amount_str = (request.form.get("amount-input") or "").strip()
    category_name = (request.form.get("category-input") or "").strip()
    date_str = (request.form.get("date-input") or "").strip()

    if not description or not amount_str or not category_name:
        flash("Please fill all inputs")
        return redirect(url_for("index"))

    cat_obj = Category.query.filter_by(name=category_name).first()
    if not cat_obj:
        flash(f"Category '{category_name}' does not exist", "error")
        return redirect(url_for("index"))

    amount = float(amount_str)
    
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        d = date.today()

    e = Expense(description=description, amount=amount, category=cat_obj, date=d)
    db.session.add(e)
    db.session.commit()

    flash("Expense added", "Success")
    return redirect(url_for("index"))

@app.route("/expenses/delete/<int:expense_id>", methods=['POST'])
def delete_expense(expense_id):
    e = Expense.query.get_or_404(expense_id)
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted", "Success")
    return redirect(url_for("index"))

@app.route("/expenses/edit/<int:expense_id>", methods=['GET'])
def edit_expense_get(expense_id):
    e = Expense.query.get_or_404(expense_id)
    return render_template("edit.html", expense=e, categories=get_categories())

@app.route("/expenses/edit/<int:expense_id>", methods=['POST'])
def edit_expense(expense_id):
    e = Expense.query.get_or_404(expense_id)

    description = (request.form.get("description-input") or "").strip()
    amount_str = (request.form.get("amount-input") or "").strip()
    category_name = (request.form.get("category-input") or "").strip()
    date_str = (request.form.get("date-input") or "").strip()

    if not description or not amount_str or not category_name:
        flash("Please fill all inputs", "error")
        return redirect(url_for("edit", expense_id=expense_id))
    
    cat_obj = Category.query.filter_by(name=category_name).first()
    if not cat_obj:
        flash(f"Category '{category_name}' does not exist", "error")
        return redirect(url_for("edit", expense_id=expense_id))
    
    amount = float(amount_str)
    
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        d = date.today()
    
    e.description = description
    e.amount = amount
    e.category = cat_obj
    e.date = d
    db.session.commit()

    flash("Expense edited", "Success")
    return redirect(url_for("index"))

@app.route("/categories", methods=['GET'])
def categories():
    return render_template("categories.html", categories=get_categories())

@app.route("/categories/add", methods=['POST'])
def add_category():
    name = (request.form.get("name-input") or "").strip()
    if not name:
        flash("Please fill name")
        return redirect(url_for("categories"))

    c = Category(name=name)
    db.session.add(c)
    db.session.commit()

    flash("Category added", "Success")
    return redirect(url_for("categories"))

@app.route("/categories/delete/<int:category_id>", methods=['POST'])
def delete_category(category_id):
    c = Category.query.get_or_404(category_id)
    
    for e in c.expenses:
        e.category = None

    for children in c.children:
        children.parent_id = None
    
    for rule in c.rules:
        db.session.delete(rule)
    
    db.session.delete(c)
    db.session.commit()
    flash("Category deleted", "Success")
    return redirect(url_for("categories"))

@app.route("/rules", methods=['GET'])
def rules():
    return render_template("rules.html", rules=get_rules(), categories=get_categories())

@app.route("/rules/add", methods=['POST'])
def add_rule():
    pattern = (request.form.get("pattern-input") or "").strip()
    priority = (request.form.get("priority-input") or "").strip()
    category_name = (request.form.get("category-input") or "").strip()
    if not pattern or not priority or not category_name:
        flash("Please fill all inputs")
        return redirect(url_for("rules"))

    category_obj = Category.query.filter_by(name=category_name).first()

    r = Rule(pattern=pattern, priority=priority, category=category_obj)
    db.session.add(r)
    db.session.commit()

    flash("Rule added", "Success")
    return redirect(url_for("rules"))

@app.route("/rules/delete/<int:rule_id>", methods=['POST'])
def delete_rule(rule_id):
    r = Rule.query.get_or_404(rule_id)
    db.session.delete(r)
    db.session.commit()
    flash("Rule deleted", "Success")
    return redirect(url_for("rules"))

@app.route("/rules/apply", methods=['POST'])
def apply_rules():
    def apply_category(description):
        rules = db.session.query(Rule).order_by(Rule.priority.desc()).all()
        
        for rule in rules:
            if rule.pattern.casefold() in description.casefold():
                return rule.category
        return None

    expenses = Expense.query.filter(Expense.category_id == None)
    
    print(expenses.count(), "uncategorised expenses found")

    matched = 0
    for expense in expenses:
        category = apply_category(expense.description)
        if category:
            expense.category = category
            matched += 1
        else:
            print("No rule matched:", expense.description)

    db.session.commit()

    flash(f"{matched} expenses categorised")
    return redirect(url_for('rules'))

if __name__ == "__main__":
    app.run(debug=True)