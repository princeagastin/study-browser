from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, UniqueConstraint

from backend.models.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False, default="")
    url = Column(Text, nullable=False, default="")

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "title",
            name="uq_note_user_title",
        ),
    )