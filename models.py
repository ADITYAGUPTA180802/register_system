from datetime import datetime, date, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Date, DateTime, Text, ForeignKey

class Base(DeclarativeBase):
    pass

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    asset_tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # e.g. LAP-001
    category: Mapped[str] = mapped_column(String(30), default="Laptop")             # Laptop/Printer/...
    brand: Mapped[str] = mapped_column(String(60), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    serial_no: Mapped[str] = mapped_column(String(80), default="")

    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="In Stock")  # In Stock/Assigned/Repair/Retired
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    location: Mapped[str] = mapped_column(String(120), default="")

    notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    assignments = relationship("Assignment", back_populates="asset", cascade="all, delete-orphan")

    def to_dict(self):
        today = date.today()
        expired = False
        expiring_soon = False
        if self.warranty_end:
            expired = self.warranty_end < today
            expiring_soon = (not expired) and (self.warranty_end <= (today.replace() + __import__("datetime").timedelta(days=30)))

        return {
            "id": self.id,
            "asset_tag": self.asset_tag,
            "category": self.category,
            "brand": self.brand,
            "model": self.model,
            "serial_no": self.serial_no,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "warranty_end": self.warranty_end.isoformat() if self.warranty_end else None,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "location": self.location,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "warranty_expired": expired,
            "warranty_expiring_30d": expiring_soon,
        }

class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)

    assigned_to: Mapped[str] = mapped_column(String(120), nullable=False)
    assigned_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    asset = relationship("Asset", back_populates="assignments")

    def to_dict(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "assigned_to": self.assigned_to,
            "assigned_on": self.assigned_on.isoformat(),
            "returned_on": self.returned_on.isoformat() if self.returned_on else None,
            "notes": self.notes,
        }
