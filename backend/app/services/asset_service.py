import asyncio
import json
from collections import OrderedDict
from typing import Any
from urllib.parse import quote

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, JobStatus
from app.core.config import settings
from app.db.models.asset import Asset, AssetBinding, AssetPreview
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.schemas.asset import BindingRequest, ConsistencyConfig, SaveConsistencyRequest
from app.services.comfyui_service import ComfyUIService
from app.utils.files import to_relative_media_path
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


def _encode_media_url(rel_path: str, cache_buster: str | None = None) -> str:
    if not rel_path:
        return ""
    safe_rel = quote(rel_path.replace("\\", "/"), safe="/.+-_@#~=&()[]!$*;'%,")
    base = f"/media/{safe_rel}"
    if cache_buster:
        sep = "&" if "?" in base else "?"
        base = f"{base}{sep}t={cache_buster}"
    return base


GENRE_STYLE_KEYWORDS: dict[str, dict[str, Any]] = {
    "GUZHUANG_XIANXIA": {
        "label": "古装仙侠",
        "style_terms": "chinese ancient xianxia wuxia fantasy style, elegant flowing hanfu robes, celestial immortal atmosphere, ink-wash inspired color palette, mystical mountains and clouds, cinematic chinese historical aesthetic",
        "negative_extra": "modern clothes, modern city, cars, technology, english text, photography watermark",
    },
    "GUZHUANG_WUXIA": {
        "label": "古装武侠",
        "style_terms": "chinese ancient wuxia martial arts style, traditional hanfu, jianghu pugilist atmosphere, historic mountain landscapes, bamboo forests, dramatic cinematic lighting",
        "negative_extra": "modern clothes, modern city, guns, neon lights, english text",
    },
    "GUFENG_ZHAIDOU": {
        "label": "古风宅斗",
        "style_terms": "chinese ancient mansion harem style, ornate silk hanfu, traditional chinese courtyard interior, lacquer wood furniture, elegant court atmosphere, historical realistic illustration",
        "negative_extra": "modern interior, plastic furniture, neon lights, modern clothes",
    },
    "XIANDAN_DUSHI": {
        "label": "现代都市",
        "style_terms": "modern contemporary chinese urban city style, realistic kdrama cdrama cinematography, city street skyscrapers, modern fashion streetwear, cinematic natural lighting",
        "negative_extra": "ancient clothes, traditional hanfu, swords, historical architecture, fantasy creatures",
    },
    "XIAOYUAN_QINGCHUN": {
        "label": "校园青春",
        "style_terms": "japanese korean chinese high school youth style, modern school uniforms, classroom campus cherry blossom, soft bright youthful lighting, slice of life anime illustration",
        "negative_extra": "adult business suits, old faces, ancient clothes, dark moody scenes",
    },
    "XUANYI_TUILI": {
        "label": "悬疑推理",
        "style_terms": "noir detective thriller mystery style, moody low-key chiaroscuro lighting, rain wet city streets, shadowy crime scene, cinematic dark color grading, realistic cinematic illustration",
        "negative_extra": "bright pastel colors, cartoon, chibi, comedic expression, text watermark",
    },
    "MINGUO_DIEZHAN": {
        "label": "民国谍战",
        "style_terms": "republic of china 1930s spy espionage style, cheongsam qipao, vintage suits, old shanghai street, art deco architecture, sepia vintage cinematic tone",
        "negative_extra": "modern skyscraper, modern fashion, smartphones, neon, ancient hanfu",
    },
    "KEHUAN_MOSHI": {
        "label": "科幻末世",
        "style_terms": "cyberpunk post-apocalyptic sci-fi style, ruined city skyscraper, neon holograms, advanced tech armor, smoke dust volumetric light, cinematic sci-fi concept art",
        "negative_extra": "medieval fantasy, horses, swords, ancient architecture, vintage sepia",
    },
    "ZHICHANG_JINGYING": {
        "label": "职场经营",
        "style_terms": "modern corporate office business drama style, stylish business suits, modern skyscraper office interior, clean bright professional lighting, realistic kdrama style",
        "negative_extra": "casual street clothes, messy rooms, ancient clothes, fantasy elements",
    },
    "JIATING_LUNLI": {
        "label": "家庭伦理",
        "style_terms": "modern chinese family domestic drama style, contemporary apartment interior, casual home clothes, natural warm lighting, realistic slice of life illustration",
        "negative_extra": "office suits, skyscrapers, ancient clothes, fantasy creatures, neon",
    },
    "KAIXIAO_WENNAN": {
        "label": "爆笑微甜",
        "style_terms": "bright warm romantic comedy style, pastel cute color palette, cute chibi accent moments, soft lighting, cheerful sweet romantic kdrama cdrama illustration",
        "negative_extra": "dark moody scenes, horror, violence, blood, noir shadows, crying face",
    },
    "AUTO": {
        "label": "自动识别",
        "style_terms": "masterpiece, best quality, cinematic lighting, highly detailed illustration, beautiful color grading",
        "negative_extra": "",
    },
}


def get_genre_style_keywords(genre_style: str | None) -> dict[str, Any]:
    key = (genre_style or "AUTO").strip().upper()
    if key not in GENRE_STYLE_KEYWORDS:
        key = "GUZHUANG_XIANXIA"
    return GENRE_STYLE_KEYWORDS[key]


CHARACTER_EN_KEYWORDS: list[tuple[str, str]] = [
    ("青衫", "wears azure-blue flowing robe hanfu"),
    ("白裙", "wears elegant white layered silk hanfu dress"),
    ("白衣", "wears elegant white flowing hanfu robes"),
    ("红衣", "wears crimson red embroidered hanfu"),
    ("黑袍", "wears dark black mysterious hanfu robes"),
    ("素裹", "plain unadorned silk fabric, minimalist aesthetic"),
    ("灵动", "lively expressive gentle eyes, delicate soft features"),
    ("英气", "heroic noble sharp eyebrows and jawline, dignified bearing"),
    ("温婉", "gentle soft facial features, graceful feminine aura"),
    ("冷艳", "cool ethereal stoic expression, icy regal beauty"),
    ("束发", "long black hair tied up in traditional topknot with jade hairpin"),
    ("长发", "very long flowing black hair cascading down back"),
    ("盘发", "elaborate traditional coiffure updo with golden hair ornaments"),
    ("青年男", "young handsome man around 20 years old, tall athletic build"),
    ("少女女", "young beautiful woman around 18 years old, slender graceful figure"),
    ("中年男", "mature middle aged man, experienced weathered face"),
    ("少女", "young beautiful woman around 18 years old, slender graceful figure"),
    ("青年", "young person around 20 years old"),
    ("长剑", "wears or carries a long straight sword at waist"),
    ("医仙", "carries medicinal herbs and silver acupuncture needle pouch"),
    ("侠客", "wandering martial artist swordsman, practical travel worn robes"),
    ("书生", "scholar with book scroll tucked in robe, refined scholarly air"),
    ("将军", "military general in ornate armor, commanding imposing presence"),
    ("公主", "royal princess with golden headdress, exquisite palace robes"),
]

