from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AudioTrack(Base, TimestampMixin):
    __tablename__ = "audio_tracks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[str | None] = mapped_column(String, ForeignKey("script_segments.id", ondelete="CASCADE"))
    track_type: Mapped[str] = mapped_column(String, nullable=False)
    voice_profile: Mapped[str] = mapped_column(String, default="", nullable=False)
    audio_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
