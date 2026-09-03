from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class VideoClip(Base, TimestampMixin):
    __tablename__ = "video_clips"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[str] = mapped_column(String, ForeignKey("script_segments.id", ondelete="CASCADE"), nullable=False)
    source_frame_id: Mapped[str] = mapped_column(String, ForeignKey("storyboard_frames.id", ondelete="CASCADE"), nullable=False)
    tail_frame_id: Mapped[str | None] = mapped_column(String, ForeignKey("storyboard_frames.id", ondelete="SET NULL"))
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    video_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fps: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