SCENE_EN_KEYWORDS: list[tuple[str, str]] = [
    ("客栈门口", "traditional chinese tavern inn entrance, wooden archway gate, red paper lanterns hanging, bluestone pavement steps leading up to door, prominent doorway and threshold"),
    ("客栈门前", "traditional chinese tavern inn entrance, wooden archway gate, red paper lanterns hanging, bluestone pavement steps leading up to door, prominent doorway and threshold"),
    ("客栈二楼窗前", "second floor interior of traditional chinese tavern inn, WOODEN LATTICE WINDOW WITH RICE PAPER PANES PROMINENTLY VISIBLE IN CENTER OF FRAME, tea table and wooden stool, warm sunset golden glow streaming through window panes"),
    ("下山路", "WIDE WALKABLE DESCENDING MOUNTAIN TRAIL PAVED WITH BLUESTONE STONE STEPS DOMINATING THE FOREGROUND, winding path all the way visible through pine forest down slope, handrail ropes at side"),
    ("小镇集市", "bustling ancient chinese small town market street entrance, bluestone main road crowded with wooden vendor stalls, waving cloth banners, pedestrians carrying goods, smoke from food stalls"),
    ("山脚客栈", "inn tavern building at foot of tall misty mountains, dirt and stone meeting area outside, traveler horses tied to posts, distant mountain peaks"),
    ("山林清晨", "mountain forest early dawn morning, thick white mist between ancient pine trees, soft golden sun rays filtering through canopy, dew on grass"),
    ("黄昏晴朗", "dramatic golden hour sunset orange and purple sky, warm long shadows cast, clear blue atmosphere transitioning"),
    ("白天晴朗", "bright clear midday sky, crisp natural daylight, vivid saturated colors"),
    ("晨雾", "atmospheric soft white ground fog, ethereal diffused lighting, dreamy mood"),
    ("青石板", "bluestone stone slab pavement path, clearly visible flat stone tiles with moss"),
    ("灯笼", "red paper lanterns with golden tassels hanging along eaves"),
    ("木牌楼", "tall wooden paifang archway gate at entrance, traditional joinery"),
    ("窗外落霞", "view through window of romantic sunset rosy clouds in sky"),
    ("炊烟袅袅", "woodsmoke curling up from kitchen chimneys in distant village houses"),
]

PROP_EN_KEYWORDS: list[tuple[str, str]] = [
    ("青铜", "crafted from aged patinated green bronze metal, antique weathered verdigris surface patina"),
    ("长剑", "LONG CHINESE DOUBLE EDGED STRAIGHT JIAN SWORD with detailed jade pommel, long central fuller groove"),
    ("剑鞘有云纹", "matching scabbard decorated with engraved cloud motifs and leather wrappings"),
    ("古朴", "simple rustic ancient aesthetic, no excessive ornamentation, timeless elegant design"),
    ("云纹", "engraved traditional chinese cloud scroll pattern decoration"),
    ("玉饰", "polished jade ornament inlays, translucent ice green color"),
    ("玉佩", "carved jade pendant with tassel string hanging"),
    ("扇子", "folding handheld paper fan with calligraphy and ink painting"),
    ("笛子", "bamboo transverse flute with red binding thread tassel"),
    ("药囊", "embroidered silk medicine pouch with drawstring closure, herbs visible inside"),
    ("兵书", "ancient bamboo slip military strategy scroll book tied with cord"),
]

SCENE_NAME_EN_OVERRIDES: dict[str, str] = {
    "山脚客栈门口": "traditional chinese mountain village tavern inn entrance at foot of misty xianxia peaks",
    "下山路": "descending bluestone stone step mountain trail through pine forest",
    "小镇集市入口": "ancient chinese small town market street entrance with vendor stalls",
    "客栈二楼窗前": "second floor interior of traditional chinese inn, lattice paper window visible",
}

PROP_NAME_EN_OVERRIDES: dict[str, str] = {
    "青铜长剑": "ANCIENT CHINESE BRONZE DOUBLE-EDGED STRAIGHT JIAN LONGSWORD with matching cloud pattern scabbard",
}

CHARACTER_NAME_EN_OVERRIDES: dict[str, str] = {
    "凌风": "Ling Feng, young heroic xianxia wandering swordsman",
    "苏婉": "Su Wan, young elegant xianxia healer herbalist maiden",
}


def _map_keywords(text: str, mapping: list[tuple[str, str]]) -> list[str]:
    hits: list[str] = []
    if not text:
        return hits
    for cn, en in mapping:
        if cn in text:
            hits.append(en)
    return hits


def _asset_core_name_en(asset: Asset) -> str:
    name = (asset.name or "").strip()
    at = asset.asset_type
    if at == AssetType.CHARACTER.value:
        if name in CHARACTER_NAME_EN_OVERRIDES:
            return CHARACTER_NAME_EN_OVERRIDES[name]
        return f"{name} character, xianxia fantasy person"
    if at == AssetType.SCENE.value:
        if name in SCENE_NAME_EN_OVERRIDES:
            return SCENE_NAME_EN_OVERRIDES[name]
        return f"{name} location, xianxia fantasy environment"
    if name in PROP_NAME_EN_OVERRIDES:
        return PROP_NAME_EN_OVERRIDES[name]
    return f"{name} object, xianxia fantasy prop"


def _asset_detail_keywords_en(asset: Asset) -> str:
    combined = f"{asset.name or ''} {asset.description or ''}"
    at = asset.asset_type
    parts: list[str] = []
    if at == AssetType.CHARACTER.value:
        parts.extend(_map_keywords(combined, CHARACTER_EN_KEYWORDS))
    elif at == AssetType.SCENE.value:
        parts.extend(_map_keywords(combined, SCENE_EN_KEYWORDS))
    else:
        parts.extend(_map_keywords(combined, PROP_EN_KEYWORDS))
    dedup = list(dict.fromkeys(parts))
    return ", ".join(dedup)


