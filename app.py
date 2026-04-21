from flask import Flask, render_template, request, url_for, make_response, flash, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy import func, or_
from dotenv import load_dotenv
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, decode_token
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta
import csv
import io
import os

app = Flask(__name__)

load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SECRET_KEY'] = os.getenv("DB_SECRET_KEY")
app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=20)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

ALLOWED_EXTENSIONS = set(['csv'])

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return redirect(url_for('login'))

@jwt.unauthorized_loader  
def unauthorized_callback(reason):
    return redirect(url_for('login'))

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(30), nullable = False)
    email = db.Column(db.String(), nullable = False)
    password = db.Column(db.Text, nullable = False)

    categories = db.relationship('Category', backref='user')
    expenses = db.relationship('Expense', backref='user')
    rules = db.relationship('Rule', backref='user')

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(120), nullable = False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    parent = db.relationship("Category", backref="children", remote_side="Category.id")
    expenses = db.relationship('Expense', backref='category')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    description = db.Column(db.String(120), nullable = False)
    amount = db.Column(db.Float, nullable = False)
    date = db.Column(db.Date, nullable = False, default=date.today)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=0)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship('Category', backref='rules')

with app.app_context():
    db.create_all()

def get_categories(user_id):
    return Category.query.filter(Category.user_id == user_id)

def get_rules(user_id):
    return Rule.query.filter(Rule.user_id == user_id)

def parse_date_or_none(str):
    if not str:
        return None
    try:
        return datetime.strptime(str, "%Y-%m-%d").date()
    except ValueError:
        return None

def get_current_user():
    token = request.cookies.get('access_token')
    if not token:
        return None
    try:
        decoded = decode_token(token)
        return decoded['sub']
    except Exception:
        return None
    
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_all_category_ids(category_name, user_id):
    root = Category.query.filter_by(name=category_name, user_id=user_id).first()
    print(f"category name '{category_name}'")
    if not root:
        return []
    
    ids = []
    stack = [root]
    while stack:
        cat = stack.pop()
        ids.append(cat.id)
        children = Category.query.filter_by(parent_id=cat.id, user_id=user_id).all()
        print(f"parent id: {cat.id}")
        print(children)
        stack.extend(children)
    
    print(ids)
    return ids

@app.route("/")
@jwt_required()
def index():
    user_id = int(get_jwt_identity())    

    start_date_str = (request.args.get("start-input") or "").strip()
    end_date_str = (request.args.get("end-input") or "").strip()
    selected_category = (request.args.get("category-input") or "").strip()

    start_date = parse_date_or_none(start_date_str)
    end_date = parse_date_or_none(end_date_str)

    if start_date and end_date and end_date < start_date:
        flash("End date cannot be before start date")
        start_date = end_date = None
        start_date_str = end_date_str = ""

    q = Expense.query.filter(Expense.user_id == user_id)
    if start_date:
        q = q.filter(Expense.date >= start_date)
    if end_date:
        q = q.filter(Expense.date <= end_date)

    if selected_category:
        if selected_category == "None":
            q = q.filter(Expense.category_id.is_(None))
        else:
            q = q.join(Category).filter(Category.id.in_(get_all_category_ids(category_name=selected_category, user_id=user_id)))

    expenses = q.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total = sum(e.amount for e in expenses)

    # pie chart
    cat_q = db.session.query(Category.name, func.sum(Expense.amount)).join(Expense, Expense.category_id == Category.id).filter(Expense.user_id == user_id, Expense.amount < 0)

    if start_date:
        cat_q = cat_q.filter(Expense.date >= start_date)
    if end_date:
        cat_q = cat_q.filter(Expense.date <= end_date)
    if selected_category:
        cat_q = cat_q.filter(Category.id.in_(get_all_category_ids(category_name=selected_category, user_id=user_id)))

    cat_rows = cat_q.group_by(Category.name).all()
    cat_labels = [c for c, _ in cat_rows]
    cat_values = [round(float(s or 0), 2) for _, s in cat_rows]

    # day chart
    day_q = db.session.query(Expense.date, func.sum(Expense.amount)).filter(Expense.user_id == user_id, Expense.amount <0)

    if start_date:
        day_q = day_q.filter(Expense.date >= start_date)
    if end_date:
        day_q = day_q.filter(Expense.date <= end_date)
    if selected_category:
        day_q = day_q.join(Category).filter(Category.id.in_(get_all_category_ids(category_name=selected_category, user_id=user_id)))

    day_rows = day_q.group_by(Expense.date).order_by(Expense.date).all()
    day_labels = [d.isoformat() for d, _ in day_rows]
    day_values = [round(float(s or 0), 2) for _, s in day_rows]

    money_in  = sum(e.amount for e in expenses if e.amount > 0)
    money_out = sum(e.amount for e in expenses if e.amount < 0)
    net = money_in + money_out

    return render_template(
        "index.html", 
        expenses=expenses,
        categories=get_categories(user_id=user_id),
        total=total,
        start_str=start_date_str,
        end_str=end_date_str,
        today=date.today().isoformat(),
        selected_category=selected_category,
        cat_labels=cat_labels,
        cat_values=cat_values,
        day_labels=day_labels,
        day_values=day_values,
        money_in=money_in,
        money_out=abs(money_out),
        net=net,
        expense_count=len(expenses)
    )

