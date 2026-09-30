import math
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for
)

from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-change-before-deployment"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "database.db"
)


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
            UNIQUE(name, type)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            date TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, month, year)
        )
    """)

    expense_categories = [
        "Food",
        "Transportation",
        "Shopping",
        "Bills",
        "Entertainment",
        "Healthcare",
        "Education",
        "Rent",
        "Travel",
        "Other"
    ]

    income_categories = [
        "Salary",
        "Freelance",
        "Business",
        "Investment",
        "Gift",
        "Other"
    ]

    for category in expense_categories:
        connection.execute(
            """
            INSERT OR IGNORE INTO categories (name, type)
            VALUES (?, ?)
            """,
            (category, "expense")
        )

    for category in income_categories:
        connection.execute(
            """
            INSERT OR IGNORE INTO categories (name, type)
            VALUES (?, ?)
            """,
            (category, "income")
        )

    connection.commit()
    connection.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("Please fill in all required fields.", "error")
            return render_template("register.html")

        if len(name) < 2:
            flash("Name must contain at least 2 characters.", "error")
            return render_template("register.html")

        if "@" not in email or "." not in email.split("@")[-1]:
            flash("Please enter a valid email address.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        connection = get_db_connection()

        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing_user:
            connection.close()
            flash("An account with that email already exists.", "error")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        connection.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
            """,
            (name, email, hashed_password)
        )

        connection.commit()
        connection.close()

        flash(
            "Your account has been created. You can now log in.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return render_template("login.html")

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT id, name, email, password
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        connection.close()

        if user is None or not check_password_hash(
            user["password"],
            password
        ):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session.clear()

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    today = date.today()

    current_month = today.month
    current_year = today.year

    month_start = f"{current_year:04d}-{current_month:02d}-01"

    if current_month == 12:
        next_month = f"{current_year + 1:04d}-01-01"
    else:
        next_month = (
            f"{current_year:04d}-{current_month + 1:02d}-01"
        )

    connection = get_db_connection()

    total_income_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        AND type = 'income'
        """,
        (user_id,)
    ).fetchone()

    total_expense_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        AND type = 'expense'
        """,
        (user_id,)
    ).fetchone()

    monthly_income_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        AND type = 'income'
        AND date >= ?
        AND date < ?
        """,
        (user_id, month_start, next_month)
    ).fetchone()

    monthly_expense_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        AND type = 'expense'
        AND date >= ?
        AND date < ?
        """,
        (user_id, month_start, next_month)
    ).fetchone()

    budget_row = connection.execute(
        """
        SELECT amount
        FROM budgets
        WHERE user_id = ?
        AND month = ?
        AND year = ?
        """,
        (user_id, current_month, current_year)
    ).fetchone()

    category_spending = connection.execute(
        """
        SELECT
            categories.name AS name,
            SUM(transactions.amount) AS total
        FROM transactions
        INNER JOIN categories
            ON categories.id = transactions.category_id
        WHERE transactions.user_id = ?
        AND transactions.type = 'expense'
        GROUP BY categories.id, categories.name
        ORDER BY total DESC
        LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    recent_transactions = connection.execute(
        """
        SELECT
            transactions.id,
            transactions.type,
            transactions.amount,
            transactions.date,
            transactions.description,
            categories.name AS category_name
        FROM transactions
        INNER JOIN categories
            ON categories.id = transactions.category_id
        WHERE transactions.user_id = ?
        ORDER BY transactions.date DESC, transactions.id DESC
        LIMIT 6
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    total_income = total_income_row["total"]
    total_expenses = total_expense_row["total"]

    monthly_income = monthly_income_row["total"]
    monthly_expenses = monthly_expense_row["total"]

    balance = total_income - total_expenses

    monthly_budget = (
        budget_row["amount"]
        if budget_row
        else 0
    )

    remaining_budget = monthly_budget - monthly_expenses

    if monthly_budget > 0:
        budget_percentage = (
            monthly_expenses / monthly_budget
        ) * 100

        budget_percentage = min(
            budget_percentage,
            100
        )
    else:
        budget_percentage = 0

    return render_template(
        "dashboard.html",
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        monthly_budget=monthly_budget,
        remaining_budget=remaining_budget,
        budget_percentage=budget_percentage,
        category_spending=category_spending,
        recent_transactions=recent_transactions,
        current_month=today.strftime("%B"),
        current_year=current_year
    )


@app.route("/add-transaction", methods=["GET", "POST"])
@login_required
def add_transaction():
    connection = get_db_connection()

    categories = connection.execute(
        """
        SELECT id, name, type
        FROM categories
        ORDER BY type, name
        """
    ).fetchall()

    if request.method == "POST":
        transaction_type = request.form.get(
            "type",
            ""
        ).strip().lower()

        category_id = request.form.get(
            "category_id",
            ""
        ).strip()

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        transaction_date = request.form.get(
            "date",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        if transaction_type not in ("income", "expense"):
            connection.close()

            flash(
                "Please select a valid transaction type.",
                "error"
            )

            return render_template(
                "add_transaction.html",
                categories=categories
            )

        if not category_id or not amount_text or not transaction_date:
            connection.close()

            flash(
                "Please complete all required fields.",
                "error"
            )

            return render_template(
                "add_transaction.html",
                categories=categories
            )

        try:
            amount = float(amount_text)
        except ValueError:
            connection.close()

            flash(
                "Please enter a valid amount.",
                "error"
            )

            return render_template(
                "add_transaction.html",
                categories=categories
            )

        if not math.isfinite(amount) or amount <= 0:
            connection.close()

            flash(
                "Amount must be a valid number greater than zero.",
                "error"
            )

            return render_template(
                "add_transaction.html",
                categories=categories
            )

        try:
            date.fromisoformat(transaction_date)
        except ValueError:
            connection.close()

            flash(
                "Please enter a valid date.",
                "error"
            )

            return render_template(
                "add_transaction.html",
                categories=categories
            )

        category = connection.execute(
            """
            SELECT id, name, type
            FROM categories
            WHERE id = ?
            """,
            (category_id,)
        ).fetchone()

        if category is None:
            connection.close()

            flash(
                "The selected category does not exist.",
                "error"
            )

            return render_template(
                "add_transaction.html",
                categories=categories
            )

        if category["type"] != transaction_type:
            connection.close()

            flash(
                "The selected category is not valid for this transaction.",
                "error"
            )

            return render_template(
                "add_transaction.html",
                categories=categories
            )

        connection.execute(
            """
            INSERT INTO transactions (
                user_id,
                type,
                category_id,
                amount,
                date,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                transaction_type,
                category_id,
                amount,
                transaction_date,
                description or None
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Transaction added successfully.",
            "success"
        )

        return redirect(url_for("dashboard"))

    connection.close()

    return render_template(
        "add_transaction.html",
        categories=categories
    )

@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    user_id = session["user_id"]

    today = date.today()

    selected_month = request.args.get(
        "month",
        str(today.month)
    )

    selected_year = request.args.get(
        "year",
        str(today.year)
    )

    try:
        selected_month = int(selected_month)
        selected_year = int(selected_year)
    except ValueError:
        selected_month = today.month
        selected_year = today.year

    if selected_month < 1 or selected_month > 12:
        selected_month = today.month

    if selected_year < 2000 or selected_year > 2100:
        selected_year = today.year

    connection = get_db_connection()

    if request.method == "POST":
        month = request.form.get(
            "month",
            str(selected_month)
        ).strip()

        year = request.form.get(
            "year",
            str(selected_year)
        ).strip()

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        try:
            month = int(month)
            year = int(year)
            amount = float(amount_text)
        except ValueError:
            connection.close()

            flash(
                "Please enter valid budget details.",
                "error"
            )

            return redirect(
                url_for(
                    "budget",
                    month=selected_month,
                    year=selected_year
                )
            )

        if month < 1 or month > 12:
            connection.close()

            flash(
                "Please select a valid month.",
                "error"
            )

            return redirect(url_for("budget"))

        if year < 2000 or year > 2100:
            connection.close()

            flash(
                "Please enter a valid year.",
                "error"
            )

            return redirect(url_for("budget"))

        if not math.isfinite(amount) or amount <= 0:
            connection.close()

            flash(
                "Budget amount must be a valid number greater than zero.",
                "error"
            )

            return redirect(
                url_for(
                    "budget",
                    month=month,
                    year=year
                )
            )

        existing_budget = connection.execute(
            """
            SELECT id
            FROM budgets
            WHERE user_id = ?
            AND month = ?
            AND year = ?
            """,
            (
                user_id,
                month,
                year
            )
        ).fetchone()

        if existing_budget:
            connection.execute(
                """
                UPDATE budgets
                SET amount = ?
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    amount,
                    existing_budget["id"],
                    user_id
                )
            )
        else:
            connection.execute(
                """
                INSERT INTO budgets (
                    user_id,
                    month,
                    year,
                    amount
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    month,
                    year,
                    amount
                )
            )

        connection.commit()
        connection.close()

        flash(
            "Monthly budget saved successfully.",
            "success"
        )

        return redirect(
            url_for(
                "budget",
                month=month,
                year=year
            )
        )

    budget_row = connection.execute(
        """
        SELECT amount
        FROM budgets
        WHERE user_id = ?
        AND month = ?
        AND year = ?
        """,
        (
            user_id,
            selected_month,
            selected_year
        )
    ).fetchone()

    budget_amount = (
        budget_row["amount"]
        if budget_row
        else 0
    )

    month_start = (
        f"{selected_year:04d}-"
        f"{selected_month:02d}-01"
    )

    if selected_month == 12:
        next_month = (
            f"{selected_year + 1:04d}-01-01"
        )
    else:
        next_month = (
            f"{selected_year:04d}-"
            f"{selected_month + 1:02d}-01"
        )

    spent_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        AND type = 'expense'
        AND date >= ?
        AND date < ?
        """,
        (
            user_id,
            month_start,
            next_month
        )
    ).fetchone()

    spent_amount = spent_row["total"]

    remaining_amount = (
        budget_amount - spent_amount
    )

    if budget_amount > 0:
        progress_percentage = (
            spent_amount / budget_amount
        ) * 100

        progress_percentage = min(
            progress_percentage,
            100
        )
    else:
        progress_percentage = 0

    connection.close()

    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December"
    ]

    return render_template(
        "budget.html",
        budget_amount=budget_amount,
        spent_amount=spent_amount,
        remaining_amount=remaining_amount,
        progress_percentage=progress_percentage,
        selected_month=selected_month,
        selected_year=selected_year,
        month_name=month_names[selected_month - 1]
    )
