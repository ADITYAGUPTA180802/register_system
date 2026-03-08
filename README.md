# Asset Register System (Python + Frontend + Backend)

## Features
- Add / Edit / Delete assets (Laptop, Printer, etc.)
- Warranty tracking (expired + expiring within 30 days)
- Assign/Return assets with full assignment history (assigned-to tracking)
- Dashboard stats
- Export Assets and Assignments to CSV

## Tech
- Backend: Flask + SQLAlchemy
- DB: SQLite (local file `asset_register.db`)
- Frontend: HTML + Bootstrap + Vanilla JS (Fetch API)

## Run (Windows / Mac / Linux)

### 1) Create venv
Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Mac/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Run server
```bash
python app.py
```

Open:
http://127.0.0.1:5000

## Notes
- Warranty dates use `YYYY-MM-DD`
- Assignment history is in the "History" button for each asset.
