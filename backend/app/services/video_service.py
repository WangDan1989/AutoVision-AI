from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import JobStatus, TaskType
from app.core.config import settings
from app.db.models.frame import StoryboardFrame
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.db.models.video import VideoClip
from app.schemas.video import GenerateVideoRequest
from app.services.media_utils import ensure_binary, run_subprocess
from app.services.task_log_service import TaskLogService
from app.utils.files import to_relative_media_path
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class VideoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.task_log = TaskLogService(db)

    def _next_version(self, segment_id: str) -> int:
        return (
            self.db.query(VideoClip)
            .filter(VideoClip.segment_id == segment_id)
            .count()
            + 1
        )

    def _locked_frame(self, segment_id: str) -> StoryboardFrame:
        frame = self.db.scalar(
            select(StoryboardFrame).where(
                StoryboardFrame.segment_id == segment_id,
                StoryboardFrame.frame_type == "KEYFRAME_START",
                StoryboardFrame.is_locked == 1,
            )
        )
        if not frame:
            raise ValueError("当前分镜还没有锁定首帧，无法生成视频")
        return frame

    def generate_clip(self, segment: ScriptSegment, req: GenerateVideoRequest) -> VideoClip:
        frame = self._locked_frame(segment.id)
        task = self.task_log.create(
            project_id=segment.project_id,
            step_no=4,
            task_type=TaskType.VIDEO_RENDER.value,
            entity_type="segment",
            entity_id=segment.id,
            payload_json=req.model_dump_json(),
        )
        try:
            ffmpeg_bin = ensure_binary(settings.FFMPEG_BIN)
            now = utc_now_iso()
            version_no = self._next_version(segment.id)
            output_path = (
                settings.media_root_path
                / settings.VIDEOS_DIR
                / f"{segment.project_id}_{segment.id}_v{version_no}.mp4"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

            zoompan = (
                f"scale={req.width}:{req.height},"
                f"zoompan=z='min(zoom+0.0015,1.08)':"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"d={req.duration_sec * req.fps}:"
                f"s={req.width}x{req.height}:fps={req.fps},"
                "format=yuv420p"
            )
            run_subprocess(
                [
                    ffmpeg_bin,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    frame.image_path,
                    "-vf",
                    zoompan,
                    "-t",
                    str(req.duration_sec),
                    "-r",
                    str(req.fps),
                    "-pix_fmt",
                    "yuv420p",
                    str(output_path),
                ],
                "FFmpeg 生成视频失败",
            )

            clip = VideoClip(
                id=new_id(),
                project_id=segment.project_id,
                segment_id=segment.id,
                source_frame_id=frame.id,
                tail_frame_id=None,
                version_no=version_no,
                video_path=str(output_path.resolve()),
                duration_sec=float(req.duration_sec),
                fps=req.fps,
                width=req.width,
                height=req.height,
                status=JobStatus.COMPLETED.value,
                created_at=now,
                updated_at=now,
            )
            self.db.add(clip)

            project = self.db.get(Project, segment.project_id)
            if project:
                project.current_step_unlock = max(project.current_step_unlock, 4)
                project.updated_at = now

            self.db.commit()
            self.db.refresh(clip)
            self.task_log.complete(task, result_json=f'{{"video_clip_id":"{clip.id}"}}')
            return clip
        except Exception as exc:
            self.task_log.fail(task, str(exc), "VIDEO_RENDER_FAILED")
            raise

    def list_clips(self, project_id: str) -> list[dict]:
        items = list(
            self.db.scalars(
                select(VideoClip).where(VideoClip.project_id == project_id).order_by(VideoClip.created_at.desc())
            )
        )
        return [
            {
                "id": item.id,
                "segment_id": item.segment_id,
                "source_frame_id": item.source_frame_id,
                "version_no": item.version_no,
                "video_path": item.video_path,
                "video_url": f"/media/{to_relative_media_path(item.video_path)}?t={item.updated_at}" if item.video_path else "",
                "duration_sec": item.duration_sec,
                "fps": item.fps,
                "width": item.width,
                "height": item.height,
                "status": item.status,
                "updated_at": item.updated_at,
            }
            for item in items
        ]
