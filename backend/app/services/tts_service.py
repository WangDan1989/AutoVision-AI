import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import JobStatus, TaskType
from app.db.models.audio import AudioTrack
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.schemas.audio import GenerateAudioRequest
from app.services.media_utils import probe_duration
from app.services.task_log_service import TaskLogService
from app.utils.files import to_relative_media_path
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class TTSService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.task_log = TaskLogService(db)

    def _resolve_text(self, segment: ScriptSegment, req: GenerateAudioRequest) -> str:
        text = req.text_content.strip()
        if text:
            return text
        return (segment.dialogue_text or "").strip() or (segment.narration_text or "").strip() or (segment.visual_desc or "").strip()

    def _next_version_count(self, project_id: str, segment_id: str | None) -> int:
        return (
            self.db.query(AudioTrack)
            .filter(AudioTrack.project_id == project_id, AudioTrack.segment_id == segment_id)
            .count()
            + 1
        )

    async def _generate_with_http(self, text: str, output_path: Path, voice: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    settings.TTS_BASE_URL,
                    json={"text": text, "voice": voice},
                )
                response.raise_for_status()
                output_path.write_bytes(response.content)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接 HTTP TTS 服务，请确认已启动并检查 TTS_BASE_URL={settings.TTS_BASE_URL}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("HTTP TTS 调用超时，请检查服务负载或网络状态") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"HTTP TTS 接口返回异常 HTTP {exc.response.status_code}，请检查服务入参与鉴权配置"
            ) from exc

    async def _generate_with_edge_tts(self, text: str, output_path: Path, voice: str) -> None:
        command = [
            "edge-tts",
            "--voice",
            voice,
            "--text",
            text,
            "--write-media",
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"edge-tts 生成音频失败，请检查网络、voice 配置或 edge-tts 安装状态: {stderr or 'unknown error'}")

    async def generate_segment_audio(self, segment: ScriptSegment, req: GenerateAudioRequest) -> AudioTrack:
        text = self._resolve_text(segment, req)
        if not text:
            raise ValueError("当前分镜没有可用于 TTS 的文本")

        task = self.task_log.create(
            project_id=segment.project_id,
            step_no=4,
            task_type=TaskType.TTS_RENDER.value,
            entity_type="segment",
            entity_id=segment.id,
            payload_json=req.model_dump_json(),
        )
        try:
            now = utc_now_iso()
            version_no = self._next_version_count(segment.project_id, segment.id)
            voice = req.voice_profile.strip() or settings.TTS_VOICE
            output_path = (
                settings.media_root_path
                / settings.AUDIO_DIR
                / f"{segment.project_id}_{segment.id}_v{version_no}.mp3"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if settings.TTS_PROVIDER == "http":
                if not settings.TTS_BASE_URL:
                    raise ValueError("TTS_PROVIDER=http 时必须配置 TTS_BASE_URL")
                await self._generate_with_http(text, output_path, voice)
            else:
                await self._generate_with_edge_tts(text, output_path, voice)

            duration = probe_duration(str(output_path.resolve()))
            track = AudioTrack(
                id=new_id(),
                project_id=segment.project_id,
                segment_id=segment.id,
                track_type=req.track_type,
                voice_profile=voice,
                audio_path=str(output_path.resolve()),
                duration_sec=duration,
                text_content=text,
                status=JobStatus.COMPLETED.value,
                created_at=now,
                updated_at=now,
            )
            self.db.add(track)

            project = self.db.get(Project, segment.project_id)
            if project:
                project.current_step_unlock = max(project.current_step_unlock, 4)
                project.updated_at = now

            self.db.commit()
            self.db.refresh(track)
            self.task_log.complete(task, result_json=json.dumps({"audio_track_id": track.id}, ensure_ascii=False))
            return track
        except Exception as exc:
            self.task_log.fail(task, str(exc), "TTS_RENDER_FAILED")
            raise

    def list_tracks(self, project_id: str) -> list[dict]:
        items = list(
            self.db.scalars(
                select(AudioTrack).where(AudioTrack.project_id == project_id).order_by(AudioTrack.created_at.desc())
            )
        )
        return [
            {
                "id": item.id,
                "segment_id": item.segment_id,
                "track_type": item.track_type,
                "voice_profile": item.voice_profile,
                "audio_path": item.audio_path,
                "audio_url": f"/media/{to_relative_media_path(item.audio_path)}?t={item.updated_at}" if item.audio_path else "",
                "duration_sec": item.duration_sec,
                "text_content": item.text_content,
                "status": item.status,
                "updated_at": item.updated_at,
            }
            for item in items
        ]