@app.route("/register", methods=['GET','POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    username = (request.form.get("username-input") or "").strip()
    email = (request.form.get("email-input") or "").strip()
    password = (request.form.get("password-input") or "").strip()
    confirm_password = (request.form.get("confirm-password-input") or "").strip()

    if not username or not email or not password or not confirm_password:
        flash("Please fill all inputs")
        return redirect(url_for('register'))
    
    user_query = User.query.filter(or_(User.username == username, User.email == email)).first()

    if user_query is not None:
        flash("User already exists")
        return redirect(url_for('register'))
    
    new_user = User(
        username = username,
        email = email
    )
    new_user.set_password(password=password)

    db.session.add(new_user)
    db.session.commit()

    token_query = User.query.filter(User.email == email).first()

    if token_query is None:
        flash("User does not exist")
        return redirect(url_for('login'))

    if not token_query.check_password(password=password):
        flash("Password incorect")
        return redirect(url_for('login'))
    
    access_token = create_access_token(identity=str(token_query.id))
    
    response = make_response(redirect(url_for('index')))
    response.set_cookie(
        'access_token_cookie',
        access_token,
        httponly=True,
        samesite='Lax',
    )
    flash("Registration sucessful", "Success")
    return response

@app.route("/login", methods=['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    email = (request.form.get("email-input") or "").strip()
    password = (request.form.get("password-input") or "").strip()

    if not email or not password:
        flash("Please fill all inputs")
        return redirect(url_for('login'))

    user_query = User.query.filter_by(email=email).first()

    if user_query is None:
        flash("User does not exist")
        return redirect(url_for('login'))

    if not user_query.check_password(password=password):
        flash("Password incorect")
        return redirect(url_for('login'))
    
    access_token = create_access_token(identity=str(user_query.id))
    
    response = make_response(redirect(url_for('index')))
    response.set_cookie(
        'access_token_cookie',
        access_token,
        httponly=True,
        samesite='Lax',
    )
    return response

@app.route("/logout")
@jwt_required()
def logout():
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('access_token_cookie')
    return response

@app.route("/expenses/add", methods=['POST'])
@jwt_required()
def add_expense():
    user_id = int(get_jwt_identity())
    description = (request.form.get("description-input") or "").strip()
    amount_str = (request.form.get("amount-input") or "").strip()
    category_name = (request.form.get("category-input") or "").strip()
    date_str = (request.form.get("date-input") or "").strip()

    if not description or not amount_str or not category_name:
        flash("Please fill all inputs")
        return redirect(url_for("index"))

    cat_obj = Category.query.filter_by(name=category_name, user_id=user_id).first()
    if not cat_obj:
        flash(f"Category '{category_name}' does not exist", "error")
        return redirect(url_for("index"))

    amount = float(amount_str)
    
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        d = date.today()

    e = Expense(description=description, amount=amount, category=cat_obj, date=d, user_id=user_id)
    db.session.add(e)
    db.session.commit()

    flash("Expense added", "Success")
    return redirect(url_for("index"))

@app.route("/expenses/delete/<int:expense_id>", methods=['POST'])
@jwt_required()
def delete_expense(expense_id):
    user_id = int(get_jwt_identity())    
    e = Expense.query.filter_by(id=expense_id, user_id=user_id).first_or_404()
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted", "Success")
    return redirect(url_for("index"))

@app.route("/expenses/edit/<int:expense_id>", methods=['GET'])
@jwt_required()
def edit_expense_get(expense_id):
    user_id = int(get_jwt_identity())    
    e = Expense.query.filter_by(id=expense_id, user_id=user_id).first_or_404()
    return render_template("edit.html", expense=e, categories=get_categories(user_id=user_id))

@app.route("/expenses/edit/<int:expense_id>", methods=['POST'])
@jwt_required()
def edit_expense(expense_id):
    user_id = int(get_jwt_identity())    
    e = Expense.query.filter_by(user_id=user_id, id=expense_id).first_or_404()

    description = (request.form.get("description-input") or "").strip()
    amount_str = (request.form.get("amount-input") or "").strip()
    category_name = (request.form.get("category-input") or "").strip()
    date_str = (request.form.get("date-input") or "").strip()

    if not description or not amount_str or not category_name:
        flash("Please fill all inputs", "error")
        return redirect(url_for("edit_expense_get", expense_id=expense_id))
    
    cat_obj = Category.query.filter_by(name=category_name, user_id=user_id).first()
    if not cat_obj:
        flash(f"Category '{category_name}' does not exist", "error")
        return redirect(url_for("edit_expense_get", expense_id=expense_id))
    
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
@jwt_required()
def categories():
    user_id = int(get_jwt_identity())    
    return render_template("categories.html", categories=get_categories(user_id=user_id))

@app.route("/categories/add", methods=['POST'])
@jwt_required()
def add_category():
    user_id = int(get_jwt_identity())    
    name = (request.form.get("name-input") or "").strip()
    parent_category_name = (request.form.get("category-input") or "").strip()

    if not name:
        flash("Please fill name")
        return redirect(url_for("categories"))

    if parent_category_name == "None" or not parent_category_name:
        parent_category_name = None

    category_q = Category.query.filter_by(name=parent_category_name, user_id=user_id).first() if parent_category_name else None

    c = Category(name=name, user_id=user_id, parent_id=category_q.id if category_q else None)
    db.session.add(c)
    db.session.commit()

    flash("Category added", "Success")
    return redirect(url_for("categories"))

@app.route("/categories/delete/<int:category_id>", methods=['POST'])
@jwt_required()
def delete_category(category_id):
    user_id = int(get_jwt_identity())    
    c = Category.query.filter_by(user_id=user_id, id=category_id).first_or_404()
    
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
@jwt_required()
def rules():
    user_id = int(get_jwt_identity())    
    return render_template("rules.html", rules=get_rules(user_id=user_id), categories=get_categories(user_id=user_id))

@app.route("/rules/add", methods=['POST'])
@jwt_required()
def add_rule():
    user_id = int(get_jwt_identity())    
    pattern = (request.form.get("pattern-input") or "").strip()
    priority = (request.form.get("priority-input") or "").strip()
    category_name = (request.form.get("category-input") or "").strip()
    if not pattern or not priority or not category_name:
        flash("Please fill all inputs")
        return redirect(url_for("rules"))

    category_obj = Category.query.filter_by(name=category_name).first()

    r = Rule(pattern=pattern, priority=priority, category=category_obj, user_id=user_id)
    db.session.add(r)
    db.session.commit()

    flash("Rule added", "Success")
    return redirect(url_for("rules"))

@app.route("/rules/delete/<int:rule_id>", methods=['POST'])
@jwt_required()
def delete_rule(rule_id):
    user_id = int(get_jwt_identity())    
    r = Rule.query.filter_by(user_id=user_id, id=rule_id).first_or_404()
    db.session.delete(r)
    db.session.commit()
    flash("Rule deleted", "Success")
    return redirect(url_for("rules"))

@app.route("/rules/apply", methods=['POST'])
@jwt_required()
def apply_rules():
    user_id = int(get_jwt_identity())    
    def apply_category(description):
        rules = db.session.query(Rule).filter(Rule.user_id == user_id).order_by(Rule.priority.desc()).all()
        
        for rule in rules:
            if rule.pattern.strip().casefold() in description.strip().casefold():
                return rule.category
        return None

    expenses = Expense.query.filter(Expense.category_id == None, Expense.user_id == user_id)
    
    print(expenses.count(), "uncategorised expenses found")

    matched = 0
    for expense in expenses:
        category = apply_category(expense.description)
        if category:
            expense.category = category
            matched += 1

    db.session.commit()

    flash(f"{matched} expenses categorised", "success")
    return redirect(url_for('rules'))

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload():
    user_id = get_jwt_identity()
    file = request.files['file']
    if not file or not allowed_file(file.filename):
        flash("No or incorrect file")
        return redirect(url_for('rules'))

    try:
        file_stream = io.TextIOWrapper(file.stream, encoding='utf-8')
        data = csv.DictReader(file_stream)
        counter = 0
        for row in data:
            if row["Debit Amount"] != "":
                amount = float(row["Debit Amount"].strip()) * -1
            elif row["Credit amount"] != "":
                amount = float(row["Credit amount"].strip())
            else:
                amount = 0
                print("Both credit and debit amount == \"\"")
            db.session.add(Expense(
                description = row["Transaction description"],
                amount = amount,
                date = datetime.strptime(row["Transaction date"], "%Y-%m-%d").date(),
                user_id=user_id
            ))
            counter += 1
        db.session.commit()
        flash(f"{counter} expenses added", "success")
    except Exception as e:
        db.session.rollback()
        print("Error uploading file", e)        
        flash("An error ocured uploading file", "error")

    return redirect(url_for('rules'))


if __name__ == "__main__":
    app.run(debug=True)