def _seed_from_id(asset_id: str, role: str) -> int:
    key = f"{asset_id}|{role}".encode("utf-8")
    import hashlib
    digest = hashlib.sha1(key).digest()
    return int.from_bytes(digest[:4], "big", signed=False) % (2**31 - 1) + 1


def _extra_negative(asset_type: str, consistency: dict | None = None) -> str:
    base = (
        "lowres, worst quality, low quality, jpeg artifacts, blurry, out of focus, "
        "ugly, deformed, disfigured, bad anatomy, extra limbs, extra digits, extra fingers, "
        "watermark, signature, text, logo, border, frame, cropped"
    )
    if asset_type == AssetType.CHARACTER.value:
        neg = (
            base + ", landscape, scenery, mountain background, buildings, crowd, multiple people, "
            "group photo, environmental shot, out of frame body, face cut off"
        )
    elif asset_type == AssetType.SCENE.value:
        neg = (
            base + ", human, person, character, face, portrait, close up of person, figure, "
            "animal, giant creature, text overlay, watermark inside scene, close-up cropped detail"
        )
    else:
        neg = (
            base + ", landscape, scenery, mountain, building, architecture, forest environment, "
            "human, person, character, face, crowd, animals, background scenery overwhelming"
        )
    cons = consistency or {}
    if asset_type == AssetType.CHARACTER.value and cons.get("lock_outfit"):
        neg += (
            ", random accessories, gradient dye outfit, different clothing, "
            "wardrobe change, outfit variant, mismatched costume design, altered robe pattern"
        )
    return neg


def _load_consistency(asset: Asset) -> dict:
    try:
        raw = asset.consistency_config_json if hasattr(asset, "consistency_config_json") else "{}"
        parsed = json.loads(raw or "{}") if raw else {}
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception:
        parsed = {}
    defaults = ConsistencyConfig().model_dump()
    for k, v in defaults.items():
        if k not in parsed:
            parsed[k] = v
    return parsed


class AssetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.comfy = ComfyUIService()

    def _ordered_unique(self, items: list[str]) -> list[str]:
        bag: OrderedDict[str, bool] = OrderedDict()
        for item in items:
            name = item.strip()
            if name:
                bag[name] = True
        return list(bag.keys())

    def _trim_style_for_asset_type(self, asset_type: str, style_terms: str, consistency: dict | None = None) -> str:
        parts = [p.strip() for p in style_terms.split(",") if p.strip()]
        drops = set()
        extras: list[str] = []
        if asset_type == AssetType.PROP.value:
            drops.update({
                "elegant flowing hanfu robes",
                "mystical mountains and clouds",
                "celestial immortal atmosphere",
                "traditional hanfu",
                "jianghu pugilist atmosphere",
                "historic mountain landscapes",
                "bamboo forests",
                "ornate silk hanfu",
                "traditional chinese courtyard interior",
                "lacquer wood furniture",
            })
            extras.extend([
                "high detail product photography",
                "clean isolated object showcase",
                "professional studio product shot",
                "macro sharp textures on object surface",
            ])
        elif asset_type == AssetType.CHARACTER.value:
            drops.update({
                "mystical mountains and clouds",
                "historic mountain landscapes",
                "bamboo forests",
                "traditional chinese courtyard interior",
                "lacquer wood furniture",
            })
            extras.extend([
                "character design illustration",
                "highly detailed facial features and costume design",
                "consistent character likeness across angles",
            ])
        else:
            extras.extend([
                "practical film set location design",
                "cohesive cinematic color tone and lighting continuity",
            ])
        filtered = [p for p in parts if p.lower() not in {d.lower() for d in drops}]
        filtered.extend(extras)
        cons = consistency or {}
        extra_style = (cons.get("style_extra_prompt") or "").strip()
        if extra_style:
            filtered.append(extra_style)
        return ", ".join(filtered)

    def _full_en_prompt_prefix(self, asset: Asset, style_terms: str, consistency: dict | None = None) -> str:
        cons = consistency or {}
        face_tags_list = cons.get("face_tags") or []
        face_prefix = ""
        if face_tags_list and asset.asset_type == AssetType.CHARACTER.value:
            cleaned = [str(t).strip() for t in face_tags_list if str(t).strip()]
            if cleaned:
                face_prefix = ", ".join(cleaned) + ", "
        core = _asset_core_name_en(asset)
        trimmed_style = self._trim_style_for_asset_type(asset.asset_type, style_terms, consistency)
        details = _asset_detail_keywords_en(asset)
        if details:
            return f"{face_prefix}{core}, {trimmed_style}, {details}"
        return f"{face_prefix}{core}, {trimmed_style}"

    def _consistency_lighting_suffix(self, consistency: dict) -> str:
        cons = consistency or {}
        parts: list[str] = []
        preset = (cons.get("lighting_preset") or "").strip().lower()
        if preset == "day":
            parts.append("bright natural daylight, clear midday sun")
        elif preset == "sunset_golden" or preset == "sunset":
            parts.append("warm sunset golden hour lighting, long cast soft shadows")
        elif preset == "night" or preset == "night_dark":
            parts.append("low-key night scene lighting, cool moonlight rim light, deep shadows")
        elif preset == "indoor_warm" or preset == "indoor":
            parts.append("warm cozy indoor ambient lamplight, soft tungsten color temperature")
        color_temp = int(cons.get("lighting_color_temp_k") or 0)
        if color_temp > 0:
            parts.append(f"{color_temp}K color temperature")
        direction = (cons.get("lighting_direction") or "").strip().lower()
        if direction == "top":
            parts.append("top-down overhead key light")
        elif direction == "side_left":
            parts.append("side-left key light")
        elif direction == "side_right":
            parts.append("side-right key light")
        elif direction == "back":
            parts.append("backlight rim silhouette lighting")
        return ", ".join(parts)

    def _build_character_cover_prompt(self, asset: Asset, style_terms: str, consistency: dict | None = None) -> tuple[str, int, int]:
        cons = consistency or {}
        lock_outfit_extra = ""
        if cons.get("lock_outfit"):
            lock_outfit_extra = (
                ", consistent identical outfit design, NO outfit variations, same costume every frame, "
                "exact matching robe color and pattern"
            )
        lighting = self._consistency_lighting_suffix(cons)
        lighting_suffix = f", {lighting}" if lighting else ""
        prompt = (
            f"{self._full_en_prompt_prefix(asset, style_terms, consistency)}, "
            "full body standing character reference sheet, symmetrical T-pose front view facing camera, "
            "detailed clear face and outfit, plain light grey studio background, "
            f"masterpiece, best quality, highres, sharp focus{lock_outfit_extra}{lighting_suffix}"
        )
        return prompt, 512, 768

    def _build_scene_cover_prompt(self, asset: Asset, style_terms: str, consistency: dict | None = None) -> tuple[str, int, int]:
        cons = consistency or {}
        anchor = (cons.get("scene_anchor_desc") or "").strip()
        anchor_suffix = f", {anchor}" if anchor else ""
        lighting = self._consistency_lighting_suffix(cons)
        lighting_suffix = f", {lighting}" if lighting else ""
        lut_tag = (cons.get("lighting_lut") or "").strip()
        lut_suffix = f", {lut_tag} LUT color grade applied" if lut_tag else ""
        prompt = (
            f"{self._full_en_prompt_prefix(asset, style_terms, consistency)}, "
            "cinematic wide establishing shot keyframe, beautiful detailed environment, "
            f"dramatic atmospheric lighting, masterpiece, best quality, highres, "
            f"wide angle composition, no people, environment only{anchor_suffix}{lighting_suffix}{lut_suffix}"
        )
        return prompt, 768, 512

    def _build_prop_cover_prompt(self, asset: Asset, style_terms: str, consistency: dict | None = None) -> tuple[str, int, int]:
        lighting = self._consistency_lighting_suffix(consistency)
        lighting_suffix = f", {lighting}" if lighting else ""
        prompt = (
            f"{self._full_en_prompt_prefix(asset, style_terms, consistency)}, "
            "centered product shot on plain light grey studio background, "
            "soft rim lighting, high detail textures, no people, no environment background, "
            f"masterpiece, best quality, high resolution, sharp macro focus{lighting_suffix}"
        )
        return prompt, 512, 512

    def _build_preview_plan(self, asset: Asset, style_terms: str, consistency: dict | None = None) -> list[dict]:
        cons = consistency or {}
        prefix = self._full_en_prompt_prefix(asset, style_terms, consistency)
        lighting = self._consistency_lighting_suffix(cons)
        lighting_suffix = f", {lighting}" if lighting else ""
        lock_suffix = ""
        if asset.asset_type == AssetType.CHARACTER.value and cons.get("lock_outfit"):
            lock_suffix = (
                ", consistent identical outfit design, NO outfit variations, same costume every frame"
            )
        anchor_suffix = ""
        lut_suffix = ""
        if asset.asset_type == AssetType.SCENE.value:
            anchor = (cons.get("scene_anchor_desc") or "").strip()
            if anchor:
                anchor_suffix = f", {anchor}"
            lut_tag = (cons.get("lighting_lut") or "").strip()
            if lut_tag:
                lut_suffix = f", {lut_tag} LUT color grade"
        camera_move = (cons.get("camera_move_preset") or "").strip().lower()
        move_suffix = ""
        if camera_move == "push_in" or camera_move == "pushin":
            move_suffix = ", slow push in camera move, steady dolly in motion"
        elif camera_move == "pan" or camera_move == "pan_left":
            move_suffix = ", slow pan left camera move, sweeping lateral motion"
        elif camera_move == "pan_right":
            move_suffix = ", slow pan right camera move, sweeping lateral motion"
        elif camera_move == "establishing":
            move_suffix = ", cinematic establishing shot camera language"
        elif camera_move == "ots" or camera_move == "over_the_shoulder":
            move_suffix = ", over-the-shoulder shot composition"
        axis = (cons.get("camera_180_axis") or "").strip().lower()
        axis_suffix = ""
        if axis == "left":
            axis_suffix = ", camera stays on left side of 180 degree axis, consistent screen direction"
        elif axis == "right":
            axis_suffix = ", camera stays on right side of 180 degree axis, consistent screen direction"
        if asset.asset_type == AssetType.CHARACTER.value:
            char_suffix = f"{lock_suffix}{lighting_suffix}{move_suffix}{axis_suffix}"
            return [
                {
                    "preview_role": "FRONT_FULL",
                    "preview_label": "正面全身",
                    "prompt": (
                        f"{prefix}, full body front view standing, facing camera straight on, "
                        "plain light grey studio background, masterpiece, best quality, "
                        f"highly detailed face and matching outfit, sharp focus{char_suffix}"
                    ),
                    "width": 512,
                    "height": 768,
                },
                {
                    "preview_role": "SIDE_HALF",
                    "preview_label": "侧面半身",
                    "prompt": (
                        f"{prefix}, side view profile half body portrait, 90 degree turn to camera right, "
                        "profile silhouette face and clothing line, plain light grey background, "
                        f"masterpiece, best quality, highres{char_suffix}"
                    ),
                    "width": 512,
                    "height": 768,
                },
                {
                    "preview_role": "BACK_FULL",
                    "preview_label": "背面全身",
                    "prompt": (
                        f"{prefix}, full body back view from directly behind, "
                        "back of hairstyle and back robe embroidery design clearly visible, "
                        f"plain light grey studio background, masterpiece, best quality, highres{char_suffix}"
                    ),
                    "width": 512,
                    "height": 768,
                },
                {
                    "preview_role": "FACE_CLOSEUP",
                    "preview_label": "面部表情特写",
                    "prompt": (
                        f"{prefix}, tight close-up portrait of face only, shoulders up crop, "
                        "neutral calm expression, detailed eyes and traditional makeup, "
                        f"soft studio lighting, masterpiece, best quality, high detail{char_suffix}"
                    ),
                    "width": 512,
                    "height": 512,
                },
            ]
        if asset.asset_type == AssetType.SCENE.value:
            scene_suffix = f"{lighting_suffix}{anchor_suffix}{lut_suffix}{move_suffix}{axis_suffix}"
            return [
                {
                    "preview_role": "WIDE_PANORAMA",
                    "preview_label": "宽景全景",
                    "prompt": (
                        f"{prefix}, ultra wide panoramic establishing shot, "
                        "epic scale sweeping landscape vista, dramatic sky and atmospheric weather, "
                        f"no humans no characters, masterpiece, best quality, ultra detailed environment{scene_suffix}"
                    ),
                    "width": 768,
                    "height": 432,
                },
                {
                    "preview_role": "MID_ESTABLISH",
                    "preview_label": "中景主视角",
                    "prompt": (
                        f"{prefix}, medium shot main camera angle composition, "
                        "walkable practical set layout for character entry blocking, "
                        f"cinematic natural lighting, no people no characters, "
                        f"masterpiece, best quality{scene_suffix}"
                    ),
                    "width": 768,
                    "height": 512,
                },
                {
                    "preview_role": "ALT_ANGLE",
                    "preview_label": "切换机位角度",
                    "prompt": (
                        f"{prefix}, alternate camera angle from opposite corner or different floor level, "
                        "same time of day same weather same color tone consistency for scene transition, "
                        f"no people no characters, masterpiece, best quality{scene_suffix}"
                    ),
                    "width": 768,
                    "height": 512,
                },
            ]
        prop_suffix = f"{lighting_suffix}"
        return [
            {
                "preview_role": "FRONT_PRODUCT",
                "preview_label": "正面主视图",
                "prompt": (
                    f"{prefix}, centered symmetrical front view product photo, "
                    "plain light grey studio background, soft key light and rim light setup, "
                    f"no humans, no environment, object only, macro sharp detail textures, "
                    f"masterpiece, best quality{prop_suffix}"
                ),
                "width": 512,
                "height": 512,
            },
            {
                "preview_role": "IN_CONTEXT",
                "preview_label": "使用场景图",
                "prompt": (
                    f"{prefix}, contextual hero shot of object being held or placed in matching period setting, "
                    "cinematic storytelling composition, soft bokeh background, focus sharp on object, "
                    f"narrative atmosphere, masterpiece, best quality{prop_suffix}"
                ),
                "width": 768,
                "height": 512,
            },
        ]

    async def _generate_single_image(
        self,
        project_id: str,
        asset_id: str,
        asset_type: str,
        role: str,
        name: str,
        prompt: str,
        width: int,
        height: int,
        genre_style: str | None = None,
        consistency: dict | None = None,
    ) -> str | None:
        try:
            now = utc_now_iso()
            safe_name = name.replace(" ", "_").replace("/", "_")
            prefix = f"{project_id}_{asset_id}_{safe_name}_{role}_{now.replace(':', '').replace('-', '')}"
            style_cfg = get_genre_style_keywords(genre_style)
            neg_parts = [
                _extra_negative(asset_type, consistency),
                settings.COMFYUI_NEGATIVE_PROMPT or "",
            ]
            extra_neg = style_cfg.get("negative_extra") or ""
            if extra_neg:
                neg_parts.append(extra_neg)
            negative = ", ".join(p for p in neg_parts if p)
            seed = _seed_from_id(asset_id, role)
            render = await self.comfy.generate_image(
                positive_prompt=prompt,
                negative_prompt=negative,
                width=width,
                height=height,
                filename_prefix=prefix,
                seed=seed,
            )
            return render["image_path"]
        except Exception as exc:
            import traceback
            try:
                import sys as _sys
                msg = (
                    "_generate_single_image failed name="
                    + str(name)
                    + " role="
                    + str(role)
                    + " exc="
                    + str(exc)
                    + "\n"
                    + traceback.format_exc()[:800]
                )
                print(msg, file=_sys.stderr)
            except Exception:
                pass
            return None

    async def _render_preview(self, asset: Asset, preview_row: AssetPreview, style_terms: str, genre_style: str | None = None) -> None:
        consistency = _load_consistency(asset)
        plan = self._build_preview_plan(asset, style_terms, consistency)
        matched = next((p for p in plan if p["preview_role"] == preview_row.preview_role), None)
        if not matched:
            preview_row.status = JobStatus.FAILED.value
            return
        prompt = matched["prompt"]
        preview_row.prompt_text = prompt
        preview_row.width = matched["width"]
        preview_row.height = matched["height"]
        pose_tags_map = consistency.get("pose_tags") or {}
        pose_default = str(pose_tags_map.get(preview_row.preview_role) or "").strip()
        if pose_default:
            preview_row.pose_tag = pose_default
        cam_parts = []
        mc = consistency.get("main_camera_tag") or ""
        mp = consistency.get("camera_move_preset") or ""
        ma = consistency.get("camera_180_axis") or ""
        if mc: cam_parts.append(str(mc))
        if mp: cam_parts.append(str(mp))
        if ma: cam_parts.append(str(ma))
        preview_row.camera_tag = ", ".join(cam_parts)
        lm_parts = []
        lp = consistency.get("lighting_preset") or ""
        lk = consistency.get("lighting_color_temp_k") or 0
        ld = consistency.get("lighting_direction") or ""
        ll = consistency.get("lighting_lut") or ""
        if lp: lm_parts.append(str(lp))
        try:
            if lk and int(lk) > 0: lm_parts.append(f"{int(lk)}K")
        except Exception: pass
        if ld: lm_parts.append(str(ld))
        if ll: lm_parts.append(f"LUT:{ll}")
        preview_row.lighting_tag = ", ".join(lm_parts)
        image_path = await self._generate_single_image(
            project_id=asset.project_id,
            asset_id=asset.id,
            asset_type=asset.asset_type,
            role=preview_row.preview_role,
            name=asset.name,
            prompt=prompt,
            width=matched["width"],
            height=matched["height"],
            genre_style=genre_style,
            consistency=consistency,
        )
        if image_path:
            preview_row.image_path = image_path
            preview_row.status = JobStatus.COMPLETED.value
        else:
            preview_row.status = JobStatus.FAILED.value
        preview_row.updated_at = utc_now_iso()

    async def _render_cover(self, asset: Asset, style_terms: str, genre_style: str | None = None) -> None:
        consistency = _load_consistency(asset)
        if asset.asset_type == AssetType.CHARACTER.value:
            prompt, width, height = self._build_character_cover_prompt(asset, style_terms, consistency)
        elif asset.asset_type == AssetType.SCENE.value:
            prompt, width, height = self._build_scene_cover_prompt(asset, style_terms, consistency)
        else:
            prompt, width, height = self._build_prop_cover_prompt(asset, style_terms, consistency)
        cover_path = await self._generate_single_image(
            project_id=asset.project_id,
            asset_id=asset.id,
            asset_type=asset.asset_type,
            role="COVER",
            name=asset.name,
            prompt=prompt,
            width=width,
            height=height,
            genre_style=genre_style,
            consistency=consistency,
        )
        if cover_path:
            asset.cover_image_path = cover_path
            asset.status = JobStatus.COMPLETED.value
        else:
            asset.status = JobStatus.FAILED.value
        asset.updated_at = utc_now_iso()

    def _collect_project_asset_specs(
        self, project: Project
    ) -> tuple[list[dict], list[dict], list[dict]]:
        segments = list(
            self.db.scalars(
                select(ScriptSegment)
                .where(ScriptSegment.project_id == project.id)
                .order_by(ScriptSegment.seq_no.asc())
            )
        )
        raw_script_text = project.raw_script_text or ""
        try:
            raw_latest_parse: dict = json.loads(project.last_parse_result_json or "{}") or {}
        except Exception:
            raw_latest_parse = {}

        character_by_canon: OrderedDict[str, dict] = OrderedDict()
        location_by_canon: OrderedDict[str, dict] = OrderedDict()

        for seg in segments:
            seg_chars = json.loads(seg.character_ids_json or "[]")
            for cname in seg_chars:
                cname = str(cname).strip()
                if not cname:
                    continue
                if cname not in character_by_canon:
                    character_by_canon[cname] = {
                        "canonical_name": cname,
                        "display_name": cname,
                        "appearance_desc": "",
                        "age_group": "青年",
                        "gender": "男",
                    }
            loc = (seg.location_canonical or "").strip()
            if not loc:
                continue
            if loc not in location_by_canon:
                location_by_canon[loc] = {
                    "canonical_name": loc,
                    "display_name": loc,
                    "environment_desc": "",
                    "time_of_day": "白天",
                    "weather": "晴朗",
                }

        if character_by_canon or location_by_canon:
            parsed = raw_latest_parse
            if parsed:
                for c in parsed.get("characters") or []:
                    canon = (c.get("canonical_name") or "").strip()
                    if canon and canon in character_by_canon:
                        character_by_canon[canon].update({
                            "display_name": c.get("display_name") or canon,
                            "appearance_desc": (c.get("appearance_desc") or "").strip(),
                            "age_group": c.get("age_group") or "青年",
                            "gender": c.get("gender") or "男",
                        })
                for loc in parsed.get("locations") or []:
                    canon = (loc.get("canonical_name") or "").strip()
                    if canon and canon in location_by_canon:
                        location_by_canon[canon].update({
                            "display_name": loc.get("display_name") or canon,
                            "environment_desc": (loc.get("environment_desc") or "").strip(),
                            "time_of_day": loc.get("time_of_day") or "白天",
                            "weather": loc.get("weather") or "晴朗",
                        })

        parsed = raw_latest_parse
        if parsed:
            for c in parsed.get("characters") or []:
                canon = (c.get("canonical_name") or "").strip()
                if not canon:
                    continue
                if canon not in character_by_canon:
                    character_by_canon[canon] = {
                        "canonical_name": canon,
                        "display_name": c.get("display_name") or canon,
                        "appearance_desc": (c.get("appearance_desc") or "").strip(),
                        "age_group": c.get("age_group") or "青年",
                        "gender": c.get("gender") or "男",
                    }
            for loc in parsed.get("locations") or []:
                canon = (loc.get("canonical_name") or "").strip()
                if not canon:
                    continue
                if canon not in location_by_canon:
                    location_by_canon[canon] = {
                        "canonical_name": canon,
                        "display_name": loc.get("display_name") or canon,
                        "environment_desc": (loc.get("environment_desc") or "").strip(),
                        "time_of_day": loc.get("time_of_day") or "白天",
                        "weather": loc.get("weather") or "晴朗",
                    }

        first_seg_texts = "\n".join(
            f"{s.scene_name}: {s.visual_desc}" for s in segments[:10] if s.visual_desc
        )

        def build_char_desc(c_spec: dict) -> str:
            parts: list[str] = []
            if c_spec.get("appearance_desc"):
                parts.append(c_spec["appearance_desc"])
            age_gender = f"{c_spec.get('age_group') or ''}{c_spec.get('gender') or ''}".strip()
            if age_gender:
                parts.append(age_gender)
            if not parts and raw_script_text:
                parts.append(f"major character in the script, design consistent with the story")
            return ", ".join([p for p in parts if p])

        def build_loc_desc(l_spec: dict) -> str:
            parts: list[str] = []
            if l_spec.get("environment_desc"):
                parts.append(l_spec["environment_desc"])
            time_weather = f"{l_spec.get('time_of_day') or ''} {l_spec.get('weather') or ''}".strip()
            if time_weather:
                parts.append(time_weather)
            if not parts and first_seg_texts:
                sample = first_seg_texts[:200]
                parts.append(sample)
            return ", ".join([p for p in parts if p])

        characters = [
            {
                "canonical_name": c["canonical_name"],
                "display_name": c["display_name"] or c["canonical_name"],
                "description": build_char_desc(c),
            }
            for c in character_by_canon.values()
        ]
        locations = [
            {
                "canonical_name": l["canonical_name"],
                "display_name": l["display_name"] or l["canonical_name"],
                "description": build_loc_desc(l),
            }
            for l in location_by_canon.values()
        ]
        props_raw: list[dict] = []
        if raw_latest_parse:
            props_raw = list(raw_latest_parse.get("props") or [])
        if not props_raw and raw_script_text:
            props_raw = []
        props_dedup: OrderedDict[str, dict] = OrderedDict()
        for p in props_raw:
            canon = (p.get("canonical_name") or p.get("display_name") or "").strip()
            if not canon:
                continue
            if canon not in props_dedup:
                owner = (p.get("owner_character") or "").strip()
                desc_parts: list[str] = []
                if p.get("description"):
                    desc_parts.append(str(p["description"]).strip())
                if owner:
                    desc_parts.append(f"owner: {owner}")
                props_dedup[canon] = {
                    "canonical_name": canon,
                    "display_name": p.get("display_name") or canon,
                    "description": ", ".join(x for x in desc_parts if x) or f"{canon} prop",
                }
        props = list(props_dedup.values())
        return characters, locations, props

    async def rebuild_assets(self, project: Project) -> list[Asset]:
        characters, locations, props = self._collect_project_asset_specs(project)
        if not characters and not locations and not props:
            raise ValueError("当前项目还没有可用于构建资产的分镜/剧本数据")

        style_cfg = get_genre_style_keywords(project.genre_style)
        style_terms = style_cfg["style_terms"]

        canon_to_consistency: dict[tuple[str, str], str] = {}
        canon_preview_to_tags: dict[tuple[str, str, str], tuple[str, str, str]] = {}
        try:
            old_assets = list(self.db.scalars(select(Asset).where(Asset.project_id == project.id)))
            for _a in old_assets:
                ckey = (_a.asset_type, _a.canonical_name)
                canon_to_consistency[ckey] = _a.consistency_config_json if hasattr(_a, "consistency_config_json") and _a.consistency_config_json else "{}"
                old_pvs = list(self.db.scalars(select(AssetPreview).where(AssetPreview.asset_id == _a.id)))
                for _pv in old_pvs:
                    pkey = (_a.asset_type, _a.canonical_name, _pv.preview_role)
                    canon_preview_to_tags[pkey] = (
                        getattr(_pv, "camera_tag", "") or "",
                        getattr(_pv, "pose_tag", "") or "",
                        getattr(_pv, "lighting_tag", "") or "",
                    )
        except Exception:
            canon_to_consistency.clear()
            canon_preview_to_tags.clear()

        self.db.execute(delete(AssetPreview).where(AssetPreview.project_id == project.id))
        self.db.execute(delete(AssetBinding).where(AssetBinding.project_id == project.id))
        self.db.execute(delete(Asset).where(Asset.project_id == project.id))

        now = utc_now_iso()
        created: list[Asset] = []

        def make_asset(asset_type: str, spec: dict) -> Asset:
            ckey = (asset_type, spec["canonical_name"])
            cons_json = canon_to_consistency.get(ckey, "{}") or "{}"
            return Asset(
                id=new_id(),
                project_id=project.id,
                asset_type=asset_type,
                name=spec.get("display_name") or spec["canonical_name"],
                canonical_name=spec["canonical_name"],
                description=spec.get("description") or "",
                cover_image_path="",
                consistency_config_json=cons_json,
                status=JobStatus.PENDING.value,
                created_at=now,
                updated_at=now,
            )

        for c in characters:
            created.append(make_asset(AssetType.CHARACTER.value, c))
        for loc in locations:
            created.append(make_asset(AssetType.SCENE.value, loc))
        for p in props:
            created.append(make_asset(AssetType.PROP.value, p))

        self.db.add_all(created)
        self.db.flush()

        default_bindings: list[AssetBinding] = []
        for asset in created:
            default_bindings.append(
                AssetBinding(
                    id=new_id(),
                    project_id=project.id,
                    asset_id=asset.id,
                    variant_id=None,
                    created_at=now,
                    updated_at=now,
                    status=JobStatus.COMPLETED.value,
                    binding_mode="NO_LORA",
                    lora_enabled=0,
                    lora_file_path="",
                    lora_weight=0.75,
                    trigger_word="",
                    ip_adapter_enabled=0,
                    ip_adapter_weight=0.60,
                    reference_image_paths_json="[]",
                    decouple_clothes=1,
                )
            )
        preview_rows: list[AssetPreview] = []
        for asset in created:
            plan = self._build_preview_plan(asset, style_terms)
            for entry in plan:
                pkey = (asset.asset_type, asset.canonical_name, entry["preview_role"])
                tags = canon_preview_to_tags.get(pkey, ("", "", ""))
                cam_t, pose_t, light_t = tags
                cons = _load_consistency(asset)
                if not cam_t:
                    cm_parts = []
                    mc = cons.get("main_camera_tag") or ""
                    mp = cons.get("camera_move_preset") or ""
                    ma = cons.get("camera_180_axis") or ""
                    if mc: cm_parts.append(str(mc))
                    if mp: cm_parts.append(str(mp))
                    if ma: cm_parts.append(str(ma))
                    cam_t = ", ".join(cm_parts)
                if not light_t:
                    lm_parts = []
                    lp = cons.get("lighting_preset") or ""
                    lk = cons.get("lighting_color_temp_k") or 0
                    ld = cons.get("lighting_direction") or ""
                    ll = cons.get("lighting_lut") or ""
                    if lp: lm_parts.append(str(lp))
                    try:
                        if lk and int(lk) > 0: lm_parts.append(f"{int(lk)}K")
                    except Exception: pass
                    if ld: lm_parts.append(str(ld))
                    if ll: lm_parts.append(f"LUT:{ll}")
                    light_t = ", ".join(lm_parts)
                preview_rows.append(
                    AssetPreview(
                        id=new_id(),
                        project_id=project.id,
                        asset_id=asset.id,
                        preview_role=entry["preview_role"],
                        preview_label=entry["preview_label"],
                        prompt_text=entry["prompt"],
                        image_path="",
                        width=entry["width"],
                        height=entry["height"],
                        camera_tag=cam_t,
                        pose_tag=pose_t,
                        lighting_tag=light_t,
                        status=JobStatus.PENDING.value,
                        created_at=now,
                        updated_at=now,
                    )
                )
        if default_bindings:
            self.db.add_all(default_bindings)
        if preview_rows:
            self.db.add_all(preview_rows)
        self.db.commit()
        for asset in created:
            self.db.refresh(asset)
        for pr in preview_rows:
            self.db.refresh(pr)

        if settings.COMFYUI_CHECKPOINT:
            cover_tasks = [self._render_cover(a, style_terms, genre_style=project.genre_style) for a in created]
            preview_tasks = [self._render_preview(a, pr, style_terms, genre_style=project.genre_style) for pr in preview_rows for a in created if a.id == pr.asset_id]
            await asyncio.gather(*cover_tasks, *preview_tasks, return_exceptions=False)
            self.db.commit()

        project.current_step_unlock = max(project.current_step_unlock, 2)
        project.updated_at = utc_now_iso()
        self.db.commit()
        return created

    def list_assets(self, project_id: str) -> list[dict]:
        assets = list(
            self.db.scalars(
                select(Asset)
                .where(Asset.project_id == project_id)
                .order_by(
                    case(
                        (Asset.asset_type == AssetType.CHARACTER.value, 1),
                        (Asset.asset_type == AssetType.SCENE.value, 2),
                        (Asset.asset_type == AssetType.PROP.value, 3),
                        else_=99,
                    ),
                    Asset.name.asc(),
                )
            )
        )
        result: list[dict] = []
        for asset in assets:
            binding = self.db.scalar(
                select(AssetBinding).where(AssetBinding.asset_id == asset.id, AssetBinding.variant_id.is_(None))
            )
            cover_url = ""
            if asset.cover_image_path:
                try:
                    cover_url = _encode_media_url(to_relative_media_path(asset.cover_image_path), asset.updated_at)
                except Exception:
                    cover_url = ""
            refs_raw = json.loads(binding.reference_image_paths_json or "[]") if binding else []
            ref_urls: list[str] = []
            for ref in refs_raw:
                try:
                    ref_urls.append(_encode_media_url(to_relative_media_path(str(ref))))
                except Exception:
                    ref_urls.append("")
            preview_rows = list(
                self.db.scalars(
                    select(AssetPreview).where(AssetPreview.asset_id == asset.id).order_by(AssetPreview.created_at.asc())
                )
            )
            previews: list[dict] = []
            for pr in preview_rows:
                img_url = ""
                if pr.image_path:
                    try:
                        img_url = _encode_media_url(to_relative_media_path(pr.image_path), pr.updated_at)
                    except Exception:
                        img_url = ""
                previews.append(
                    {
                        "id": pr.id,
                        "preview_role": pr.preview_role,
                        "preview_label": pr.preview_label,
                        "prompt_text": pr.prompt_text,
                        "image_path": pr.image_path,
                        "image_url": img_url,
                        "width": pr.width,
                        "height": pr.height,
                        "camera_tag": pr.camera_tag if hasattr(pr, "camera_tag") else "",
                        "pose_tag": pr.pose_tag if hasattr(pr, "pose_tag") else "",
                        "lighting_tag": pr.lighting_tag if hasattr(pr, "lighting_tag") else "",
                        "status": pr.status,
                        "created_at": pr.created_at,
                        "updated_at": pr.updated_at,
                    }
                )
            consistency_config = _load_consistency(asset)
            cover_seed_prefix = str(_seed_from_id(asset.id, "COVER"))[:8]
            try:
                checkpoint_name = settings.COMFYUI_CHECKPOINT or ""
            except Exception:
                checkpoint_name = ""
            production_log = {
                "sampler": "euler",
                "steps": 24,
                "cfg": 7,
                "checkpoint": checkpoint_name,
                "seed_hash_prefix": cover_seed_prefix,
            }
            result.append(
                {
                    "id": asset.id,
                    "project_id": asset.project_id,
                    "asset_type": asset.asset_type,
                    "name": asset.name,
                    "canonical_name": asset.canonical_name,
                    "description": asset.description,
                    "status": asset.status,
                    "cover_image_path": asset.cover_image_path,
                    "cover_image_url": cover_url,
                    "consistency_config": consistency_config,
                    "production_log": production_log,
                    "previews": previews,
                    "binding": None
                    if not binding
                    else {
                        "id": binding.id,
                        "binding_mode": binding.binding_mode,
                        "lora_enabled": bool(binding.lora_enabled),
                        "lora_file_path": binding.lora_file_path,
                        "lora_weight": binding.lora_weight,
                        "trigger_word": binding.trigger_word,
                        "ip_adapter_enabled": bool(binding.ip_adapter_enabled),
                        "ip_adapter_weight": binding.ip_adapter_weight,
                        "reference_image_paths": refs_raw,
                        "reference_image_urls": ref_urls,
                        "decouple_clothes": bool(binding.decouple_clothes),
                    },
                }
            )
        return result

    def save_binding(self, asset: Asset, req: BindingRequest) -> AssetBinding:
        binding = self.db.scalar(select(AssetBinding).where(AssetBinding.asset_id == asset.id, AssetBinding.variant_id.is_(None)))
        now = utc_now_iso()

        if not binding:
            binding = AssetBinding(
                id=new_id(),
                project_id=asset.project_id,
                asset_id=asset.id,
                variant_id=None,
                created_at=now,
                updated_at=now,
                status=JobStatus.COMPLETED.value,
                binding_mode=req.binding_mode,
                lora_enabled=1 if req.lora_enabled else 0,
                lora_file_path=req.lora_file_path,
                lora_weight=req.lora_weight,
                trigger_word=req.trigger_word,
                ip_adapter_enabled=1 if req.ip_adapter_enabled else 0,
                ip_adapter_weight=req.ip_adapter_weight,
                reference_image_paths_json=json.dumps(req.reference_image_paths, ensure_ascii=False),
                decouple_clothes=1 if req.decouple_clothes else 0,
            )
            self.db.add(binding)
        else:
            binding.updated_at = now
            binding.binding_mode = req.binding_mode
            binding.lora_enabled = 1 if req.lora_enabled else 0
            binding.lora_file_path = req.lora_file_path
            binding.lora_weight = req.lora_weight
            binding.trigger_word = req.trigger_word
            binding.ip_adapter_enabled = 1 if req.ip_adapter_enabled else 0
            binding.ip_adapter_weight = req.ip_adapter_weight
            binding.reference_image_paths_json = json.dumps(req.reference_image_paths, ensure_ascii=False)
            binding.decouple_clothes=1 if req.decouple_clothes else 0

        asset_project = self.db.get(Project, asset.project_id)
        if asset_project:
            total_assets = self.db.scalar(select(func.count()).select_from(Asset).where(Asset.project_id == asset.project_id)) or 0
            total_bindings = self.db.scalar(select(func.count()).select_from(AssetBinding).where(AssetBinding.project_id == asset.project_id)) or 0
            if total_assets and total_bindings >= total_assets:
                asset_project.current_step_unlock = max(asset_project.current_step_unlock, 3)
                asset_project.updated_at = now

        self.db.commit()
        self.db.refresh(binding)
        return binding

    def save_consistency(self, asset: Asset, req: SaveConsistencyRequest) -> Asset:
        now = utc_now_iso()
        raw_dict = req.model_dump(
            exclude={"preview_camera_tags", "preview_pose_tags", "preview_lighting_tags"},
        )
        config_json = json.dumps(raw_dict, ensure_ascii=False)
        asset.consistency_config_json = config_json
        asset.updated_at = now
        preview_cam_map = req.preview_camera_tags or {}
        preview_pose_map = req.preview_pose_tags or {}
        preview_light_map = req.preview_lighting_tags or {}
        all_roles = set(preview_cam_map.keys()) | set(preview_pose_map.keys()) | set(preview_light_map.keys())
        for role in all_roles:
            pr = self.db.scalar(
                select(AssetPreview).where(
                    AssetPreview.asset_id == asset.id,
                    AssetPreview.preview_role == role,
                )
            )
            if not pr:
                continue
            if role in preview_cam_map:
                pr.camera_tag = str(preview_cam_map[role] or "").strip()
            if role in preview_pose_map:
                pr.pose_tag = str(preview_pose_map[role] or "").strip()
            if role in preview_light_map:
                pr.lighting_tag = str(preview_light_map[role] or "").strip()
            pr.updated_at = now
        self.db.commit()
        self.db.refresh(asset)
        return asset
