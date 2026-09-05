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
    ("束发", "long black hair tied up in traditional topknot with jade hairpin, hair tied back in neat bun, forehead clear"),
    ("长发", "very long flowing black hair cascading down back past waist, straight shiny smooth texture"),
    ("长发披肩", "long loose hair flowing over shoulders down to chest"),
    ("盘发", "elaborate traditional coiffure updo with golden hair ornaments"),
    ("刘海", "bangs fringe swept to the side covering forehead,刘海斜分"),
    ("齐刘海", "straight blunt bangs evenly covering eyebrows,齐刘海"),
    ("青年男", "young handsome man around 20 years old, tall athletic build, male"),
    ("少女女", "young beautiful woman around 18 years old, slender graceful figure, female"),
    ("中年男", "mature middle aged man, experienced weathered face, male, 40s age appearance"),
    ("少女", "young beautiful woman around 18 years old, slender graceful figure, female"),
    ("青年", "young person around 20 years old"),
    ("男", "male gender, man"),
    ("女", "female gender, woman"),
    ("九岁", "nine-year-old pre-teen young boy, childlike facial features, age 9"),
    ("十岁", "ten-year-old child, 10s age appearance"),
    ("少年男", "young teen boy 13-16 years old, delicate youthful features, adolescent age male"),
    ("少年", "young teen aged person"),
    ("青年女", "young woman 18-25 years old, youthful graceful features, female"),
    ("老年男", "elderly senior old man, white or grey beard and hair, deeply wrinkled sagely face, male 60s age appearance"),
    ("老年女", "elderly senior old woman, grey hair styled in bun, wrinkled kind face, female 60s age appearance"),
    ("中年/老年男", "middle-aged to elderly senior taoist man, aged wrinkles around eyes and mouth, wise experienced solemn face, male"),
    ("少年/青年男", "young teen boy to early 20s young man, growing into adult features, male adolescent to young adult transition"),
    ("黑发", "jet black natural hair color"),
    ("棕发", "dark chestnut brown hair color"),
    ("白发", "silver white grey hair color, snowy white hair"),
    ("金发", "golden blonde hair color"),
    ("红发", "auburn crimson red hair color"),
    ("瞳孔", "default dark brown eyes"),
    ("黑眸", "deep dark black pupil eyes, solemn dark eyes"),
    ("褐眸", "warm brown amber eyes, brown pupil"),
    ("蓝眸", "clear ice blue pupil eyes, sapphire blue eyes"),
    ("绿眸", "emerald forest green pupil eyes"),
    ("红眸", "crimson blood red pupil eyes, scarlet glowing eyes"),
    ("紫眸", "royal purple amethyst pupil eyes"),
    ("金眸", "shining golden amber pupil eyes"),
    ("长剑", "wears or carries a long straight sword at waist"),
    ("医仙", "carries medicinal herbs and silver acupuncture needle pouch"),
    ("侠客", "wandering martial artist swordsman, practical travel worn robes"),
    ("书生", "scholar with book scroll tucked in robe, refined scholarly air"),
    ("将军", "military general in ornate armor, commanding imposing presence"),
    ("公主", "royal princess with golden headdress, exquisite palace robes"),
    ("道袍", "traditional wide-sleeved taoist priest robe"),
    ("青色道袍", "qing-blue colored taoist priest robe with wide flowing sleeves, plain austere matte linen-cotton fabric"),
    ("短褂", "short tunic jacket cropped above hip level"),
    ("长衫", "long robe gown reaching ankle level, full length tunic"),
    ("裙子", "long layered pleated skirt"),
    ("马面裙", "traditional horse-face structured pleated skirt"),
    ("葫芦", "gourd bottle pouch hanging at waist"),
    ("缺口的葫芦", "broken gourd bottle with chipped rim hanging at waist, worn cracked bamboo gourd flask, prominent visible chip on mouth"),
    ("腰间挂", "pendant or bottle prominently hanging at waist belt sash"),
    ("灰布短褂", "worn tattered grey cotton cloth short tunic jacket, peasant commoner clothing"),
    ("洗得发白", "faded washed white cotton fabric, threadbare worn overwashed texture"),
    ("左手缠着白色布条", "left hand and forearm wrapped in white cotton bandage cloth strips, bandaged left arm"),
    ("腕骨上刻满符文", "rune spell sigil tattoos carved deeply into wrist bones, visible mystical ink tattoos on wrist"),
    ("布靴", "traditional hand-made linen wrapped cloth boots"),
    ("麻鞋", "coarse woven hemp straw sandals"),
    ("云靴", "ornate embroidered cloud-pattern warrior leather boots"),
    ("木履", "wooden geta clogs sandals with cloth straps"),
    ("官靴", "official black leather mandarin boots with thick sole"),
    ("丝绸", "smooth glossy silk satin fabric with subtle sheen"),
    ("麻布", "coarse woven linen hemp fabric, textured rustic surface"),
    ("织锦", "rich brocade jacquard woven fabric with gold thread embroidery"),
    ("皮革", "genuine aged leather with worn patina texture"),
    ("刺绣", "intricate hand embroidery stitching on garment surface"),
    ("玉佩", "carved jade pendant ornament hanging from belt sash"),
    ("簪子", "ornamental hairpin with jade or pearl top securing updo"),
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


