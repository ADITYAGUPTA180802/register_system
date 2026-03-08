from datetime import datetime, date, timezone, timedelta
import csv
import io

from flask import Flask, jsonify, request, render_template, send_file
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from db import engine, SessionLocal
from models import Base, Asset, Assignment

app = Flask(__name__)
Base.metadata.create_all(bind=engine)

VALID_CATEGORIES = ["Laptop", "Printer", "Monitor", "Desktop", "Networking", "Other"]
VALID_STATUSES = ["In Stock", "Assigned", "Repair", "Retired"]

def now_utc():
    return datetime.now(timezone.utc)

def parse_date(s: str | None):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)   # YYYY-MM-DD
    except ValueError:
        return None

def get_db() -> Session:
    return SessionLocal()

@app.get("/")
def home():
    return render_template("index.html")

# ---------- API: Assets ----------
@app.get("/api/assets")
def list_assets():
    status = (request.args.get("status") or "").strip()
    category = (request.args.get("category") or "").strip()
    search = (request.args.get("search") or "").strip().lower()
    warranty = (request.args.get("warranty") or "").strip()  # expiring / expired

    with get_db() as db:
        stmt = select(Asset).order_by(desc(Asset.updated_at))
        if status:
            stmt = stmt.where(Asset.status == status)
        if category:
            stmt = stmt.where(Asset.category == category)

        assets = db.execute(stmt).scalars().all()
        items = [a.to_dict() for a in assets]

        if search:
            def match(a):
                return (
                    search in (a["asset_tag"] or "").lower()
                    or search in (a["brand"] or "").lower()
                    or search in (a["model"] or "").lower()
                    or search in (a["serial_no"] or "").lower()
                    or search in (a["assigned_to"] or "").lower()
                    or search in (a["location"] or "").lower()
                )
            items = [a for a in items if match(a)]

        if warranty == "expiring":
            items = [a for a in items if a["warranty_expiring_30d"]]
        elif warranty == "expired":
            items = [a for a in items if a["warranty_expired"]]

        return jsonify({"items": items})

