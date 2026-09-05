from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ScriptSegment(Base, TimestampMixin):
    __tablename__ = "script_segments"
    __table_args__ = (UniqueConstraint("project_id", "seq_no", name="uq_segment_project_seq"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_name: Mapped[str] = mapped_column(String, default="", nullable=False)
    location_canonical: Mapped[str] = mapped_column(String, default="", nullable=False)
    visual_desc: Mapped[str] = mapped_column(Text, nullable=False)
    camera_lang: Mapped[str] = mapped_column(String, default="", nullable=False)
    character_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    variant_refs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    dialogue_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    narration_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    emotion_tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