CHAR_FIELD_HINTS_AGE: list[tuple[str, str]] = [
    ("九岁", "9 years old"),
    ("十岁", "10 years old"),
    ("少年", "14 years old"),
    ("少女", "18 years old"),
    ("青年", "22 years old"),
    ("中年", "45 years old"),
    ("老年", "65 years old"),
    ("成年", "30 years old"),
]
CHAR_FIELD_HINTS_GENDER: list[tuple[str, str]] = [
    ("男", "male"),
    ("女", "female"),
    ("少年", "male"),
    ("少女", "female"),
    ("公主", "female"),
    ("将军", "male"),
    ("书生", "male"),
    ("侠客", "male"),
    ("道袍", "unisex taoist robe, male character if not otherwise specified"),
]
CHAR_FIELD_HINTS_HAIR: list[tuple[str, str]] = [
    ("束发", "hair tied up in traditional topknot with jade hairpin"),
    ("长发", "very long straight hair cascading down back"),
    ("长发披肩", "long loose hair flowing over shoulders"),
    ("盘发", "elaborate traditional coiffure updo with golden ornaments"),
    ("刘海", "side-swept bangs covering forehead"),
    ("齐刘海", "straight blunt bangs evenly across eyebrows"),
    ("短发", "short cropped hair cut to ear level"),
]
CHAR_FIELD_HINTS_HAIR_COLOR: list[tuple[str, str]] = [
    ("黑发", "jet black hair,刘海方向: swept to right side"),
    ("棕发", "dark chestnut brown hair,刘海方向: swept to left"),
    ("白发", "silver snowy white hair,刘海方向: middle part"),
    ("金发", "golden blonde hair,刘海方向: swept fringe"),
    ("红发", "crimson red auburn hair,刘海方向: side part"),
]
CHAR_FIELD_HINTS_EYE: list[tuple[str, str]] = [
    ("黑眸", "deep dark black eyes"),
    ("褐眸", "warm amber brown eyes"),
    ("蓝眸", "clear ice sapphire blue eyes"),
    ("绿眸", "emerald forest green eyes"),
    ("红眸", "crimson scarlet red eyes"),
    ("紫眸", "royal amethyst purple eyes"),
    ("金眸", "shining golden amber eyes"),
    ("瞳孔", "dark brown eyes"),
]
CHAR_FIELD_HINTS_FACE: list[tuple[str, str]] = [
    ("英气", "heroic sharp jawline, dignified noble facial temperament气质: dignified heroic"),
    ("灵动", "lively expressive big eyes, gentle soft features气质: lively vivid"),
    ("温婉", "soft gentle oval face, graceful feminine aura气质: gentle graceful"),
    ("冷艳", "cool stoic high cheekbones, icy regal beauty气质: cold elegant"),
    ("灵动", "lively vivid temperament"),
    ("沧桑", "weathered experienced wrinkles around eyes, solemn wise气质: solemn wise"),
    ("稚气", "childlike round face, innocent youthful temperament气质: innocent childish"),
]
CHAR_FIELD_HINTS_TOP: list[tuple[str, str]] = [
    ("青衫", "上衣: azure-blue flowing hanfu robe, silk satin material, wide embroidered sleeves"),
    ("青色道袍", "上衣: qing-blue matte linen-cotton taoist priest robe, wide flowing sleeves, cross-collar closed with knot button, plain unadorned"),
    ("白衣", "上衣: elegant pure white flowing hanfu robes, fine silk material, layered cross collar"),
    ("红衣", "上衣: crimson red embroidered hanfu, brocade jacquard silk, gold phoenix motifs"),
    ("黑袍", "上衣: dark black mysterious hanfu robes, heavy silk, subtle cloud pattern embroidery"),
    ("灰布短褂", "上衣: faded washed-white grey cotton short tunic jacket, cropped above hips, peasant commoner clothing, frayed cuffs, worn threadbare texture"),
    ("短褂", "上衣: short cropped tunic jacket, cotton material, simple style"),
    ("长衫", "上衣: ankle-length long robe gown, silk brocade material, mandarin collar"),
    ("道袍", "上衣: traditional wide-sleeved taoist priest robe, matte linen cotton material, cross collar wrap closure"),
]
CHAR_FIELD_HINTS_BOTTOM: list[tuple[str, str]] = [
    ("白裙", "下装: white layered pleated silk skirt, horse-face structured style"),
    ("马面裙", "下装: traditional horse-face structured pleated skirt, rich silk material"),
    ("裙子", "下装: long layered pleated silk skirt"),
    ("长裤", "下装: matching fabric loose straight trousers, full length to ankle"),
    ("道袍", "下装: matching robe lower garment same color as top, full flowing silhouette"),
    ("短褂", "下装: dark indigo cotton trousers tucked into cloth boots, faded matching grey tone"),
]
CHAR_FIELD_HINTS_SHOES: list[tuple[str, str]] = [
    ("布靴", "鞋履: traditional linen wrapped cloth boots, thick cotton sole"),
    ("麻鞋", "鞋履: coarse woven hemp straw sandals"),
    ("云靴", "鞋履: ornate embroidered cloud-pattern leather warrior boots"),
    ("木履", "鞋履: wooden geta clogs with red cloth straps"),
    ("官靴", "鞋履: official black leather mandarin boots, thick elevated sole"),
]
CHAR_FIELD_HINTS_BACK: list[tuple[str, str]] = [
    ("刺绣", "背部细节: intricate cloud embroidery pattern, gold silk stitching on upper back"),
    ("玉佩", "背部细节: carved jade pendant hanging from back waist sash"),
    ("长发", "背部细节: long flowing black hair covering upper back, smooth shiny texture"),
    ("盘发", "背部细节: elaborate updo securing hair on crown, golden hairpin visible at back of head"),
    ("道袍", "背部细节: wide back collar structure, central vertical seam, long hanging belt sash draped down center back, robe fabric folds visible"),
    ("葫芦", "背部细节: gourd bottle hanging from back waist sash on right side, cracked chipped rim visible"),
    ("左手缠着白色布条", "背部细节: left forearm bandage visible from behind, white cotton wrap strips"),
]


def _resolve_canonical_age_gender(combined_cn_text: str, extra_en_samples: list[str] | None = None) -> tuple[str, str]:
    """Single-source-of-truth age/gender canonical resolver shared between
    _parse_char_fields_cn_to_en, _zero_shot_auto_consistency and rebuild backup restoration.

    Age conflict resolution: pick smallest age bucket (9y child priority over 14y teen
    over 22y adult over 30y middle-aged over 45y senior over 65y elderly).
    Gender resolution: chinese character count ("男" vs "女") first, then english samples.
    """
    extra_en = " ".join(extra_en_samples or []).lower()
    # --- age ---
    age_hits_en: list[str] = []
    for kw in ("9 years old", "10 years old", "14 years old", "18 years old",
               "22 years old", "30 years old", "45 years old", "65 years old"):
        if kw in extra_en:
            age_hits_en.append(kw)
    for _cn, _en in CHAR_FIELD_HINTS_AGE:
        if _cn in combined_cn_text:
            if _en not in age_hits_en:
                age_hits_en.append(_en)
    _AGE_SORT = {"9 years old": 0, "10 years old": 1, "14 years old": 2, "18 years old": 3,
                 "22 years old": 4, "30 years old": 5, "45 years old": 6, "65 years old": 7}
    if age_hits_en:
        age_hits_en.sort(key=lambda x: _AGE_SORT.get(x, 99))
        canonical_age = age_hits_en[0]
    else:
        if any(x in combined_cn_text for x in ("九岁", "9岁", "小孩", "儿童")):
            canonical_age = "9 years old"
        elif any(x in combined_cn_text for x in ("少年", "14岁", "十四岁")):
            canonical_age = "14 years old"
        elif any(x in combined_cn_text for x in ("中年", "40岁", "五十岁")):
            canonical_age = "45 years old"
        elif any(x in combined_cn_text for x in ("老年", "老者", "道长", "老人")):
            canonical_age = "65 years old"
        else:
            canonical_age = "22 years old"
    # --- gender ---
    cn_male = combined_cn_text.count("男") + sum(1 for x in ("少年", "道士", "公子", "皇帝", "少爷", "青年男子") if x in combined_cn_text)
    cn_female = combined_cn_text.count("女") + sum(1 for x in ("少女", "夫人", "皇后", "小姐", "姑娘", "丫鬟") if x in combined_cn_text)
    if cn_female > cn_male:
        canonical_gender = "female"
    elif any(x in extra_en for x in (" female ", " girl ", " woman ", " lady ")):
        canonical_gender = "female"
    elif any(x in extra_en for x in (" male ", " boy ", " man ", " gentleman ")):
        canonical_gender = "male"
    else:
        canonical_gender = "male"
    return canonical_age, canonical_gender


