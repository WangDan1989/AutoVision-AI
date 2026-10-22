from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
for item in (str(BACKEND_DIR),):
    if item not in sys.path:
        sys.path.insert(0, item)

from app.core.config import settings
from app.core.enums import AssetType, JobStatus, ProjectStatus, TaskType
from app.db.base import Base
from app.db.models.asset import Asset, AssetBinding, AssetPreview
from app.db.models.audio import AudioTrack
from app.db.models.file_registry import FileRegistry
from app.db.models.frame import StoryboardFrame
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.db.models.task import TaskQueue
from app.db.models.video import VideoClip
from app.db.session import SessionLocal, engine
from app.schemas.project import CreateProjectRequest
from app.services.media_utils import ensure_binary
from app.services.project_service import ProjectService
from app.utils.files import to_relative_media_path
from app.utils.ids import new_id
from app.utils.time import utc_now_iso

DEMO_NAME = "AutoVision 离线示例项目"
DEMO_MARKER = "[DEMO_SEED]"
DEMO_WIDTH = 1280
DEMO_HEIGHT = 720
DEMO_FPS = 24


SEGMENTS = [
    {
        "scene_name": "旧书房夜谈",
        "location_canonical": "老宅书房",
        "visual_desc": "雨夜中的旧书房，暖黄台灯映着木桌，窗外偶尔闪过冷色雨光，空气里有轻微尘埃。",
        "camera_lang": "中景推近，先交代环境，再切主角近景。",
        "characters": ["lin_qiu", "mo_yan"],
        "dialogue_text": "林秋：你不是说这本手稿已经失踪十年了吗？",
        "narration_text": "林秋伸手翻开泛黄的手稿，灯光在纸页边缘微微颤动。",
        "emotion_tags": ["紧张", "压低声音"],
        "frame_title": "雨夜书房首帧",
        "frame_subtitle": "中景 / 暖灯 / 推近",
        "audio_text": "林秋：你不是说这本手稿已经失踪十年了吗？",
        "audio_hz": 392,
        "video_color": "royalblue",
    },
    {
        "scene_name": "走廊追踪",
        "location_canonical": "老宅走廊",
        "visual_desc": "长走廊被壁灯切出一段段明暗，尽头半掩的门后透出冷蓝色轮廓，脚步声回荡。",
        "camera_lang": "低机位跟拍，镜头略带手持感。",
        "characters": ["lin_qiu"],
        "dialogue_text": "林秋：等等，刚才那个人影是从这里过去的。",
        "narration_text": "她加快脚步，目光追向走廊深处那扇微微摆动的门。",
        "emotion_tags": ["警觉", "急促"],
        "frame_title": "走廊追踪首帧",
        "frame_subtitle": "跟拍 / 冷暖对比",
        "audio_text": "林秋：等等，刚才那个人影是从这里过去的。",
        "audio_hz": 440,
        "video_color": "midnightblue",
    },
    {
        "scene_name": "地下室真相",
        "location_canonical": "地下室",
        "visual_desc": "地下室里摆着旧投影机和一整面尘封胶片柜，中央桌上放着发光的金属装置。",
        "camera_lang": "先远景建立空间，再切装置特写。",
        "characters": ["lin_qiu", "mo_yan"],
        "dialogue_text": "莫言：别碰它，你现在看到的只是第一层记忆。",
        "narration_text": "金属装置忽明忽暗，冷色反光掠过两人的侧脸。",
        "emotion_tags": ["震惊", "克制"],
        "frame_title": "地下室真相首帧",
        "frame_subtitle": "远景 / 装置特写",
        "audio_text": "莫言：别碰它，你现在看到的只是第一层记忆。",
        "audio_hz": 330,
        "video_color": "teal",
    },
]


ASSETS = [
    {
        "asset_type": AssetType.CHARACTER.value,
        "name": "林秋",
        "canonical_name": "lin_qiu",
        "description": "女主角，28岁，短发，偏冷静理性，现代风衣造型。",
        "color": "#506d8b",
        "preview_labels": [
            ("cover", "角色定妆"),
            ("front", "正面半身"),
            ("side", "侧面轮廓"),
        ],
    },
    {
        "asset_type": AssetType.CHARACTER.value,
        "name": "莫言",
        "canonical_name": "mo_yan",
        "description": "神秘调查员，黑色长外套，面部情绪克制，气质偏冷。",
        "color": "#5e4f79",
        "preview_labels": [
            ("cover", "角色定妆"),
            ("front", "正面半身"),
            ("side", "侧面轮廓"),
        ],
    },
    {
        "asset_type": AssetType.SCENE.value,
        "name": "老宅书房",
        "canonical_name": "old_study",
        "description": "木桌、书柜、暖黄台灯和雨夜窗景组成的主要叙事空间。",
        "color": "#7a6348",
        "preview_labels": [
            ("cover", "场景总览"),
            ("lighting", "暖灯氛围"),
        ],
    },
    {
        "asset_type": AssetType.PROP.value,
        "name": "失踪手稿",
        "canonical_name": "missing_manuscript",
        "description": "泛黄纸页、旧牛皮封套、带有折角和批注的关键道具。",
        "color": "#7e6a45",
        "preview_labels": [
            ("cover", "道具封面"),
            ("detail", "纸页细节"),
        ],
    },
]