@app.route("/transactions")
@login_required
def transactions():
    user_id = session["user_id"]

    search = request.args.get(
        "search",
        ""
    ).strip()

    selected_type = request.args.get(
        "type",
        ""
    ).strip().lower()

    selected_category = request.args.get(
        "category",
        ""
    ).strip()

    start_date = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date = request.args.get(
        "end_date",
        ""
    ).strip()

    connection = get_db_connection()

    query = """
        SELECT
            transactions.id,
            transactions.type,
            transactions.amount,
            transactions.date,
            transactions.description,
            categories.name AS category_name
        FROM transactions
        INNER JOIN categories
            ON categories.id = transactions.category_id
        WHERE transactions.user_id = ?
    """

    parameters = [user_id]

    if search:
        query += """
            AND (
                transactions.description LIKE ?
                OR categories.name LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.extend(
            [search_value, search_value]
        )

    if selected_type in ("income", "expense"):
        query += """
            AND transactions.type = ?
        """

        parameters.append(selected_type)

    if selected_category:
        try:
            category_id = int(selected_category)

            query += """
                AND transactions.category_id = ?
            """

            parameters.append(category_id)

        except ValueError:
            selected_category = ""

    # Validate the date filters before adding them to the SQL query.
    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            flash("Please enter a valid From date.", "error")
            start_date = ""

    if end_date:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            flash("Please enter a valid To date.", "error")
            end_date = ""

    if start_date and end_date and start_date > end_date:
        flash(
            "From date cannot be later than To date.",
            "error"
        )
        start_date = ""
        end_date = ""

    if start_date:
        query += """
            AND transactions.date >= ?
        """
        parameters.append(start_date)

    if end_date:
        query += """
            AND transactions.date <= ?
        """
        parameters.append(end_date)

    query += """
        ORDER BY transactions.date DESC,
        transactions.id DESC
    """

    transaction_rows = connection.execute(
        query,
        parameters
    ).fetchall()

    categories = connection.execute(
        """
        SELECT id, name, type
        FROM categories
        ORDER BY type, name
        """
    ).fetchall()

    connection.close()

    return render_template(
        "transactions.html",
        transactions=transaction_rows,
        categories=categories,
        search=search,
        selected_type=selected_type,
        selected_category=selected_category,
        start_date=start_date,
        end_date=end_date
    )

@app.route(
    "/edit-transaction/<int:transaction_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_transaction(transaction_id):
    user_id = session["user_id"]

    connection = get_db_connection()

    transaction = connection.execute(
        """
        SELECT
            transactions.id,
            transactions.type,
            transactions.category_id,
            transactions.amount,
            transactions.date,
            transactions.description
        FROM transactions
        WHERE transactions.id = ?
        AND transactions.user_id = ?
        """,
        (transaction_id, user_id)
    ).fetchone()

    if transaction is None:
        connection.close()

        flash(
            "Transaction not found.",
            "error"
        )

        return redirect(url_for("transactions"))

    categories = connection.execute(
        """
        SELECT id, name, type
        FROM categories
        ORDER BY type, name
        """
    ).fetchall()

    if request.method == "POST":
        transaction_type = request.form.get(
            "type",
            ""
        ).strip().lower()

        category_id = request.form.get(
            "category_id",
            ""
        ).strip()

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        transaction_date = request.form.get(
            "date",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        if transaction_type not in ("income", "expense"):
            connection.close()

            flash(
                "Please select a valid transaction type.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_transaction",
                    transaction_id=transaction_id
                )
            )

        if not category_id or not amount_text or not transaction_date:
            connection.close()

            flash(
                "Please fill in all required fields.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_transaction",
                    transaction_id=transaction_id
                )
            )

        try:
            amount = float(amount_text)
        except ValueError:
            connection.close()

            flash(
                "Please enter a valid amount.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_transaction",
                    transaction_id=transaction_id
                )
            )

        if not math.isfinite(amount) or amount <= 0:
            connection.close()

            flash(
                "Amount must be a valid number greater than zero.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_transaction",
                    transaction_id=transaction_id
                )
            )

        try:
            date.fromisoformat(transaction_date)
        except ValueError:
            connection.close()

            flash(
                "Please enter a valid date.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_transaction",
                    transaction_id=transaction_id
                )
            )

        category = connection.execute(
            """
            SELECT id, type
            FROM categories
            WHERE id = ?
            """,
            (category_id,)
        ).fetchone()

        if category is None or category["type"] != transaction_type:
            connection.close()

            flash(
                "Please select a valid category.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_transaction",
                    transaction_id=transaction_id
                )
            )

        connection.execute(
            """
            UPDATE transactions
            SET
                type = ?,
                category_id = ?,
                amount = ?,
                date = ?,
                description = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                transaction_type,
                category_id,
                amount,
                transaction_date,
                description or None,
                transaction_id,
                user_id
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Transaction updated successfully.",
            "success"
        )

        return redirect(url_for("transactions"))

    connection.close()

    return render_template(
        "edit_transaction.html",
        transaction=transaction,
        categories=categories
    )