def _age_bucket_keywords(canonical_age: str) -> set[str]:
    """Return EN keywords that a valid face description MUST mention (any one)
    for the given canonical age. Used to dedupe multi-age face_tags arrays."""
    s: set[str] = set()
    a = canonical_age.lower()
    if "9 years" in a or canonical_age == "9 years old":
        s |= {"nine-year", "9 years", "pre-teen", "child", "childlike", "little boy", "little girl", "boy kid", "girl kid", "young boy", "young child"}
    elif "14 years" in a:
        s |= {"14 years", "teen", "teenager", "adolescent", "young teen"}
    elif "18 years" in a or "22 years" in a:
        s |= {"18 years", "22 years", "young adult", "early 20s", "young person around 20", "young handsome man around 20", "young woman around 20", "young man", "young woman"}
    elif "30 years" in a:
        s |= {"30 years", "thirty", "middle-aged", "mature adult"}
    elif "45 years" in a or "65 years" in a:
        s |= {"45 years", "65 years", "elderly", "senior", "old man", "old woman", "wrinkled sagely", "aged wrinkles", "middle-aged to elderly senior", "deeply wrinkled", "white or grey beard"}
    else:
        s |= {"young adult", "early 20s"}
    return s


def _gender_mismatch_keywords(canonical_gender: str) -> set[str]:
    """Return EN keywords that a face description for canonical_gender MUST NOT contain."""
    if canonical_gender == "female":
        return {"man,", " man ", "boy,", " boy ", "male gender, man", "young man", "handsome man", "elderly man", "old man", "gentleman", "king,", "emperor", "prince,"}
    # male
    return {"woman,", " woman ", "girl,", " girl ", "female gender, woman", "young woman", "beautiful woman", "elderly woman", "old woman", "lady,", "queen,", "empress,", "princess,", "concubine"}


def _dedupe_face_tags_by_age_gender(face_list: list[str], canonical_age: str, canonical_gender: str) -> list[str]:
    """Filter a raw face_tags list to keep only entries matching the canonical age bucket
    AND matching canonical gender. Preserves original order (dict.fromkeys). If after
    filtering the list is empty, synthesize exactly ONE deterministic canonical face line.

    Rule: entries that mention "aged up" are ONLY kept when canonical_age bucket is adult (18y+),
    otherwise dropped because "aged up" describes a future version of a child character.
    """
    if not face_list:
        return []
    age_kw = _age_bucket_keywords(canonical_age)
    bad_gender_kw = _gender_mismatch_keywords(canonical_gender)
    is_adult_bucket = canonical_age in ("18 years old", "22 years old", "30 years old", "45 years old", "65 years old")

    kept: list[str] = []
    for raw in face_list:
        entry = (raw or "").strip()
        if not entry:
            continue
        low = f" {entry.lower()} "
        # 1) gender mismatch: drop
        if any(bg in low for bg in bad_gender_kw):
            continue
        # 2) "aged up" only for adult buckets
        if ("aged up" in low or "older teen" in low or "ten years later" in low or "growing into adult features" in low) and not is_adult_bucket:
            continue
        # 3) age bucket match required (any 1 keyword)
        if not any(ak in low for ak in age_kw):
            # allow generic "consistent identical face same person" guardrail
            if not ("consistent identical face" in low or "clear recognizable portrait" in low):
                continue
        kept.append(entry)
    # dedupe (order-preserving)
    kept = list(dict.fromkeys(kept))
    # if empty -> synthesize 1 line exactly matching canonical_age+gender
    if not kept:
        age_placeholder = canonical_age
        if canonical_gender == "female":
            if canonical_age == "9 years old":
                kept = ["nine-year-old pre-teen young girl, childlike round soft facial features, age 9, female child"]
            elif canonical_age == "14 years old":
                kept = ["14-year-old teen girl, youthful delicate soft features, young adolescent female"]
            elif canonical_age == "45 years old" or canonical_age == "65 years old":
                kept = ["elderly senior middle-aged woman, wrinkled mature feminine facial features, dignified solemn lady face"]
            else:
                kept = ["beautiful young woman around 20 years old, elegant feminine facial features"]
        else:
            if canonical_age == "9 years old":
                kept = ["nine-year-old pre-teen young boy, childlike round soft facial features, age 9, male child"]
            elif canonical_age == "14 years old":
                kept = ["14-year-old teen boy, youthful delicate soft features, young adolescent male"]
            elif canonical_age == "45 years old" or canonical_age == "65 years old":
                kept = ["solemn wise old man face, wrinkled mature masculine facial features, elderly senior man"]
            else:
                kept = ["young handsome man around 20 years old, tall athletic build, clear masculine features"]
        # (fallback unreachable, kept was filled above)
    return kept


def _filter_text_by_canonical_age_gender(text: str, canonical_age: str, canonical_gender: str) -> str:
    """v7 helper: split comma-delimited prompt text into segments, drop any segment that:
    (a) contains an "XX years old" phrase NOT equal to canonical_age, OR
    (b) contains any gender-mismatch keywords for canonical_gender.
    Keeps order; drops empty segments. Returns cleaned text (may be empty).

    Used to scrub description_en / lock_outfit free-text fields that may have multi-age
    generic keywords leaking in from CHARACTER_EN_KEYWORDS map (e.g. "青年" -> both 9y and
    20y phrases).
    """
    if not text:
        return ""
    age_kw = _age_bucket_keywords(canonical_age)
    bad_gender_kw = _gender_mismatch_keywords(canonical_gender)
    canonical_age_num = (canonical_age or "").strip().lower()
    out: list[str] = []
    for seg in text.split(","):
        s = seg.strip()
        if not s:
            continue
        low = f" {s.lower()} "
        # 1) skip mismatched gender segments
        if any(bg in low for bg in bad_gender_kw):
            continue
        # 2) skip segments that carry foreign XX years old phrase
        foreign_age = False
        for m in __import__("re").finditer(r"(\d+ years old)", low):
            phrase = m.group(1)
            if phrase != canonical_age_num:
                foreign_age = True
                break
        if foreign_age:
            continue
        # 3) for age-sensitive bucket keywords: if segment has age-adult carry words
        #    but bucket is child, drop (e.g. "young handsome man around 20" in 9y bucket)
        is_adult_bucket = canonical_age in ("18 years old", "22 years old", "30 years old", "45 years old", "65 years old")
        if not is_adult_bucket:
            adult_carry = ("young handsome man around 20", "young person around 20",
                           "young woman around 20", "beautiful young woman around 20",
                           "older teen to young adult version ten years later", "aged up",
                           "growing into adult features", "young teen boy to early 20s")
            if any(carry in low for carry in adult_carry):
                continue
        # keep segment (order-preserving)
        out.append(s)
    return ", ".join(dict.fromkeys(out))


