from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    current_step_unlock: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    aspect_ratio: Mapped[str] = mapped_column(String, nullable=False, default="16:9")
    target_width: Mapped[int] = mapped_column(Integer, nullable=False, default=1280)
    target_height: Mapped[int] = mapped_column(Integer, nullable=False, default=720)
    fps: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    raw_script_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
