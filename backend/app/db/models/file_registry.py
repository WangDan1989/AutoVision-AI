from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FileRegistry(Base, TimestampMixin):
    __tablename__ = "file_registry"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    biz_type: Mapped[str] = mapped_column(String, nullable=False)
    biz_id: Mapped[str] = mapped_column(String, nullable=False)
    file_kind: Mapped[str] = mapped_column(String, nullable=False)
    abs_path: Mapped[str] = mapped_column(String, nullable=False)
    relative_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exists_flag: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(String)