def _parse_char_fields_cn_to_en(asset: Asset) -> dict[str, str]:
    """Parse 6 character appearance categories (age/gender/hair color/eye/face/outfit/shoes/back)
    directly from asset.name + asset.description via 9 mapping tables above,
    filling user's strict 左侧面板/中间面板/右侧面板 template fields."""
    combined = f"{asset.name or ''} {asset.description or ''}"
    def pick(mapping: list[tuple[str, str]], default: str) -> str:
        hits = _map_keywords(combined, mapping)
        if hits:
            joined = "; ".join(dict.fromkeys(hits).keys())
            return joined if joined else default
        return default
    _age_raw = pick(CHAR_FIELD_HINTS_AGE, "early 20s")
    _gender_raw = pick(CHAR_FIELD_HINTS_GENDER, "male")
    # v6: delegate to shared resolver (SSOT) — guarantees age single-solution + gender binary
    age, gender = _resolve_canonical_age_gender(
        combined,
        extra_en_samples=[s.strip() for s in _age_raw.split(";") if s.strip()] +
                         [s.strip() for s in _gender_raw.split(";") if s.strip()],
    )
    hair_desc = pick(CHAR_FIELD_HINTS_HAIR, "long straight hair, tied neatly in traditional style")
    hair_color_dir = pick(CHAR_FIELD_HINTS_HAIR_COLOR, "jet black hair,刘海方向: swept to right side")
    eye = pick(CHAR_FIELD_HINTS_EYE, "dark brown eyes")
    face = pick(CHAR_FIELD_HINTS_FACE, "balanced oval face, neutral calm temperament气质: serene")
    top = pick(CHAR_FIELD_HINTS_TOP, "上衣: traditional period robes, natural linen material, simple style")
    bottom = pick(CHAR_FIELD_HINTS_BOTTOM, "下装: matching period trousers or skirt same fabric as top, full length")
    shoes = pick(CHAR_FIELD_HINTS_SHOES, "鞋履: traditional cloth boots, period appropriate footwear")
    back = pick(CHAR_FIELD_HINTS_BACK, "背部细节: smooth fabric back, clean collar structure, long waist sash ends hanging down")
    return {
        "age": age, "gender": gender, "hair": hair_desc, "hair_color_dir": hair_color_dir,
        "eye": eye, "face": face, "top": top, "bottom": bottom, "shoes": shoes, "back": back,
    }


