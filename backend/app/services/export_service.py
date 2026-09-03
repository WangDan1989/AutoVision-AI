import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import JobStatus, TaskType
from app.db.models.audio import AudioTrack
from app.db.models.export import ExportJob
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.db.models.video import VideoClip
from app.schemas.export import GenerateExportRequest
from app.services.media_utils import ensure_binary, run_subprocess, write_concat_file
from app.services.task_log_service import TaskLogService
from app.utils.files import to_relative_media_path
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class ExportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.task_log = TaskLogService(db)

    def _segments(self, project_id: str) -> list[ScriptSegment]:
        return list(
            self.db.scalars(
                select(ScriptSegment).where(ScriptSegment.project_id == project_id).order_by(ScriptSegment.seq_no.asc())
            )
        )

    def _latest_clip(self, segment_id: str) -> VideoClip | None:
        clips = list(
            self.db.scalars(
                select(VideoClip).where(VideoClip.segment_id == segment_id).order_by(VideoClip.version_no.desc())
            )
        )
        return clips[0] if clips else None

    def _latest_track(self, segment_id: str) -> AudioTrack | None:
        tracks = list(
            self.db.scalars(
                select(AudioTrack).where(AudioTrack.segment_id == segment_id).order_by(AudioTrack.created_at.desc())
            )
        )
        return tracks[0] if tracks else None

    def _next_version(self, project_id: str) -> int:
        return (
            self.db.query(ExportJob)
            .filter(ExportJob.project_id == project_id)
            .count()
            + 1
        )

    def create_export(self, project: Project, req: GenerateExportRequest) -> ExportJob:
        task = self.task_log.create(
            project_id=project.id,
            step_no=5,
            task_type=TaskType.EXPORT_RENDER.value,
            entity_type="project",
            entity_id=project.id,
            payload_json=req.model_dump_json(),
        )
        try:
            ffmpeg_bin = ensure_binary(settings.FFMPEG_BIN)
            now = utc_now_iso()
            segments = self._segments(project.id)
            if not segments:
                raise ValueError("当前项目还没有分镜，无法导出")

            clip_paths: list[str] = []
            timeline_tracks: list[tuple[str, float]] = []
            compose_plan: list[dict] = []
            current_offset = 0.0
            for segment in segments:
                clip = self._latest_clip(segment.id)
                if not clip or not clip.video_path:
                    raise ValueError(f"分镜 #{segment.seq_no} 还没有可导出的视频片段")
                clip_paths.append(clip.video_path)
                track = self._latest_track(segment.id)
                if track and track.audio_path:
                    timeline_tracks.append((track.audio_path, current_offset))
                compose_plan.append(
                    {
                        "segment_id": segment.id,
                        "seq_no": segment.seq_no,
                        "video_clip_id": clip.id,
                        "audio_track_id": track.id if track else "",
                    }
                )
                current_offset += float(clip.duration_sec or 0.0)

            temp_dir = settings.media_root_path / settings.TEMP_DIR
            temp_dir.mkdir(parents=True, exist_ok=True)
            concat_file = temp_dir / f"{project.id}_export_concat.txt"
            merged_video = temp_dir / f"{project.id}_merged_video.mp4"
            write_concat_file(concat_file, clip_paths)

            run_subprocess(
                [
                    ffmpeg_bin,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c",
                    "copy",
                    str(merged_video),
                ],
                "FFmpeg 合并视频失败",
            )

            version_no = self._next_version(project.id)
            output_path = settings.media_root_path / settings.EXPORTS_DIR / f"{project.id}_export_v{version_no}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if timeline_tracks:
                command = [ffmpeg_bin, "-y", "-i", str(merged_video)]
                filter_parts: list[str] = []
                mix_inputs: list[str] = []
                for idx, (audio_file, offset_sec) in enumerate(timeline_tracks, start=1):
                    command.extend(["-i", audio_file])
                    delay_ms = int(max(offset_sec, 0.0) * 1000)
                    filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}[a{idx}]")
                    mix_inputs.append(f"[a{idx}]")
                filter_parts.append(
                    f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=longest:dropout_transition=0[aout]"
                )
                command.extend(
                    [
                        "-filter_complex",
                        ";".join(filter_parts),
                        "-map",
                        "0:v:0",
                        "-map",
                        "[aout]",
                        "-shortest",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        str(output_path),
                    ]
                )
                run_subprocess(command, "FFmpeg 合成音视频失败")
            else:
                run_subprocess(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(merged_video),
                        "-c",
                        "copy",
                        str(output_path),
                    ],
                    "FFmpeg 导出成片失败",
                )

            export = ExportJob(
                id=new_id(),
                project_id=project.id,
                version_no=version_no,
                output_path=str(output_path.resolve()),
                subtitle_enabled=1 if req.subtitle_enabled else 0,
                transition_enabled=1 if req.transition_enabled else 0,
                compose_plan_json=json.dumps(compose_plan, ensure_ascii=False),
                status=JobStatus.COMPLETED.value,
                started_at=now,
                finished_at=utc_now_iso(),
                created_at=now,
                updated_at=utc_now_iso(),
            )
            self.db.add(export)
            project.current_step_unlock = max(project.current_step_unlock, 5)
            project.updated_at = export.updated_at
            self.db.commit()
            self.db.refresh(export)
            self.task_log.complete(task, result_json=json.dumps({"export_job_id": export.id}, ensure_ascii=False))
            return export
        except Exception as exc:
            self.task_log.fail(task, str(exc), "EXPORT_RENDER_FAILED")
            raise

    def list_exports(self, project_id: str) -> list[dict]:
        items = list(
            self.db.scalars(
                select(ExportJob).where(ExportJob.project_id == project_id).order_by(ExportJob.created_at.desc())
            )
        )
        return [
            {
                "id": item.id,
                "version_no": item.version_no,
                "output_path": item.output_path,
                "output_url": f"/media/{to_relative_media_path(item.output_path)}?t={item.updated_at}" if item.output_path else "",
                "subtitle_enabled": bool(item.subtitle_enabled),
                "transition_enabled": bool(item.transition_enabled),
                "compose_plan": json.loads(item.compose_plan_json or "[]"),
                "status": item.status,
                "updated_at": item.updated_at,
            }
            for item in items
        ]
