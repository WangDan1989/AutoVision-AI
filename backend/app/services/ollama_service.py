import json
import re
from typing import Any

import httpx

from app.core.config import settings


class OllamaService:
    def build_prompt(self, raw_script_text: str) -> str:
        return f"""
你是短剧剧本结构化拆解引擎。你只能输出一个 JSON 对象，不允许输出 markdown，不允许输出解释。

输出格式严格为：
{{
  "genre_style_guess": "GUZHUANG_XIANXIA | GUZHUANG_WUXIA | GUFENG_ZHAIDOU | XIANDAN_DUSHI | XIAOYUAN_QINGCHUN | XUANYI_TUILI | MINGUO_DIEZHAN | KEHUAN_MOSHI | ZHICHANG_JINGYING | JIATING_LUNLI | KAIXIAO_WENNAN",
  "characters": [
    {{
      "canonical_name": "角色唯一规范名（如 凌风）",
      "display_name": "凌风",
      "appearance_desc": "外貌穿着描述，适合图像生成 prompt：例如 青年侠客，长剑青衫，英气眉宇，束发",
      "age_group": "青年/中年/老年/少年/少女",
      "gender": "男/女"
    }}
  ],
  "locations": [
    {{
      "canonical_name": "场景唯一规范名，必须合并相似地点（如 客栈门口、山脚客栈门外 都合并成 山脚客栈门口）",
      "display_name": "山脚客栈门口",
      "environment_desc": "环境描述，适合图像生成 prompt：例如 青石板路、灯笼、木牌楼、黄昏光",
      "time_of_day": "白天/黄昏/夜晚/清晨",
      "weather": "晴朗/雨天/雪天/雾天 等"
    }}
  ],
  "props": [
    {{
      "canonical_name": "道具唯一规范名",
      "display_name": "青铜长剑",
      "description": "道具描述，适合图像生成 prompt：例如 古朴青铜长剑，剑鞘有云纹",
      "owner_character": "凌风 或 空"
    }}
  ],
  "segments": [
    {{
      "scene_name": "镜头名（简短，如 客栈门口·黄昏），不要把整句动作当场景名",
      "location_canonical": "对应 locations 里的某个 canonical_name，场景引用必须指向已合并的静态地点",
      "visual_desc": "适合图像生成的视觉描述",
      "camera_lang": "运镜：中景/特写/推镜/拉镜/手持 等",
      "character_ids": ["引用 characters 列表里的 canonical_name，或空数组"],
      "variant_refs": [],
      "dialogue_text": "",
      "narration_text": "",
      "emotion_tags": []
    }}
  ]
}}

强制约束：
1. locations 必须跨分镜合并相似地点，同一物理地点只能有 1 条（绝对不能把「向客栈走去」「客栈门口」「并肩出客栈」拆成 3 个场景——它们是同一个地点 客栈门口）。
2. characters 必须跨分镜合并同名角色，同一角色只能有 1 条。
3. props 列出全剧出现的有辨识度的道具（武器、首饰、信物、关键物品），纯背景物品不要列。
4. 每个 segment 的 location_canonical 必须能在 locations 列表里找到匹配的 canonical_name。
5. 每个 segment 的 character_ids 必须能在 characters 列表里找到匹配的 canonical_name。
6. character_ids 用 canonical_name 而不是自增 id。

剧本如下：
{raw_script_text}
""".strip()

    def _extract_json_text(self, text: str) -> str:
        fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
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
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
        fixed = re.sub(r'(?<=[{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'"\1":', fixed)
        return fixed

    def _dedupe_by_canonical(self, items: list[dict], key: str = "canonical_name") -> list[dict]:
        seen: set[str] = set()
        deduped: list[dict] = []
        for it in items:
            c = (it.get(key) or "").strip()
            if not c or c in seen:
                continue
            seen.add(c)
            deduped.append(it)
        return deduped

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        valid_genre = {
            "GUZHUANG_XIANXIA", "GUZHUANG_WUXIA", "GUFENG_ZHAIDOU",
            "XIANDAN_DUSHI", "XIAOYUAN_QINGCHUN", "XUANYI_TUILI",
            "MINGUO_DIEZHAN", "KEHUAN_MOSHI", "ZHICHANG_JINGYING",
            "JIATING_LUNLI", "KAIXIAO_WENNAN",
        }
        genre = (data.get("genre_style_guess") or "GUZHUANG_XIANXIA").strip().upper()
        if genre not in valid_genre:
            genre = "GUZHUANG_XIANXIA"

        characters = self._dedupe_by_canonical(data.get("characters") or [])
        for c in characters:
            c.setdefault("canonical_name", c.get("display_name") or "")
            c["canonical_name"] = (c["canonical_name"] or "").strip() or (c.get("display_name") or c.get("name") or "角色").strip()
            c["display_name"] = (c.get("display_name") or c["canonical_name"]).strip()
            c["appearance_desc"] = (c.get("appearance_desc") or "").strip()
            c.setdefault("age_group", "青年")
            c.setdefault("gender", "男")

        locations = self._dedupe_by_canonical(data.get("locations") or [])
        loc_canonical_set = set()
        for loc in locations:
            loc.setdefault("canonical_name", loc.get("display_name") or "")
            loc["canonical_name"] = (loc["canonical_name"] or "").strip() or (loc.get("display_name") or loc.get("name") or "场景").strip()
            loc["display_name"] = (loc.get("display_name") or loc["canonical_name"]).strip()
            loc["environment_desc"] = (loc.get("environment_desc") or "").strip()
            loc.setdefault("time_of_day", "白天")
            loc.setdefault("weather", "晴朗")
            loc_canonical_set.add(loc["canonical_name"])

        props = self._dedupe_by_canonical(data.get("props") or [])
        for p in props:
            p.setdefault("canonical_name", p.get("display_name") or "")
            p["canonical_name"] = (p["canonical_name"] or "").strip() or (p.get("display_name") or p.get("name") or "道具").strip()
            p["display_name"] = (p.get("display_name") or p["canonical_name"]).strip()
            p["description"] = (p.get("description") or "").strip()
            p.setdefault("owner_character", "")

        segments = data.get("segments") or []
        normalized_segments: list[dict[str, Any]] = []
        for item in segments:
            visual_desc = (item.get("visual_desc") or item.get("shot_desc") or "").strip()
            if not visual_desc:
                continue
            character_ids = []
            for cid in (item.get("character_ids") or []):
                cid_s = str(cid).strip()
                if any(c["canonical_name"] == cid_s for c in characters):
                    character_ids.append(cid_s)
                else:
                    matched = next((c["canonical_name"] for c in characters if c["display_name"] == cid_s), None)
                    if matched:
                        character_ids.append(matched)
            loc_canon = (item.get("location_canonical") or "").strip()
            if loc_canon and loc_canon not in loc_canonical_set and locations:
                loc_canon = locations[0]["canonical_name"]
            if not loc_canon and locations:
                loc_canon = locations[0]["canonical_name"]
            scene_name = (item.get("scene_name") or "").strip() or (next((loc["display_name"] for loc in locations if loc["canonical_name"] == loc_canon), None) if loc_canon else "未命名场景")
            normalized_segments.append(
                {
                    "scene_name": scene_name,
                    "location_canonical": loc_canon,
                    "visual_desc": visual_desc,
                    "camera_lang": (item.get("camera_lang") or "").strip(),
                    "character_ids": character_ids,
                    "variant_refs": item.get("variant_refs") or [],
                    "dialogue_text": (item.get("dialogue_text") or "").strip(),
                    "narration_text": (item.get("narration_text") or "").strip(),
                    "emotion_tags": item.get("emotion_tags") or [],
                }
            )
        if not normalized_segments:
            raise ValueError("Ollama 拆解结果为空")
        if not locations:
            first_scene = normalized_segments[0]["scene_name"] or "主场景"
            locations.append({
                "canonical_name": first_scene,
                "display_name": first_scene,
                "environment_desc": normalized_segments[0]["visual_desc"][:200],
                "time_of_day": "白天",
                "weather": "晴朗",
            })
            normalized_segments[0]["location_canonical"] = first_scene

        return {
            "genre_style_guess": genre,
            "characters": characters,
            "locations": locations,
            "props": props,
            "segments": normalized_segments,
        }

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
