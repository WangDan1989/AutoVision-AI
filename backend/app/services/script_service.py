import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import JobStatus, ProjectStatus, TaskType
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.services.ollama_service import OllamaService
from app.services.task_log_service import TaskLogService
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class ScriptService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ollama = OllamaService()
        self.task_log = TaskLogService(db)

    async def parse_and_save(self, project: Project, raw_script_text: str) -> dict:
        task = self.task_log.create(
            project_id=project.id,
            step_no=1,
            task_type=TaskType.SCRIPT_PARSE.value,
            entity_type="project",
            entity_id=project.id,
            payload_json=json.dumps({"raw_script_text": raw_script_text}, ensure_ascii=False),
        )
        try:
            result = await self.ollama.parse_script(raw_script_text)
            self.db.execute(delete(ScriptSegment).where(ScriptSegment.project_id == project.id))
            now = utc_now_iso()
            for index, item in enumerate(result["segments"], start=1):
                self.db.add(
                    ScriptSegment(
                        id=new_id(),
                        project_id=project.id,
                        seq_no=index,
                        scene_name=item["scene_name"],
                        visual_desc=item["visual_desc"],
                        camera_lang=item["camera_lang"],
                        character_ids_json=json.dumps(item["character_ids"], ensure_ascii=False),
                        variant_refs_json=json.dumps(item["variant_refs"], ensure_ascii=False),
                        dialogue_text=item["dialogue_text"],
                        narration_text=item["narration_text"],
                        emotion_tags_json=json.dumps(item["emotion_tags"], ensure_ascii=False),
                        status=JobStatus.COMPLETED.value,
                        created_at=now,
                        updated_at=now,
                    )
                )

            project.raw_script_text = raw_script_text
            project.status = ProjectStatus.RUNNING.value
            project.current_step_unlock = max(project.current_step_unlock, 2)
            project.updated_at = now
            self.db.commit()
            self.task_log.complete(task, json.dumps(result, ensure_ascii=False))
            return result
        except Exception as exc:
            self.task_log.fail(task, str(exc), "SCRIPT_PARSE_FAILED")
            raise

    def list_segments(self, project_id: str) -> list[dict]:
        items = list(
            self.db.scalars(
                select(ScriptSegment).where(ScriptSegment.project_id == project_id).order_by(ScriptSegment.seq_no.asc())
            )
        )
        return [
            {
                "id": item.id,
                "project_id": item.project_id,
                "seq_no": item.seq_no,
                "scene_name": item.scene_name,
                "visual_desc": item.visual_desc,
                "camera_lang": item.camera_lang,
                "character_ids": json.loads(item.character_ids_json or "[]"),
                "variant_refs": json.loads(item.variant_refs_json or "[]"),
                "dialogue_text": item.dialogue_text,
                "narration_text": item.narration_text,
                "emotion_tags": json.loads(item.emotion_tags_json or "[]"),
                "status": item.status,
            }
            for item in items
        ]
