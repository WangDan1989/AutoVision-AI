from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("project_id", "asset_type", "canonical_name", name="uq_asset_project_type_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cover_image_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    consistency_config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class AssetVariant(Base, TimestampMixin):
    __tablename__ = "asset_variants"
    __table_args__ = (UniqueConstraint("project_id", "asset_id", "variant_code", name="uq_variant_project_asset_code"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    variant_name: Mapped[str] = mapped_column(String, nullable=False)
    variant_code: Mapped[str] = mapped_column(String, nullable=False)
    clothes_prompt_override: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class AssetBinding(Base, TimestampMixin):
    __tablename__ = "asset_bindings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[str | None] = mapped_column(String, ForeignKey("asset_variants.id", ondelete="SET NULL"))
    binding_mode: Mapped[str] = mapped_column(String, nullable=False)
    lora_enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lora_file_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    lora_weight: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    trigger_word: Mapped[str] = mapped_column(String, default="", nullable=False)
    ip_adapter_enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ip_adapter_weight: Mapped[float] = mapped_column(Float, default=0.60, nullable=False)
    reference_image_paths_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    decouple_clothes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class AssetPreview(Base, TimestampMixin):
    __tablename__ = "asset_previews"
    __table_args__ = (UniqueConstraint("asset_id", "preview_role", name="uq_preview_asset_role"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    preview_role: Mapped[str] = mapped_column(String, nullable=False)
    preview_label: Mapped[str] = mapped_column(String, default="", nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    camera_tag: Mapped[str] = mapped_column(String, default="", nullable=False)
    pose_tag: Mapped[str] = mapped_column(String, default="", nullable=False)
    lighting_tag: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
