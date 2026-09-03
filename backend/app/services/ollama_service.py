import json
import re
from typing import Any

import httpx

from app.core.config import settings


class OllamaService:
    def build_prompt(self, raw_script_text: str) -> str:
        return f"""
你是短剧分镜拆解引擎。你只能输出一个 JSON 对象，不允许输出 markdown，不允许输出解释。

输出格式严格为：
{{
  "segments": [
    {{
      "scene_name": "",
      "visual_desc": "",
      "camera_lang": "",
      "character_ids": [],
      "variant_refs": [],
      "dialogue_text": "",
      "narration_text": "",
      "emotion_tags": []
    }}
  ]
}}

要求：
1. segments 必须是连续镜头数组
2. visual_desc 必须适合图像生成
3. 每个字段必须存在，缺失时用空字符串或空数组

剧本如下：
{raw_script_text}
""".strip()

    def _extract_json_text(self, text: str) -> str:
        fenced = re.findall(r"```(?:json)?\\s*([\\s\\S]*?)```", text, flags=re.IGNORECASE)
        if fenced:
            return fenced[0].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
        raise ValueError("Ollama 返回中未找到 JSON")

    def _repair_json(self, text: str) -> str:
        fixed = text.replace("\u201c", '"').replace("\u201d", '"')
        fixed = fixed.replace("\u2018", "'").replace("\u2019", "'")
        fixed = re.sub(r",\\s*([}\\]])", r"\\1", fixed)
        fixed = re.sub(r'(?<=\\{|,)\\s*([A-Za-z_][A-Za-z0-9_]*)\\s*:', r'"\\1":', fixed)
        return fixed

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        segments = data.get("segments") or []
        normalized: list[dict[str, Any]] = []
        for item in segments:
            visual_desc = (item.get("visual_desc") or item.get("shot_desc") or "").strip()
            if not visual_desc:
                continue
            normalized.append(
                {
                    "scene_name": (item.get("scene_name") or "").strip(),
                    "visual_desc": visual_desc,
                    "camera_lang": (item.get("camera_lang") or "").strip(),
                    "character_ids": item.get("character_ids") or [],
                    "variant_refs": item.get("variant_refs") or [],
                    "dialogue_text": (item.get("dialogue_text") or "").strip(),
                    "narration_text": (item.get("narration_text") or "").strip(),
                    "emotion_tags": item.get("emotion_tags") or [],
                }
            )
        if not normalized:
            raise ValueError("Ollama 拆解结果为空")
        return {"segments": normalized}

    async def parse_script(self, raw_script_text: str) -> dict[str, Any]:
        prompt = self.build_prompt(raw_script_text)
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SEC) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接 Ollama 服务，请确认已启动并检查 OLLAMA_BASE_URL={settings.OLLAMA_BASE_URL}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama 调用超时，请检查模型是否已就绪或适当调大 OLLAMA_TIMEOUT_SEC={settings.OLLAMA_TIMEOUT_SEC}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama 接口返回异常 HTTP {exc.response.status_code}，请检查 OLLAMA_MODEL={settings.OLLAMA_MODEL}"
            ) from exc

        raw_text = payload.get("response", "")
        json_text = self._repair_json(self._extract_json_text(raw_text))
        data = json.loads(json_text)
        return self._normalize(data)
