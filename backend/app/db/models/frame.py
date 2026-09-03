from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class StoryboardFrame(Base, TimestampMixin):
    __tablename__ = "storyboard_frames"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[str] = mapped_column(String, ForeignKey("script_segments.id", ondelete="CASCADE"), nullable=False)
    frame_type: Mapped[str] = mapped_column(String, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    image_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    thumb_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    negative_prompt_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    is_locked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_binding_snapshot_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