def ensure_storage_dirs() -> None:
    settings.media_root_path.mkdir(parents=True, exist_ok=True)
    for dirname in (
        settings.IMAGES_DIR,
        settings.VIDEOS_DIR,
        settings.AUDIO_DIR,
        settings.EXPORTS_DIR,
        settings.LORAS_DIR,
        settings.TEMP_DIR,
    ):
        (settings.media_root_path / dirname).mkdir(parents=True, exist_ok=True)


def write_text_svg(path: Path, title: str, subtitle: str, fill: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{DEMO_WIDTH}" height="{DEMO_HEIGHT}" viewBox="0 0 {DEMO_WIDTH} {DEMO_HEIGHT}">
  <rect width="100%" height="100%" fill="{fill}"/>
  <rect x="56" y="56" width="{DEMO_WIDTH - 112}" height="{DEMO_HEIGHT - 112}" rx="28" fill="rgba(10,16,24,0.18)" stroke="rgba(255,255,255,0.28)" stroke-width="2"/>
  <text x="96" y="180" fill="#ffffff" font-family="Segoe UI, Arial, sans-serif" font-size="54" font-weight="700">{title}</text>
  <text x="96" y="250" fill="rgba(255,255,255,0.88)" font-family="Segoe UI, Arial, sans-serif" font-size="26">{subtitle}</text>
  <text x="96" y="{DEMO_HEIGHT - 88}" fill="rgba(255,255,255,0.72)" font-family="Segoe UI, Arial, sans-serif" font-size="22">AutoVision-AI demo seed</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def write_tone_wav(path: Path, hz: int, seconds: float = 2.2, sample_rate: int = 24000) -> float:
    path.parent.mkdir(parents=True, exist_ok=True)
    amplitude = 0.25
    total_samples = int(seconds * sample_rate)
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for index in range(total_samples):
            envelope = min(1.0, index / max(1, sample_rate // 12))
            tail = min(1.0, (total_samples - index) / max(1, sample_rate // 8))
            value = amplitude * envelope * tail * math.sin(2 * math.pi * hz * index / sample_rate)
            frames.extend(struct.pack("<h", int(value * 32767)))
        wav_file.writeframes(frames)
    return round(seconds, 2)


def make_demo_clip(path: Path, color: str, duration_sec: float = 3.0) -> bool:
    try:
        ffmpeg_bin = ensure_binary(settings.FFMPEG_BIN)
    except RuntimeError:
        return False
    command = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={DEMO_WIDTH}x{DEMO_HEIGHT}:d={duration_sec}:r={DEMO_FPS}",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        return False
    return completed.returncode == 0 and path.exists()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_file(db, project_id: str, biz_type: str, biz_id: str, file_kind: str, path: Path, now: str) -> None:
    relative_path = to_relative_media_path(str(path))
    db.add(
        FileRegistry(
            id=new_id(),
            project_id=project_id,
            biz_type=biz_type,
            biz_id=biz_id,
            file_kind=file_kind,
            abs_path=str(path),
            relative_path=relative_path,
            sha256=sha256_of(path),
            size_bytes=path.stat().st_size,
            exists_flag=1,
            created_at=now,
            updated_at=now,
        )
    )


def add_task(db, project_id: str, step_no: int, task_type: str, entity_type: str, entity_id: str, result: dict, now: str) -> None:
    db.add(
        TaskQueue(
            id=new_id(),
            project_id=project_id,
            step_no=step_no,
            task_type=task_type,
            entity_type=entity_type,
            entity_id=entity_id,
            status=JobStatus.COMPLETED.value,
            priority=100,
            payload_json="{}",
            result_json=json.dumps(result, ensure_ascii=False),
            error_code="",
            error_message="",
            retry_count=0,
            worker_name="demo-seed",
            started_at=now,
            finished_at=now,
            created_at=now,
            updated_at=now,
        )
    )


def cleanup_existing_demo(db) -> int:
    items = list(
        db.scalars(
            select(Project).where(
                Project.name == DEMO_NAME,
            )
        )
    )
    removed = 0
    service = ProjectService(db)
    for project in items:
        service.delete_project(project)
        removed += 1
    return removed


def seed_demo_project(reset: bool = True) -> str:
    ensure_storage_dirs()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if reset:
            cleanup_existing_demo(db)

        now = utc_now_iso()
        project = ProjectService(db).create_project(
            CreateProjectRequest(
                name=DEMO_NAME,
                description=f"{DEMO_MARKER} 用于离线演示五步工作台的示例项目。",
                aspect_ratio="16:9",
                target_width=DEMO_WIDTH,
                target_height=DEMO_HEIGHT,
                fps=DEMO_FPS,
                genre_style="XUANYI_TUILI",
            )
        )
        project.status = ProjectStatus.COMPLETED.value
        project.current_step_unlock = 5
        project.raw_script_text = (
            "《雨夜手稿》示例章节：林秋在旧宅书房发现失踪手稿，随后沿走廊追踪神秘人影，"
            "最终在地下室发现装置与记忆投影。"
        )
        project.last_parse_result_json = json.dumps(
            {
                "segment_count": len(SEGMENTS),
                "character_count": 2,
                "scene_count": 2,
                "prop_count": 1,
                "seed_mode": "offline_demo",
            },
            ensure_ascii=False,
        )
        project.updated_at = now
        db.add(project)
        db.commit()
        db.refresh(project)

        image_root = settings.media_root_path / settings.IMAGES_DIR / "demo" / project.id
        audio_root = settings.media_root_path / settings.AUDIO_DIR / "demo" / project.id
        video_root = settings.media_root_path / settings.VIDEOS_DIR / "demo" / project.id
        image_root.mkdir(parents=True, exist_ok=True)
        audio_root.mkdir(parents=True, exist_ok=True)
        video_root.mkdir(parents=True, exist_ok=True)

        asset_id_map: dict[str, str] = {}
        for item in ASSETS:
            asset_now = utc_now_iso()
            asset_id = new_id()
            cover_path = image_root / f"asset_{item['canonical_name']}_cover.svg"
            write_text_svg(
                cover_path,
                item["name"],
                item["description"],
                item["color"],
            )
            asset = Asset(
                id=asset_id,
                project_id=project.id,
                asset_type=item["asset_type"],
                name=item["name"],
                canonical_name=item["canonical_name"],
                description=item["description"],
                cover_image_path=str(cover_path),
                consistency_config_json=json.dumps(
                    {
                        "lock_outfit": True,
                        "style_lora_name": "",
                        "style_lora_weight": 0.75,
                        "lighting_preset": "cinematic_soft",
                        "voice_preset": "demo_voice",
                    },
                    ensure_ascii=False,
                ),
                status=JobStatus.COMPLETED.value,
                created_at=asset_now,
                updated_at=asset_now,
            )
            db.add(asset)
            db.flush()
            register_file(db, project.id, "ASSET", asset.id, "cover", cover_path, asset_now)
            db.add(
                AssetBinding(
                    id=new_id(),
                    project_id=project.id,
                    asset_id=asset.id,
                    variant_id=None,
                    binding_mode="DEMO_REFERENCE",
                    lora_enabled=0,
                    lora_file_path="",
                    lora_weight=0.75,
                    trigger_word=item["canonical_name"],
                    ip_adapter_enabled=0,
                    ip_adapter_weight=0.6,
                    reference_image_paths_json=json.dumps([str(cover_path)], ensure_ascii=False),
                    decouple_clothes=1,
                    status=JobStatus.COMPLETED.value,
                    created_at=asset_now,
                    updated_at=asset_now,
                )
            )
            for role, label in item["preview_labels"]:
                preview_path = image_root / f"asset_{item['canonical_name']}_{role}.svg"
                write_text_svg(preview_path, item["name"], label, item["color"])
                preview = AssetPreview(
                    id=new_id(),
                    project_id=project.id,
                    asset_id=asset.id,
                    preview_role=role,
                    preview_label=label,
                    prompt_text=f"{item['name']} / {label}",
                    image_path=str(preview_path),
                    width=DEMO_WIDTH,
                    height=DEMO_HEIGHT,
                    camera_tag="mid-shot",
                    pose_tag="neutral",
                    lighting_tag="soft-key",
                    status=JobStatus.COMPLETED.value,
                    created_at=asset_now,
                    updated_at=asset_now,
                )
                db.add(preview)
                register_file(db, project.id, "ASSET_PREVIEW", preview.id, "image", preview_path, asset_now)
            asset_id_map[item["canonical_name"]] = asset.id

        for seq_no, segment_item in enumerate(SEGMENTS, start=1):
            segment_now = utc_now_iso()
            segment = ScriptSegment(
                id=new_id(),
                project_id=project.id,
                seq_no=seq_no,
                scene_name=segment_item["scene_name"],
                location_canonical=segment_item["location_canonical"],
                visual_desc=segment_item["visual_desc"],
                camera_lang=segment_item["camera_lang"],
                character_ids_json=json.dumps(
                    [asset_id_map[code] for code in segment_item["characters"]],
                    ensure_ascii=False,
                ),
                variant_refs_json="[]",
                dialogue_text=segment_item["dialogue_text"],
                narration_text=segment_item["narration_text"],
                emotion_tags_json=json.dumps(segment_item["emotion_tags"], ensure_ascii=False),
                status=JobStatus.COMPLETED.value,
                created_at=segment_now,
                updated_at=segment_now,
            )
            db.add(segment)
            db.flush()

            frame_path = image_root / f"segment_{seq_no:02d}_frame.svg"
            write_text_svg(
                frame_path,
                segment_item["frame_title"],
                segment_item["frame_subtitle"],
                "#394a63",
            )
            frame = StoryboardFrame(
                id=new_id(),
                project_id=project.id,
                segment_id=segment.id,
                frame_type="KEYFRAME",
                version_no=1,
                image_path=str(frame_path),
                thumb_path=str(frame_path),
                prompt_text=segment_item["visual_desc"],
                negative_prompt_text="low quality, blurry",
                width=DEMO_WIDTH,
                height=DEMO_HEIGHT,
                is_locked=1,
                source_binding_snapshot_json=json.dumps(
                    {"character_ids": segment_item["characters"]},
                    ensure_ascii=False,
                ),
                status=JobStatus.COMPLETED.value,
                created_at=segment_now,
                updated_at=segment_now,
            )
            db.add(frame)
            register_file(db, project.id, "FRAME", frame.id, "image", frame_path, segment_now)

            audio_path = audio_root / f"segment_{seq_no:02d}.wav"
            audio_duration = write_tone_wav(audio_path, segment_item["audio_hz"])
            track = AudioTrack(
                id=new_id(),
                project_id=project.id,
                segment_id=segment.id,
                track_type="NARRATION",
                voice_profile="demo_narration",
                audio_path=str(audio_path),
                duration_sec=audio_duration,
                text_content=segment_item["audio_text"],
                status=JobStatus.COMPLETED.value,
                created_at=segment_now,
                updated_at=segment_now,
            )
            db.add(track)
            register_file(db, project.id, "AUDIO", track.id, "audio", audio_path, segment_now)

            video_path = video_root / f"segment_{seq_no:02d}.mp4"
            if make_demo_clip(video_path, segment_item["video_color"]):
                clip = VideoClip(
                    id=new_id(),
                    project_id=project.id,
                    segment_id=segment.id,
                    source_frame_id=frame.id,
                    tail_frame_id=None,
                    version_no=1,
                    video_path=str(video_path),
                    duration_sec=3.0,
                    fps=DEMO_FPS,
                    width=DEMO_WIDTH,
                    height=DEMO_HEIGHT,
                    status=JobStatus.COMPLETED.value,
                    created_at=segment_now,
                    updated_at=segment_now,
                )
                db.add(clip)
                register_file(db, project.id, "VIDEO", clip.id, "video", video_path, segment_now)
                add_task(
                    db,
                    project.id,
                    4,
                    TaskType.VIDEO_RENDER.value,
                    "segment",
                    segment.id,
                    {"video_path": str(video_path)},
                    segment_now,
                )

            add_task(
                db,
                project.id,
                3,
                TaskType.KEYFRAME_RENDER.value,
                "segment",
                segment.id,
                {"frame_path": str(frame_path)},
                segment_now,
            )
            add_task(
                db,
                project.id,
                4,
                TaskType.TTS_RENDER.value,
                "segment",
                segment.id,
                {"audio_path": str(audio_path)},
                segment_now,
            )

        add_task(
            db,
            project.id,
            1,
            TaskType.SCRIPT_PARSE.value,
            "project",
            project.id,
            {"segment_count": len(SEGMENTS), "mode": "offline_demo"},
            now,
        )
        add_task(
            db,
            project.id,
            2,
            TaskType.ASSET_REBUILD.value,
            "project",
            project.id,
            {"asset_count": len(ASSETS), "mode": "offline_demo"},
            now,
        )

        db.commit()
        return project.id


def main() -> None:
    parser = argparse.ArgumentParser(description="写入一个离线可演示的 AutoVision 示例项目。")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="保留已有同名 demo 项目，不先清理。",
    )
    args = parser.parse_args()

    project_id = seed_demo_project(reset=not args.no_reset)
    print(f"已写入示例项目：{DEMO_NAME}")
    print(f"project_id={project_id}")
    print("现在可以启动后端与前端，在项目中心直接进入示例项目查看。")


if __name__ == "__main__":
    main()
