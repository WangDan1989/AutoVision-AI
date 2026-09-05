import json
import os
import sys
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
    @staticmethod
    def _ffmpeg_subtitles_filter_arg(srt_basename: str) -> str:
        base = srt_basename.replace("'", r"'\''")
        style_chunks = [
            "FontName=Microsoft YaHei",
            "FontSize=24",
            "PrimaryColour=&H00FFFFFF",
            "OutlineColour=&H00000000",
            "BackColour=&H00000000",
            "Bold=0",
            "Italic=0",
            "BorderStyle=1",
            "Outline=1",
            "Shadow=1",
            "Alignment=2",
            "MarginV=40",
            "Spacing=0",
            "Angle=0",
        ]
        force_style = ",".join(style_chunks)
        return f"subtitles='{base}':charenc=utf-8:force_style='{force_style}'"

    @staticmethod
    def _fallback_subtitle_enabled(req: GenerateExportRequest) -> bool:
        if not getattr(req, "subtitle_enabled", True):
            return False
        if sys.platform.startswith("win"):
            windir = os.environ.get("WINDIR") or r"C:\Windows"
            candidates = [
                Path(windir) / "Fonts" / "msyh.ttc",
                Path(windir) / "Fonts" / "msyhbd.ttc",
                Path(windir) / "Fonts" / "simhei.ttf",
                Path(windir) / "Fonts" / "simsun.ttc",
            ]
            return any(p.exists() for p in candidates)
        return True

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

    def _subtitle_text(self, segment: ScriptSegment) -> str:
        dialogue = (segment.dialogue_text or "").strip()
        narration = (segment.narration_text or "").strip()
        if dialogue and narration:
            return f"{dialogue}\n{narration}"
        return dialogue or narration

    def _format_srt_time(self, seconds: float) -> str:
        total_ms = max(int(round(seconds * 1000)), 0)
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        secs = (total_ms % 60_000) // 1000
        millis = total_ms % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _write_srt(self, srt_path: Path, subtitles: list[dict]) -> None:
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for idx, item in enumerate(subtitles, start=1):
            text = (item.get("text") or "").strip()
            if not text:
                continue
            lines.append(str(idx))
            lines.append(
                f"{self._format_srt_time(float(item['start_sec']))} --> {self._format_srt_time(float(item['end_sec']))}"
            )
            lines.append(text)
            lines.append("")
        srt_path.write_text("\n".join(lines), encoding="utf-8")

    def _subtitle_overrides(self, req: GenerateExportRequest) -> dict[str, dict]:
        overrides: dict[str, dict] = {}
        for item in req.subtitle_items:
            if item.end_sec < item.start_sec:
                raise ValueError("字幕结束时间不能早于开始时间")
            overrides[item.segment_id] = {
                "start_sec": float(item.start_sec),
                "end_sec": float(item.end_sec),
                "text": item.text,
            }
        return overrides

    def _build_transition_video(
        self,
        ffmpeg_bin: str,
        clips: list[dict],
        output_path: Path,
        transition_sec: float,
    ) -> None:
        command = [ffmpeg_bin, "-y"]
        for clip in clips:
            command.extend(["-i", clip["video_path"]])

        filter_parts: list[str] = []
        last_label = "[0:v]"
        elapsed = float(clips[0]["duration_sec"])
        for idx in range(1, len(clips)):
            next_label = f"[{idx}:v]"
            out_label = f"[v{idx}]"
            offset = max(elapsed - transition_sec, 0.0)
            filter_parts.append(
                f"{last_label}{next_label}xfade=transition=fade:duration={transition_sec}:offset={offset}{out_label}"
            )
            last_label = out_label
            elapsed += float(clips[idx]["duration_sec"]) - transition_sec

        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                last_label,
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )
        run_subprocess(command, "FFmpeg 生成转场视频失败")

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

            transition_sec = max(float(settings.EXPORT_TRANSITION_SEC), 0.0) if req.transition_enabled else 0.0
            subtitle_overrides = self._subtitle_overrides(req)
            clip_items: list[dict] = []
            timeline_tracks: list[tuple[str, float]] = []
            subtitle_items: list[dict] = []
            compose_plan: list[dict] = []
            current_offset = 0.0
            for segment in segments:
                clip = self._latest_clip(segment.id)
                if not clip or not clip.video_path:
                    raise ValueError(f"分镜 #{segment.seq_no} 还没有可导出的视频片段")
                clip_duration = float(clip.duration_sec or 0.0)
                clip_start = max(current_offset, 0.0)
                clip_end = clip_start + clip_duration
                clip_items.append(
                    {
                        "segment_id": segment.id,
                        "video_clip_id": clip.id,
                        "video_path": clip.video_path,
                        "duration_sec": clip_duration,
                        "start_sec": clip_start,
                        "end_sec": clip_end,
                    }
                )
                track = self._latest_track(segment.id)
                if track and track.audio_path:
                    timeline_tracks.append((track.audio_path, clip_start))
                subtitle_text = self._subtitle_text(segment)
                subtitle_override = subtitle_overrides.get(segment.id)
                subtitle_start = clip_start
                subtitle_end = clip_end
                if subtitle_override:
                    subtitle_text = str(subtitle_override.get("text") or "")
                    subtitle_start = float(subtitle_override.get("start_sec", clip_start))
                    subtitle_end = float(subtitle_override.get("end_sec", clip_end))
                    if subtitle_end < subtitle_start:
                        raise ValueError(f"分镜 #{segment.seq_no} 的字幕结束时间不能早于开始时间")
                if subtitle_text:
                    subtitle_items.append(
                        {
                            "segment_id": segment.id,
                            "start_sec": subtitle_start,
                            "end_sec": subtitle_end,
                            "text": subtitle_text,
                        }
                    )
                compose_plan.append(
                    {
                        "segment_id": segment.id,
                        "seq_no": segment.seq_no,
                        "video_clip_id": clip.id,
                        "audio_track_id": track.id if track else "",
                        "start_sec": round(clip_start, 3),
                        "end_sec": round(clip_end, 3),
                        "subtitle_text": subtitle_text,
                        "subtitle_start_sec": round(subtitle_start, 3) if subtitle_text else 0.0,
                        "subtitle_end_sec": round(subtitle_end, 3) if subtitle_text else 0.0,
                    }
                )
                current_offset += clip_duration - transition_sec if transition_sec > 0 else clip_duration

            temp_dir = settings.media_root_path / settings.TEMP_DIR
            temp_dir.mkdir(parents=True, exist_ok=True)
            concat_file = temp_dir / f"{project.id}_export_concat.txt"
            merged_video = temp_dir / f"{project.id}_merged_video.mp4"
            if req.transition_enabled and len(clip_items) > 1 and transition_sec > 0:
                self._build_transition_video(ffmpeg_bin, clip_items, merged_video, transition_sec)
            else:
                write_concat_file(concat_file, [item["video_path"] for item in clip_items])
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
            av_output_path = temp_dir / f"{project.id}_export_av_v{version_no}.mp4"

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
                        str(av_output_path),
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
                        str(av_output_path),
                    ],
                    "FFmpeg 导出成片失败",
                )

            subtitle_path = temp_dir / f"{project.id}_export_v{version_no}.srt"
            srt_basename = subtitle_path.name
            effective_subtitle_enabled = (
                req.subtitle_enabled
                and subtitle_items
                and self._fallback_subtitle_enabled(req)
            )
            actual_subtitle_flag = False
            if effective_subtitle_enabled:
                self._write_srt(subtitle_path, subtitle_items)
                try:
                    run_subprocess(
                        [
                            ffmpeg_bin,
                            "-y",
                            "-i",
                            str(av_output_path),
                            "-vf",
                            self._ffmpeg_subtitles_filter_arg(srt_basename),
                            "-c:a",
                            "copy",
                            str(output_path),
                        ],
                        "FFmpeg 烧录字幕失败",
                        cwd=temp_dir,
                    )
                    actual_subtitle_flag = True
                except Exception:
                    run_subprocess(
                        [
                            ffmpeg_bin,
                            "-y",
                            "-i",
                            str(av_output_path),
                            "-c",
                            "copy",
                            str(output_path),
                        ],
                        "FFmpeg 字幕烧录失败后的 fallback 输出最终成片失败",
                    )
            else:
                run_subprocess(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(av_output_path),
                        "-c",
                        "copy",
                        str(output_path),
                    ],
                    "FFmpeg 输出最终成片失败",
                )

            export = ExportJob(
                id=new_id(),
                project_id=project.id,
                version_no=version_no,
                output_path=str(output_path.resolve()),
                subtitle_enabled=1 if actual_subtitle_flag else 0,
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
            if isinstance(exc, RuntimeError) and str(exc).startswith("未找到可执行文件："):
                raise RuntimeError(
                    f"未找到 FFmpeg 可执行文件，请检查 FFMPEG_BIN={settings.FFMPEG_BIN} 或确认 ffmpeg 已加入 PATH"
                ) from exc
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
