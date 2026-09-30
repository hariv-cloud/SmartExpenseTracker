# Smart Expense Tracker

A simple personal finance web application built with Flask, SQLite, HTML, CSS and JavaScript.

## Features

- User registration and login
- Secure password hashing
- Session-based authentication
- Add income and expense transactions
- Expense and income categories
- Search and filter transaction history by type, category and date range
- Edit and delete transactions
- Monthly spending budgets
- Dashboard with financial overview
- Reports with category and monthly charts
- Profile information management
- Responsive, clean interface

## Technologies

- Python 3
- Flask
- SQLite
- HTML5
- CSS3
- JavaScript
- Chart.js

## Project structure

```text
SmartExpenseTracker/
├── app.py
├── database.db
├── requirements.txt
├── README.md
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── images/
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── add_transaction.html
    ├── transactions.html
    ├── edit_transaction.html
    ├── budget.html
    ├── reports.html
    └── profile.html
```

## Setup

1. Open the project folder in VS Code.
2. Create/activate a Python virtual environment if needed.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
python app.py
```

5. Open the local Flask address shown in the terminal, normally `http://127.0.0.1:5000/`.

The SQLite database is created/updated automatically when the application starts.

## Security notes

- Passwords are stored as Werkzeug password hashes, not plaintext.
- User-owned records are checked using the logged-in session user ID.
- SQL statements use parameterized queries.
- The default secret key is suitable only for local development. For deployment, set a strong `SECRET_KEY` environment variable.

## Submission note

The Python virtual environment (`venv`) is intentionally not required in the project ZIP. It can be recreated from `requirements.txt`.