@app.post("/api/assets")
def create_asset():
    data = request.get_json(force=True) or {}
    asset_tag = (data.get("asset_tag") or "").strip()
    if not asset_tag:
        return jsonify({"error": "asset_tag is required (example: LAP-001)"}), 400

    category = (data.get("category") or "Laptop").strip()
    if category not in VALID_CATEGORIES:
        category = "Other"

    status = (data.get("status") or "In Stock").strip()
    if status not in VALID_STATUSES:
        status = "In Stock"

    asset = Asset(
        asset_tag=asset_tag,
        category=category,
        brand=(data.get("brand") or "").strip(),
        model=(data.get("model") or "").strip(),
        serial_no=(data.get("serial_no") or "").strip(),
        purchase_date=parse_date(data.get("purchase_date")),
        warranty_end=parse_date(data.get("warranty_end")),
        status=status,
        assigned_to=(data.get("assigned_to") or "").strip(),
        location=(data.get("location") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        created_at=now_utc(),
        updated_at=now_utc(),
    )

    with get_db() as db:
        # uniqueness check
        existing = db.execute(select(Asset).where(Asset.asset_tag == asset.asset_tag)).scalar_one_or_none()
        if existing:
            return jsonify({"error": "asset_tag already exists. Use a unique tag like LAP-002"}), 400

        db.add(asset)
        db.commit()
        db.refresh(asset)
        return jsonify(asset.to_dict()), 201

@app.patch("/api/assets/<int:asset_id>")
def update_asset(asset_id: int):
    data = request.get_json(force=True) or {}

    with get_db() as db:
        asset = db.get(Asset, asset_id)
        if not asset:
            return jsonify({"error": "asset not found"}), 404

        if "asset_tag" in data:
            new_tag = (data.get("asset_tag") or "").strip()
            if new_tag and new_tag != asset.asset_tag:
                exists = db.execute(select(Asset).where(Asset.asset_tag == new_tag)).scalar_one_or_none()
                if exists:
                    return jsonify({"error": "asset_tag already exists"}), 400
                asset.asset_tag = new_tag

        if "category" in data:
            c = (data.get("category") or "").strip()
            if c in VALID_CATEGORIES:
                asset.category = c

        if "status" in data:
            s = (data.get("status") or "").strip()
            if s in VALID_STATUSES:
                asset.status = s
                if s != "Assigned":
                    # if not assigned, clear current assigned_to optionally
                    pass

        for f in ["brand","model","serial_no","assigned_to","location","notes"]:
            if f in data:
                setattr(asset, f, (data.get(f) or "").strip())

        if "purchase_date" in data:
            asset.purchase_date = parse_date(data.get("purchase_date"))
        if "warranty_end" in data:
            asset.warranty_end = parse_date(data.get("warranty_end"))

        asset.updated_at = now_utc()
        db.commit()
        db.refresh(asset)
        return jsonify(asset.to_dict())

@app.delete("/api/assets/<int:asset_id>")
def delete_asset(asset_id: int):
    with get_db() as db:
        asset = db.get(Asset, asset_id)
        if not asset:
            return jsonify({"error": "asset not found"}), 404
        db.delete(asset)
        db.commit()
        return jsonify({"ok": True})

# ---------- API: Assign / Return (History) ----------
@app.get("/api/assets/<int:asset_id>/history")
def asset_history(asset_id: int):
    with get_db() as db:
        asset = db.get(Asset, asset_id)
        if not asset:
            return jsonify({"error": "asset not found"}), 404

        rows = db.execute(
            select(Assignment).where(Assignment.asset_id == asset_id).order_by(desc(Assignment.assigned_on))
        ).scalars().all()

        return jsonify({
            "asset": asset.to_dict(),
            "history": [r.to_dict() for r in rows],
        })

@app.post("/api/assets/<int:asset_id>/assign")
def assign_asset(asset_id: int):
    data = request.get_json(force=True) or {}
    assigned_to = (data.get("assigned_to") or "").strip()
    if not assigned_to:
        return jsonify({"error": "assigned_to is required"}), 400

    notes = (data.get("notes") or "").strip()
    location = (data.get("location") or "").strip()

    with get_db() as db:
        asset = db.get(Asset, asset_id)
        if not asset:
            return jsonify({"error": "asset not found"}), 404

        # Close any open assignment automatically (safety)
        open_asg = db.execute(
            select(Assignment).where(Assignment.asset_id == asset_id, Assignment.returned_on.is_(None))
        ).scalar_one_or_none()
        if open_asg:
            open_asg.returned_on = now_utc()

        asg = Assignment(
            asset_id=asset_id,
            assigned_to=assigned_to,
            assigned_on=now_utc(),
            returned_on=None,
            notes=notes,
        )
        db.add(asg)

        asset.assigned_to = assigned_to
        if location:
            asset.location = location
        asset.status = "Assigned"
        asset.updated_at = now_utc()

        db.commit()
        db.refresh(asset)
        return jsonify({"asset": asset.to_dict(), "assignment": asg.to_dict()}), 201

@app.post("/api/assets/<int:asset_id>/return")
def return_asset(asset_id: int):
    data = request.get_json(force=True) or {}
    notes = (data.get("notes") or "").strip()

    with get_db() as db:
        asset = db.get(Asset, asset_id)
        if not asset:
            return jsonify({"error": "asset not found"}), 404

        open_asg = db.execute(
            select(Assignment).where(Assignment.asset_id == asset_id, Assignment.returned_on.is_(None))
        ).scalar_one_or_none()
        if not open_asg:
            return jsonify({"error": "No active assignment found for this asset"}), 400

        open_asg.returned_on = now_utc()
        if notes:
            open_asg.notes = (open_asg.notes + "\n" + notes).strip()

        asset.status = "In Stock"
        asset.assigned_to = ""
        asset.updated_at = now_utc()

        db.commit()
        db.refresh(asset)
        return jsonify({"asset": asset.to_dict(), "assignment": open_asg.to_dict()})

# ---------- API: Reports ----------
@app.get("/api/reports")
def reports():
    today = date.today()
    expiring_limit = today + timedelta(days=30)

    with get_db() as db:
        total = db.scalar(select(func.count(Asset.id))) or 0

        by_status_rows = db.execute(
            select(Asset.status, func.count(Asset.id)).group_by(Asset.status)
        ).all()
        by_status = {s: int(c) for s, c in by_status_rows}

        expired = db.scalar(
            select(func.count(Asset.id)).where(Asset.warranty_end.is_not(None), Asset.warranty_end < today)
        ) or 0

        expiring = db.scalar(
            select(func.count(Asset.id)).where(
                Asset.warranty_end.is_not(None),
                Asset.warranty_end >= today,
                Asset.warranty_end <= expiring_limit
            )
        ) or 0

        assigned = by_status.get("Assigned", 0)

        return jsonify({
            "total_assets": int(total),
            "by_status": by_status,
            "assigned_now": int(assigned),
            "warranty_expired": int(expired),
            "warranty_expiring_30d": int(expiring),
            "categories": VALID_CATEGORIES,
            "statuses": VALID_STATUSES,
        })

@app.get("/api/reports/export/assets")
def export_assets_csv():
    with get_db() as db:
        assets = db.execute(select(Asset).order_by(desc(Asset.updated_at))).scalars().all()
        rows = [a.to_dict() for a in assets]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID","Asset Tag","Category","Brand","Model","Serial No",
        "Purchase Date","Warranty End","Status","Assigned To","Location","Notes","Updated At"
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["asset_tag"], r["category"], r["brand"], r["model"], r["serial_no"],
            r["purchase_date"] or "", r["warranty_end"] or "",
            r["status"], r["assigned_to"], r["location"], (r["notes"] or "").replace("\n", " "),
            r["updated_at"]
        ])

    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    mem.seek(0)
    filename = f"assets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype="text/csv")

@app.get("/api/reports/export/assignments")
def export_assignments_csv():
    with get_db() as db:
        asgs = db.execute(select(Assignment).order_by(desc(Assignment.assigned_on))).scalars().all()
        rows = [a.to_dict() for a in asgs]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Asset ID","Assigned To","Assigned On","Returned On","Notes"])
    for r in rows:
        writer.writerow([
            r["id"], r["asset_id"], r["assigned_to"],
            r["assigned_on"], r["returned_on"] or "",
            (r["notes"] or "").replace("\n", " ")
        ])

    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    mem.seek(0)
    filename = f"assignments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype="text/csv")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