UE8K_QUALITY_BASELINE_SFX = (
    "Unreal Engine 5 cinematic quality, photorealistic real-person 3D rendering, "
    "realistic human proportions according to Andrew Loomis ideal anatomy, "
    "hyper-detailed 8K skin texture with visible pore detail and subsurface scattering, "
    "physically-based real cloth fabric simulation correct drape and micro-wrinkle detail, "
    "authentic real hair strand rendering with individual follicle detail, "
    "clean pure seamless pure white studio background, subject centered in frame, "
    "standard 3-point studio lighting (key + fill + rim) with neutral white balance 6500K, "
    "full body head-to-toe framing, macro high detail, 8K UHD resolution, cinematic color grading"
)
UE8K_QUALITY_CHAR_ONLY = (
    "Unreal Engine 5 cinematic quality, photorealistic real-person 3D rendering, "
    "realistic human proportions Loomis ideal anatomy, "
    "8K hyperdetailed skin pore texture + subsurface scattering, "
    "real cloth PBR fabric simulation correct drape micro-wrinkle, "
    "individual follicle hair strand rendering, "
    "clean perfect pure white seamless studio background, subject centered, "
    "3-point studio lighting key fill rim neutral white balance 6500K, "
    "full body head-to-toe framing, 8K UHD, cinematic, masterpiece"
)
UE8K_QUALITY_SCENE_ONLY = (
    "Unreal Engine 5 cinematic quality, nanite geometry, lumen global illumination, "
    "ray traced reflections, photorealistic physically based rendering materials, "
    "real human 3D rendering style identical to character reference sheet, "
    "matched art style color palette tone, true 8K high detail, cinematic composition"
)
UE8K_QUALITY_PROP_ONLY = (
    "Unreal Engine 5 cinematic quality, photorealistic PBR material rendering, "
    "identical rendering pipeline and materials as character reference sheet, "
    "matched art style texture detail, 8K macro high detail, sharp focus, "
    "physically accurate metalness/roughness values"
)


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
            "group photo, environmental shot, out of frame body, face cut off, "
            "gender swap, sex change, different person, different face, unrelated person, "
            "opera makeup, theatrical Peking opera makeup, heavy stage makeup, costume drama makeup face paint, "
            "pink blush cheeks, heavy theatrical eyeliner, costume jewelry mismatched era, "
            "wardrobe change, random outfit variant, switching to different clothes style, "
            "overlapping figures, headless, missing head, extra head, extra body, three different people, "
            "different faces each panel, fabric swatch, textile texture sample, garment flat lay, "
            "no person, empty scene, sunglasses, eyewear, glasses, goggles, "
            "gold hoop earrings, dangling earrings mismatched era, "
            "duplicate persons, crowds of people, audience, bystanders"
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
                "chinese ancient mansion harem style",
                "mansion harem style",
                "harem style",
                "harem",
                "elegant court atmosphere",
                "traditional wide-sleeved taoist priest robe",
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
                "chinese ancient mansion harem style",
                "mansion harem style",
                "harem style",
                "harem",
                "ornate silk hanfu",
                "elegant court atmosphere",
            })
            extras.extend([
                "character design illustration",
                "highly detailed facial features and costume design",
                "locked identical character likeness across every angle and pose",
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
        """Prompt 前缀分层权重（最高→最低）:
        1. description_en (1.5) — 剧本里写死的角色描述 (from _asset_detail_keywords_en + 全中文原描述)
        2. lock_outfit (1.4) — 服装/配件锁定
        3. face_tags list (1.4) — 面部+年龄+性别特征
        4. core name_en
        5. trimmed_style terms (中低权重，放在最后)
        保证角色一致性不会被通用 style 词淹没 (harem/silk hanfu etc)

        v7: CHARACTER branch — BEFORE building weighted prefix, resolve canonical age/gender ONCE
        then scrub description_en, lock_outfit, face_tags free text segments through
        _filter_text_by_canonical_age_gender to eliminate foreign age phrases leaking from
        CHARACTER_EN_KEYWORDS generic hits (e.g. "少年" → both 9y child + 20y young man).
        """
        cons = consistency or {}
        description_en = _asset_detail_keywords_en(asset)
        description_raw = (asset.description or "").strip()
        lock_outfit = (cons.get("lock_outfit") or "").strip()
        face_tags_list = cons.get("face_tags") or []
        weighted: list[str] = []
        desc_raw_parts: list[str] = []

        # === v7 CHARACTER: sanitize description_en / lock_outfit / concatenated face_tags
        if asset.asset_type == AssetType.CHARACTER.value:
            _combined_cn = f"{asset.name or ''} {asset.description or ''}"
            _en_samples = [description_en or "", lock_outfit or ""]
            for t in face_tags_list:
                _en_samples.append(str(t))
            _can_age, _can_gender = _resolve_canonical_age_gender(_combined_cn, extra_en_samples=_en_samples)
            description_en = _filter_text_by_canonical_age_gender(description_en or "", _can_age, _can_gender)
            if lock_outfit:
                lock_outfit = _filter_text_by_canonical_age_gender(lock_outfit, _can_age, _can_gender)
            if face_tags_list:
                _joined_face = ", ".join(str(x).strip() for x in face_tags_list if str(x).strip())
                _joined_face = _filter_text_by_canonical_age_gender(_joined_face, _can_age, _can_gender)
                # re-split to list to preserve comma-join behaviour below
                face_tags_list = [s.strip() for s in _joined_face.split(",") if s.strip()]

        if description_en:
            desc_raw_parts.append(description_en)
        if description_raw and asset.asset_type == AssetType.CHARACTER.value and not description_en:
            desc_raw_parts.append(description_raw)
        if desc_raw_parts:
            weighted.append(f"({' '.join(desc_raw_parts)}:1.5)")
        if lock_outfit and asset.asset_type != AssetType.SCENE.value:
            weighted.append(f"({lock_outfit}:1.4)")
        if face_tags_list and asset.asset_type == AssetType.CHARACTER.value:
            cleaned_f = [str(t).strip() for t in face_tags_list if str(t).strip()]
            if cleaned_f:
                weighted.append(f"({', '.join(cleaned_f)}:1.4)")
        core_name = _asset_core_name_en(asset)
        trimmed_style = self._trim_style_for_asset_type(asset.asset_type, style_terms, consistency)
        joined_weighted = ", ".join(weighted)
        if joined_weighted:
            if description_en or lock_outfit:
                return f"{joined_weighted}, {core_name}, {trimmed_style}"
            return f"{joined_weighted}, {core_name}, {trimmed_style}"
        return f"{core_name}, {trimmed_style}"

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
        lock_outfit_extra = (
            ", identical face same person locked across three views, EXACT matching identical outfit design preserved, "
            "NO wardrobe change, NO face change, same person every view, strict consistent character identity"
        )
        if cons.get("lock_outfit"):
            lock_outfit_extra += (
                ", consistent identical outfit design, NO outfit variations, same costume every frame, "
                "exact matching robe color and pattern"
            )
        lighting = self._consistency_lighting_suffix(cons)
        lighting_suffix = f", {lighting}" if lighting else ""
        fields = _parse_char_fields_cn_to_en(asset)
        char_name_core = _asset_core_name_en(asset)

        panel_a_cn = (
            f"左列 正面全身照：{fields.get('age_cn') or fields['age']}岁 {fields.get('gender_cn') or fields['gender']}，"
            f"发型{fields.get('hair_cn') or fields['hair']}，发色刘海{fields.get('hair_color_cn') or fields['hair_color_dir']}，"
            f"瞳孔{fields.get('eye_cn') or fields['eye']}，{fields.get('face_cn') or fields['face']}，"
            f"身着 {fields.get('top_cn') or fields['top']}，{fields.get('bottom_cn') or fields['bottom']}，{fields.get('shoes_cn') or fields['shoes']}"
        )
        panel_b_cn = (
            f"中列 右侧面全身照：清晰侧脸轮廓下颌线颧骨线条，"
            f"后脑勺发尾特征{fields.get('hair_cn') or fields['hair']}，同款服装同色同面料"
        )
        panel_c_cn = (
            f"右列 背面全身照：背部标志性细节 {fields.get('back_cn') or fields['back']}，"
            f"同款服装背面结构腰带衣褶完全一致，同人同脸同服装"
        )
        layout_cn = (
            "一张横向三连参考定妆图，左中右三列并排，每列一张全身像，"
            "纯白无缝工作室背景，三列都是同一个人同一套服装同一脸型发色，绝不三列三个人，"
            "人物居中站立，全身从头到脚完整不裁剪，三列之间有细细的白色分割线分隔三栏，"
            "角色：" + (asset.name or char_name_core)
        )

        panel_a_en = (
            "LEFT COLUMN front full body view: "
            f"age {fields['age']}, gender {fields['gender']}, {fields['hair']}, {fields['hair_color_dir']}, "
            f"{fields['eye']}, {fields['face']}, wearing {fields['top']}, {fields['bottom']}, {fields['shoes']}"
        )
        panel_b_en = (
            "MIDDLE COLUMN right-side profile full body: clear side face jawline and cheek bone structure, "
            f"back-of-head hair tail detail: {fields['hair']}, same exact outfit fabric color and design as left column"
        )
        panel_c_en = (
            "RIGHT COLUMN back view full body directly from behind: "
            f"{fields['back']}, same outfit same fabric same colors same person same face as left column, "
            "robe collar structure waist belt sash drape from behind clearly visible"
        )
        layout_en = (
            "THREE VIEW CHARACTER REFERENCE SHEET, single wide horizontal image, three equal vertical columns side-by-side, "
            "one complete full-body head-to-toe standing person in each column, thin 6 pixel solid white vertical divider line "
            "between left-middle-right columns clearly separating three views, ABSOLUTELY ONLY ONE IDENTICAL PERSON repeated "
            "three times once per column, three total persons in the entire composite image one per column - NO EXTRA PEOPLE, "
            "NO crowd, NO overlapping figures, NO extra heads extra bodies, every column same identical face same identical "
            "hairstyle same identical outfit colors fabrics, clean pure white seamless studio background, neutral standing pose, "
            f"subject centered in column, {UE8K_QUALITY_CHAR_ONLY}, sharp focus, masterpiece, best quality, highres"
        )

        prefix = self._full_en_prompt_prefix(asset, style_terms, consistency)
        prompt = (
            f"{layout_cn}。{panel_a_cn}。{panel_b_cn}。{panel_c_cn}。"
            f"画风：真人3D渲染风格，虚幻引擎品质，写实人体比例，精细皮肤纹理，真实布料质感，"
            f"工作室标准三点打光，高细节8K，电影感。 {prefix}; "
            f"{layout_en}; [LEFT] {panel_a_en}; [MID] {panel_b_en}; [RIGHT] {panel_c_en}; "
            f"character core name: {char_name_core};{lock_outfit_extra}{lighting_suffix}"
        )
        return prompt, 1792, 768

    def _build_scene_cover_prompt(self, asset: Asset, style_terms: str, consistency: dict | None = None) -> tuple[str, int, int]:
        cons = consistency or {}
        anchor = (cons.get("scene_anchor_desc") or "").strip() or (asset.description or "").strip() or asset.name
        lighting_preset = (cons.get("lighting_preset") or "").strip().lower()
        if not lighting_preset:
            combined = f"{asset.name or ''} {asset.description or ''}"
            if "清晨" in combined or "早晨" in combined or "白天" in combined:
                lighting_preset = "bright natural daylight, clear midday sun"
            elif "黄昏" in combined or "夕阳" in combined or "落霞" in combined:
                lighting_preset = "warm sunset golden hour, long soft shadows"
            elif "夜晚" in combined or "夜间" in combined or "夜" in combined:
                lighting_preset = "low-key cool moonlight rim lighting, deep shadows"
            else:
                lighting_preset = "soft natural ambient light"
        time_season_raw = " ".join(t for t in ["清晨","黄昏","夜晚","白天","早晨","夕阳","落霞","夜间","春","夏","秋","冬","春季","夏季","秋季","冬季"] if t in (asset.description or "") or t in (asset.name or ""))
        time_season = (time_season_raw or "autumn daytime").strip()
        scene_name = asset.name
        scene_type_desc = _asset_detail_keywords_en(asset) or (f"{scene_name} location, cinematic film set environment")
        props_text = (
            "标志性陈设: prominent period-accurate architectural structures, authentic period furniture and props, "
            "historically correct decorative objects naturally placed"
        )
        composition = (
            "构图: wide cinematic establishing shot composition, slight low-angle to enhance scale, "
            "rule of thirds layout, negative space for storyboarding, foreground-to-background depth layers"
        )
        atmosphere_hints = []
        combined_s = f"{asset.name or ''} {asset.description or ''}"
        if "静" in combined_s or "无人" in combined_s: atmosphere_hints.append("quiet serene 安静")
        if "喧闹" in combined_s or "热闹" in combined_s: atmosphere_hints.append("lively bustling喧闹")
        if "空" in combined_s or "荒" in combined_s: atmosphere_hints.append("empty hollow空荡")
        if "湿" in combined_s or "雨" in combined_s or "雾" in combined_s: atmosphere_hints.append("damp moist湿润")
        if not atmosphere_hints: atmosphere_hints.append("atmospheric natural mood")
        atmosphere = ", ".join(atmosphere_hints)
        lighting_suffix = self._consistency_lighting_suffix(cons)
        lut_tag = (cons.get("lighting_lut") or "").strip()
        lut_suffix = f", {lut_tag} LUT color grade applied" if lut_tag else ""
        anchor_suffix = f", {anchor}" if anchor else ""
        prompt = (
            f"场景名称: {scene_name}; "
            f"场景描述: {scene_type_desc}, 时间季节 {time_season}, 光线来源与色调: {lighting_preset}, "
            f"{props_text}, {composition}, 氛围关键词: {atmosphere}; "
            f"画风要求: 与角色画风一致，真人3D渲染风格，虚幻引擎品质 (Unreal Engine 5 cinematic quality), "
            f"UE5 nanite geometry, lumen global illumination, ray traced reflections, "
            f"photorealistic physically based rendering materials, true 8K high detail, "
            f"matched rendering style color palette tone identical to character reference sheet; "
            f"{self._full_en_prompt_prefix(asset, style_terms, consistency)}, "
            f"cinematic wide establishing shot keyframe, beautiful detailed environment, "
            f"dramatic atmospheric lighting, masterpiece, best quality, highres, "
            f"wide angle composition, no people, environment only{anchor_suffix}{lighting_suffix}{lut_suffix}"
        )
        return prompt, 1536, 864

    def _build_prop_cover_prompt(self, asset: Asset, style_terms: str, consistency: dict | None = None) -> tuple[str, int, int]:
        """Template A: 独立道具 standalone material library asset (白底抠图 + 平视特写)."""
        lighting = self._consistency_lighting_suffix(consistency)
        lighting_suffix = f", {lighting}" if lighting else ""
        prop_name = asset.name
        prop_desc = _asset_detail_keywords_en(asset) or (asset.description or prop_name)
        combined_p = f"{asset.name or ''} {asset.description or ''}"
        state_hints = []
        if "旧" in combined_p or "破" in combined_p or "损" in combined_p or "缺口" in combined_p:
            state_hints.append("状态: aged weathered worn condition, scratches, patina, 旧破损")
        elif "新" in combined_p or "干净" in combined_p or "崭新" in combined_p:
            state_hints.append("状态: brand new mint condition, pristine clean 新干净")
        else:
            state_hints.append("状态: naturally aged authentic period wear 自然旧化")
        detail_hints = []
        if "纹" in combined_p or "刻" in combined_p or "符" in combined_p or "文" in combined_p:
            detail_hints.append("with engraved pattern/script/rune markings")
        if not detail_hints:
            detail_hints.append("fine craftsmanship detail visible")
        state_text = "; ".join(state_hints + detail_hints)
        lock_outfit_c = (consistency or {}).get("lock_outfit") or ""
        extra_lock = f", {lock_outfit_c}" if lock_outfit_c else ""
        prompt = (
            f"道具名称: {prop_name}; "
            f"道具描述: 类别 {prop_type_desc if (prop_type_desc:= _asset_detail_keywords_en(asset)) else 'period accurate historical prop'}, "
            f"{prop_desc}, {state_text}{extra_lock}; "
            f"构图要求: 平视 eye-level close-up composition, slight 15 degree angle reveal three-quarter detail, "
            f"centered symmetrical object placement; 背景要求: seamless pure white background cutout for material library, "
            f"no surrounding environment, isolated抠图; 光源方向: studio 3-point lighting key light from 45 degree upper left, "
            f"soft rim light from back right, gentle shadow on surface below; "
            f"{self._full_en_prompt_prefix(asset, style_terms, consistency)}, "
            f"centered product shot on pure seamless white studio background, "
            f"macro sharp textures on object surface, no people no background environment, "
            f"Unreal Engine 5 cinematic quality, photorealistic PBR material rendering, "
            f"matching character art style: identical rendering pipeline same materials same lighting as characters, "
            f"8K high detail, macro photography, sharp focus, masterpiece, best quality, high resolution{lighting_suffix}"
        )
        return prompt, 1024, 1024

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
            hard_lock_suffix = (
                ", identical face same person locked, EXACT matching identical outfit design preserved, "
                "NO wardrobe change, NO face change, same person every frame, strict consistent character identity"
            )
            char_suffix = f"{hard_lock_suffix}{lock_suffix}{lighting_suffix}{move_suffix}{axis_suffix}"
            fields = _parse_char_fields_cn_to_en(asset)
            return [
                {
                    "preview_role": "FRONT_FULL",
                    "preview_label": "正面全身",
                    "prompt": (
                        f"{prefix}, 一张清晰的正面全身照，人物正对镜头自然站立，"
                        f"年龄{fields.get('age_cn') or fields['age']}岁 性别{fields.get('gender_cn') or fields['gender']}，"
                        f"{fields.get('hair_cn') or fields['hair']}，{fields.get('hair_color_cn') or fields['hair_color_dir']}，"
                        f"{fields.get('eye_cn') or fields['eye']}，{fields.get('face_cn') or fields['face']}，"
                        f"身着 {fields.get('top_cn') or fields['top']}，{fields.get('bottom_cn') or fields['bottom']}，"
                        f"{fields.get('shoes_cn') or fields['shoes']}，"
                        f"纯白无缝工作室背景，{UE8K_QUALITY_CHAR_ONLY}，"
                        f"full body front view standing facing camera, masterpiece, best quality, "
                        f"highly detailed face and matching outfit, sharp focus{char_suffix}"
                    ),
                    "width": 768,
                    "height": 1152,
                },
                {
                    "preview_role": "SIDE_HALF",
                    "preview_label": "侧面半身",
                    "prompt": (
                        f"{prefix}, 一张清晰的右侧半身侧面照，90度正侧视角，"
                        f"展现清晰侧脸轮廓下颌线颧骨线条与鼻梁侧面剪影，"
                        f"{fields.get('hair_cn') or fields['hair']} 发型后脑勺发尾细节清晰可见，"
                        f"{fields.get('top_cn') or fields['top']} 同款服装同色同面料与正面照一致，"
                        f"纯白无缝工作室背景，{UE8K_QUALITY_CHAR_ONLY}，"
                        f"half-body right-side 90 degree profile view, clear jawline cheek silhouette, "
                        f"masterpiece, best quality, highres{char_suffix}"
                    ),
                    "width": 768,
                    "height": 1152,
                },
                {
                    "preview_role": "BACK_FULL",
                    "preview_label": "背面全身",
                    "prompt": (
                        f"{prefix}, 一张清晰的背面全身照，正后方视角拍摄，"
                        f"背部标志性细节：{fields.get('back_cn') or fields['back']}，"
                        f"后脑勺发尾细节 {fields.get('hair_cn') or fields['hair']}，"
                        f"与正面同款服装同样颜色同样面料，背面衣领结构腰带系法衣褶垂坠清晰可见，"
                        f"纯白工作室背景，{UE8K_QUALITY_CHAR_ONLY}，"
                        f"full body back view directly from behind, same outfit same fabric same colors, "
                        f"back robe collar waist belt sash drape clearly visible, "
                        f"masterpiece, best quality, highres{char_suffix}"
                    ),
                    "width": 768,
                    "height": 1152,
                },
                {
                    "preview_role": "FACE_CLOSEUP",
                    "preview_label": "面部表情特写",
                    "prompt": (
                        f"{prefix}, 一张面部肩膀以上大头特写，自然平静中性表情，"
                        f"年龄{fields.get('age_cn') or fields['age']}岁 性别{fields.get('gender_cn') or fields['gender']}，"
                        f"{fields.get('eye_cn') or fields['eye']} 瞳孔清晰，{fields.get('face_cn') or fields['face']}，"
                        f"{fields.get('hair_color_cn') or fields['hair_color_dir']}，"
                        f"真实自然皮肤纹理毛孔细节无戏曲妆容无浓妆无舞台妆无腮红无金耳环，"
                        f"纯白无缝工作室背景柔和打光，{UE8K_QUALITY_CHAR_ONLY}，"
                        f"tight close-up portrait shoulders up only, natural neutral calm expression, "
                        f"clean natural skin texture, no opera makeup no stage makeup, natural real face structure, "
                        f"masterpiece, best quality, high detail{char_suffix}"
                    ),
                    "width": 1024,
                    "height": 1024,
                },
            ]
        if asset.asset_type == AssetType.SCENE.value:
            scene_suffix = f"{lighting_suffix}{anchor_suffix}{lut_suffix}{move_suffix}{axis_suffix}"
            scene_name = asset.name
            scene_type = _asset_detail_keywords_en(asset) or asset.name
            combined_s = f"{asset.name or ''} {asset.description or ''}"
            if "清晨" in combined_s or "白天" in combined_s: time_season = "early morning autumn season"
            elif "黄昏" in combined_s or "夕阳" in combined_s: time_season = "sunset golden hour late autumn"
            elif "夜晚" in combined_s or "夜" in combined_s: time_season = "deep night early winter"
            else: time_season = "midday autumn season"
            light = (lighting if lighting else "soft natural ambient side lighting natural daylight color palette")
            atmosphere = "quiet serene empty spacious"
            if "喧闹" in combined_s or "热闹" in combined_s: atmosphere = "bustling lively crowded"
            elif "空" in combined_s or "荒" in combined_s: atmosphere = "empty hollow desolate abandoned"
            elif "湿" in combined_s or "雨" in combined_s or "雾" in combined_s: atmosphere = "damp moist misty dewy"
            return [
                {
                    "preview_role": "WIDE_PANORAMA",
                    "preview_label": "宽景全景",
                    "prompt": (
                        f"场景名称: {scene_name}。场景描述: 宽景全景视图，{scene_type}，{time_season}，光线 {light}，"
                        f"标志性陈设: 精确还原时代特征的建筑结构与陈设道具自然分布，"
                        f"构图: 超宽全景定场镜头，氛围: {atmosphere}。 "
                        f"{prefix}; ultra wide panoramic establishing shot, "
                        f"epic sweeping landscape vista, dramatic sky and volumetric weather, no humans no characters, "
                        f"{UE8K_QUALITY_SCENE_ONLY}, masterpiece, best quality, high detail{scene_suffix}"
                    ),
                    "width": 1792,
                    "height": 768,
                },
                {
                    "preview_role": "MID_ESTABLISH",
                    "preview_label": "中景主视角",
                    "prompt": (
                        f"场景名称: {scene_name}。场景描述: 中景主视角机位，{scene_type}，{time_season}，光线 {light}，"
                        f"标志性陈设: 演员可行走的空间路径与大型家具入口动线清晰，"
                        f"构图: 中景主镜头电影级构图，氛围: {atmosphere}。 "
                        f"{prefix}; medium shot main camera angle composition, "
                        f"practical film set layout with walkable space for character blocking, cinematic natural lighting, "
                        f"no people no characters, {UE8K_QUALITY_SCENE_ONLY}, 8K photorealism{scene_suffix}"
                    ),
                    "width": 1536,
                    "height": 864,
                },
                {
                    "preview_role": "ALT_ANGLE",
                    "preview_label": "切换机位角度",
                    "prompt": (
                        f"场景名称: {scene_name}。场景描述: 对角反向机位，{scene_type}，{time_season}，光线 {light}，"
                        f"标志性陈设: 完全相同的物体与时间点，"
                        f"构图: 对面角落或不同楼层高度的交替机位，氛围: {atmosphere}。 "
                        f"{prefix}; alternate camera angle from opposite corner or different floor level, "
                        f"same time same weather same color tone continuity for scene transition, lighting color matched exactly, "
                        f"no people no characters, {UE8K_QUALITY_SCENE_ONLY}, masterpiece{scene_suffix}"
                    ),
                    "width": 1536,
                    "height": 864,
                },
            ]
        prop_suffix = f"{lighting_suffix}"
        prop_name = asset.name
        prop_desc = _asset_detail_keywords_en(asset) or asset.description or prop_name
        combined_p = f"{asset.name or ''} {asset.description or ''}"
        prop_state = (
            "状态: aged weathered worn with scratches and patina 旧破损"
            if ("旧" in combined_p or "破" in combined_p or "损" in combined_p or "缺口" in combined_p)
            else ("状态: brand new mint pristine 新干净" if ("新" in combined_p or "崭新" in combined_p) else "状态: naturally aged authentic period 自然旧化")
        )
        return [
            {
                "preview_role": "FRONT_PRODUCT",
                "preview_label": "正面主视图",
                "prompt": (
                    f"一张独立的单个道具产品图，绝对聚焦在单个道具物体中心，"
                    f"模板A 独立道具。道具名称: {prop_name}。道具描述: 类别 符合时代的历史道具，"
                    f"{prop_desc}，{prop_state}。构图: 平视 eye-level 正面正视对称产品图，"
                    f"背景: 纯白无缝抠图 纯单色白色背景 孤立道具 无任何周围环境无人无背景；"
                    f"光源: 专业工作室三点打光 左上45度主光 右侧柔和补光 背面右后轮廓光。 "
                    f"{prefix}; centered symmetrical front view product photo, "
                    f"pure seamless solid white studio background cutout, single ONE object only, "
                    f"soft key 45deg upper-left light + fill + rim light setup, absolutely NO humans NO environment NO scenery, "
                    f"only the object fills frame, macro sharp textures on surface, "
                    f"{UE8K_QUALITY_PROP_ONLY}, 8K macro high detail, sharp focus, masterpiece, best quality{prop_suffix}"
                ),
                "width": 1024,
                "height": 1024,
            },
            {
                "preview_role": "IN_CONTEXT",
                "preview_label": "使用场景图",
                "prompt": (
                    f"单个道具处于匹配时代环境的场景剧照，道具作为绝对视觉焦点清晰锐利，背景自然虚化，"
                    f"模板B 场景中道具。场景名称: 与角色匹配的古风内饰外景；道具清单: 1x {prop_name}: 前景画面核心突出位置，{prop_desc}；"
                    f"场景描述: 与角色画风同一渲染管线的时代内饰外景，柔和自然日光照入，"
                    f"以上道具放置在 前景正中央桌面或角色手旁自然握持。 "
                    f"{prefix}; contextual hero shot of single object being held or placed naturally in matching interior setting, "
                    f"cinematic storytelling composition, soft bokeh shallow depth of field background, "
                    f"focus dead sharp on the object itself not background, "
                    f"{UE8K_QUALITY_PROP_ONLY}, identical rendering pipeline as characters same materials same color palette, "
                    f"8K high detail, masterpiece, best quality{prop_suffix}"
                ),
                "width": 1536,
                "height": 864,
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
                _raw_cons = _a.consistency_config_json if hasattr(_a, "consistency_config_json") and _a.consistency_config_json else "{}"
                # v6: CHARACTER backup-restore → DEDUPE existing face_tags to eliminate legacy
                # multi-age/multi-gender conflict entries (e.g. shenqi had 6 face_tags mixing 9yo boy + 20yo man)
                if _a.asset_type == AssetType.CHARACTER.value:
                    try:
                        _cons_dict = json.loads(_raw_cons or "{}") or {}
                        _face = _cons_dict.get("face_tags") or []
                        if isinstance(_face, list) and _face:
                            _cn_combined = f"{_a.name or ''} {_a.description or ''}"
                            _can_age, _can_gender = _resolve_canonical_age_gender(_cn_combined, extra_en_samples=list(_face))
                            _deduped = _dedupe_face_tags_by_age_gender([str(x) for x in _face], _can_age, _can_gender)
                            if _deduped != _face:
                                _cons_dict["face_tags"] = _deduped
                                _raw_cons = json.dumps(_cons_dict, ensure_ascii=False)
                    except Exception:
                        pass  # never fail backup restore on dedupe error; fall through to original
                canon_to_consistency[ckey] = _raw_cons
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

        def _zero_shot_auto_consistency(asset_type: str, spec: dict) -> str:
            """Zero-shot auto-fill ConsistencyConfig 18 flat keys when user has not manually configured it yet.
            - CHARACTER: lock_outfit = _asset_detail_keywords_en costume; face_tags = age/gender keyword list; style_extra_prompt = genre-appropriate; lighting_preset default soft_studio 5500K; main_camera_tag = medium_shot
            - SCENE: scene_anchor_desc = description; lighting_preset from first_seg time_weather; main_camera_tag = establishing_shot
            - PROP: lock_outfit = description; lighting_preset = studio_product
            """
            name = (spec.get("display_name") or spec.get("canonical_name") or "").strip()
            description = (spec.get("description") or "").strip()
            combined = f"{name} {description}"
            if asset_type == AssetType.CHARACTER.value:
                raw_detail = _map_keywords(combined, CHARACTER_EN_KEYWORDS)
                outfit_list: list[str] = []
                face_list: list[str] = []
                detail_style: list[str] = []
                OUTFIT_HINTS = ("robe", "hanfu", "tunic", "jacket", "gourd", "bandage", "cloth", "sword", "pouch", "armor", "cotton", "silk", "taoist", "headdress")
                FACE_HINTS = ("middle", "elderly", "senior", "young", "teen", "boy", "man", "girl", "woman", "wrinkled", "handsome", "beautiful", "pre-teen", "nine-year", "aged up")
                for kw in raw_detail:
                    k = kw.lower()
                    if any(h in k for h in OUTFIT_HINTS):
                        outfit_list.append(kw)
                    elif any(h in k for h in FACE_HINTS):
                        face_list.append(kw)
                    else:
                        detail_style.append(kw)
                # v6: resolve canonical age/gender ONCE, dedupe face_tags to eliminate
                # "20yo man + 9yo boy" multi-age conflict that breaks SD1.5 character locks.
                _can_age, _can_gender = _resolve_canonical_age_gender(combined, extra_en_samples=list(face_list) + list(outfit_list))
                face_list = [s for s in face_list if s and s.strip()]
                if face_list:
                    face_list = _dedupe_face_tags_by_age_gender(face_list, _can_age, _can_gender)
                if not outfit_list:
                    outfit_list = [description] if description else []
                if not face_list:
                    if "老年" in combined or "中年" in combined:
                        face_list = ["solemn wise old man face, wrinkled mature facial features"]
                    elif "少年" in combined or "九岁" in combined:
                        face_list = ["young teen boy face, youthful delicate soft features"]
                    else:
                        face_list = ["consistent identical face same person every frame, clear recognizable portrait features"]
                cfg = {
                    "lock_outfit": ", ".join(o.strip() for o in outfit_list if o and o.strip()) or (description if description else "traditional costume design locked"),
                    "face_tags": [f.strip() for f in face_list if f and f.strip()],
                    "style_extra_prompt": "xianxia wuxia historical period character design, sharp clean lines, high detail portrait consistency lock across all angles",
                    "style_lora_name": "",
                    "main_camera_tag": "medium shot",
                    "camera_move_preset": "",
                    "camera_180_axis": "",
                    "scene_anchor_desc": "",
                    "lighting_preset": "soft studio",
                    "lighting_color_temp_k": 5500,
                    "lighting_direction": "side_left",
                    "lighting_lut": "",
                    "pose_tags": {},
                    "voice_preset": "",
                    "voice_emotion_preset": "",
                    "voice_speed": 1.0,
                }
            elif asset_type == AssetType.SCENE.value:
                cfg = {
                    "lock_outfit": "",
                    "face_tags": [],
                    "style_extra_prompt": "cinematic period film set location, cohesive color grading, cinematic atmosphere continuity locked",
                    "style_lora_name": "",
                    "main_camera_tag": "establishing shot",
                    "camera_move_preset": "establishing",
                    "camera_180_axis": "",
                    "scene_anchor_desc": description if description else name,
                    "lighting_preset": "day" if ("清晨" in combined or "白天" in combined) else ("sunset_golden" if ("黄昏" in combined or "落霞" in combined or "夕阳" in combined) else ("night" if ("夜晚" in combined or "夜间" in combined or "夜" in combined) else "soft studio")),
                    "lighting_color_temp_k": 5800 if ("清晨" in combined or "白天" in combined) else (3300 if ("夜晚" in combined or "夜间" in combined) else 5500),
                    "lighting_direction": "top" if ("白天" in combined or "清晨" in combined) else "back",
                    "lighting_lut": "Kodak 2383" if ("夜晚" in combined) else "",
                    "pose_tags": {},
                    "voice_preset": "",
                    "voice_emotion_preset": "",
                    "voice_speed": 1.0,
                }
            else:
                cfg = {
                    "lock_outfit": description if description else f"{name} detailed object design",
                    "face_tags": [],
                    "style_extra_prompt": "antiques collectible product photography, period accurate materials and craftsmanship",
                    "style_lora_name": "",
                    "main_camera_tag": "close up product shot",
                    "camera_move_preset": "",
                    "camera_180_axis": "",
                    "scene_anchor_desc": "",
                    "lighting_preset": "soft studio",
                    "lighting_color_temp_k": 5200,
                    "lighting_direction": "top",
                    "lighting_lut": "",
                    "pose_tags": {},
                    "voice_preset": "",
                    "voice_emotion_preset": "",
                    "voice_speed": 1.0,
                }
            try:
                return json.dumps(cfg, ensure_ascii=False)
            except Exception:
                return "{}"

        def make_asset(asset_type: str, spec: dict) -> Asset:
            ckey = (asset_type, spec["canonical_name"])
            cons_json = canon_to_consistency.get(ckey, "") or ""
            if not cons_json or cons_json.strip() in ("", "{}"):
                cons_json = _zero_shot_auto_consistency(asset_type, spec)
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