@app.route(
    "/delete-transaction/<int:transaction_id>",
    methods=["POST"]
)
@login_required
def delete_transaction(transaction_id):
    user_id = session["user_id"]

    connection = get_db_connection()

    transaction = connection.execute(
        """
        SELECT id
        FROM transactions
        WHERE id = ?
        AND user_id = ?
        """,
        (transaction_id, user_id)
    ).fetchone()

    if transaction is None:
        connection.close()

        flash(
            "Transaction not found.",
            "error"
        )

        return redirect(url_for("transactions"))

    connection.execute(
        """
        DELETE FROM transactions
        WHERE id = ?
        AND user_id = ?
        """,
        (transaction_id, user_id)
    )

    connection.commit()
    connection.close()

    flash(
        "Transaction deleted successfully.",
        "success"
    )

    return redirect(url_for("transactions"))
@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]

    connection = get_db_connection()

    total_income = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        AND type = 'income'
        """,
        (user_id,)
    ).fetchone()["total"]

    total_expenses = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        AND type = 'expense'
        """,
        (user_id,)
    ).fetchone()["total"]

    category_expenses = connection.execute(
        """
        SELECT
            categories.name AS name,
            SUM(transactions.amount) AS total
        FROM transactions
        INNER JOIN categories
            ON categories.id = transactions.category_id
        WHERE transactions.user_id = ?
        AND transactions.type = 'expense'
        GROUP BY categories.id, categories.name
        ORDER BY total DESC
        """,
        (user_id,)
    ).fetchall()

    monthly_summary = connection.execute(
        """
        SELECT
            strftime('%Y-%m', date) AS month,
            SUM(
                CASE
                    WHEN type = 'income'
                    THEN amount
                    ELSE 0
                END
            ) AS income,
            SUM(
                CASE
                    WHEN type = 'expense'
                    THEN amount
                    ELSE 0
                END
            ) AS expenses
        FROM transactions
        WHERE user_id = ?
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month DESC
        LIMIT 12
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    return render_template(
        "reports.html",
        total_income=total_income,
        total_expenses=total_expenses,
        category_expenses=category_expenses,
        monthly_summary=monthly_summary
    )
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]

    connection = get_db_connection()

    user = connection.execute(
        """
        SELECT id, name, email, created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if not user:
        connection.close()
        session.clear()

        flash(
            "Your account could not be found.",
            "error"
        )

        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if not name or not email:
            connection.close()

            flash(
                "Name and email are required.",
                "error"
            )

            return redirect(url_for("profile"))

        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            AND id != ?
            """,
            (
                email,
                user_id
            )
        ).fetchone()

        if existing_user:
            connection.close()

            flash(
                "That email address is already in use.",
                "error"
            )

            return redirect(url_for("profile"))

        connection.execute(
            """
            UPDATE users
            SET name = ?, email = ?
            WHERE id = ?
            """,
            (
                name,
                email,
                user_id
            )
        )

        connection.commit()
        connection.close()

        session["user_name"] = name

        flash(
            "Profile updated successfully.",
            "success"
        )

        return redirect(url_for("profile"))

    connection.close()

    return render_template(
        "profile.html",
        user=user
    )
if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
