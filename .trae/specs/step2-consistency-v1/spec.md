# Step 2 资产池五维一致性规范落地 - Product Requirements Document

## Overview
- **Summary**：在 Step 2 资产池（Step2AssetsView）界面和后端资产服务（AssetService）中，完整落地 AI 漫剧/短剧 5 大一致性工作流规范：① 角色形象一致性（定妆三视图+特征锚点+常服锁死）② 视觉画风/艺术风格一致性（底模+风格 LoRA+正反 Prompt 模板锁死+参数归档）③ 场景与空间一致性（多视角底图资产化+主光源设定）④ 镜头语言与动作连贯性（角色 OpenPose/动作角度预设+运镜提示词模板）⑤ 影调布光与后期一致性（场景光环境预设+LUT 标签+TTS 音色标签）。
- **Purpose**：解决 Step2 只具备"出图"功能、缺乏"一致性生产级锁死机制"的问题，使最终 Step3-5 生成分镜/成片时能从资产池直接取用已经过 5 维标准化的资产配置，达到"可连载、可商业化"的连载级一致性。
- **Target Users**：AutoVision-AI 的作者（短剧 AI 生片创作者），以及后续项目中使用 Step2→Step3 Storyboard→Step4 Media→Step5 Export 的全链路用户。

## Goals
- 每一个 Step2 资产（CHARACTER/SCENE/PROP）必须能完整承载 5 维一致性配置字段与 UI 操作面板。
- 所有 5 维一致性配置必须可**持久化到 SQLite**，可通过 list_assets API 完整回显到前端，可通过 save API 保存。
- 5 维一致性配置必须**实时影响下一次 rebuild_assets**（例如：勾选了"常服锁死"后，rebuild 出的角色 4 角度服装绝对一致；勾选了"主光源夕阳光 2700K"后，下山路场景 3 张图光影一致）。
- 前端 Step2 每个资产卡片必须新增 2 个 Tab：「🔒 一致性配置」（包含 5 个维度子面板+输入项）和「🧾 制作日志/参数归档」（展示当前 seed、sampler、steps、cfg 等参数）。
- 建立一致性覆盖度评分：每个资产根据满足 5 维配置项的比例，在 UI 上以徽章显示（例如：一致性 3/5，颜色随分数变化）。

## Non-Goals
- 不涉及 Step3-5 实际调用 IP-Adapter / FaceID / OpenPose ControlNet / LoRA 推理管线的改动（本期仅保证 Step2 端到端产生并持久化**可被后续步骤消费的一致性配置结构和标准参考图资产**，不修改 Step3 Storyboard 出图代码）。
- 不新增实际 LoRA 训练 / 实际 IP-Adapter 推理服务器 / 实际 3D 导演台 Blender 集成。
- 不修改项目外的 ComfyUI workflow 节点定义 / 不增加新 ComfyUI custom nodes。
- 不做 TTS/音频一致性的实际生成（只在 SCENE 资产和 Project 级保存音色/LUT 配置标签供 Step4/Step5 读取字段占位）。

## Background & Context
- 项目现状：FastAPI 后端 + SQLite autovision.db；资产结构（Asset/AssetVariant/AssetBinding/AssetPreview）在 `backend/app/db/models/asset.py` 已完整建立。上一轮通过 [asset_service.py:L104-L513](file:///c:/Users/王丹/Documents/GitHub/AutoVision-AI/backend/app/services/asset_service.py#L104-L513) 已落地了英文 Prompt 映射 + SHA1 固定 Seed + 类型化 Negative，保证了当前项目 7 资产 29 张预览图主体正确。
- 用户刚投诉过并闭环的核心问题：青铜长剑画成山亭子（SD1.5 听不懂中文+Prompt 权重错位+随机 Seed）；人物 4 角度服装颜色完全不同（Seed 全随机）；下山路/窗前场景核心要素缺失（Prompt 主体词未前置）。
- 本轮用户的 5 维一致性规范是对 Step2"从一次性出图工具升维为生产级资产库"的核心定义，必须作为硬约束。
- 硬架构约束：
  - SQLite 缺列通过 `ensure_runtime_columns()`（main.py:L43-73）+ `Base.metadata.create_all` 自动兜底，必须向后兼容；
  - 前端必须在现有 Step2AssetsView.vue 卡片结构内新增子 Tab 布局，不得重构路由或父组件 ProjectWorkbench.vue 结构；
  - 当前 ComfyUI checkpoint=v1-5，底模/LoRA 模型名必须通过 settings.COMFYUI_CHECKPOINT / .env 读取 + 前端 UI 只读展示；
  - 所有字段存 JSON TEXT 列，避免 ALTER 频繁。

## Functional Requirements

### 5 大一致性维度功能（核心 1）
- **FR-1 角色形象一致性（CHARACTER 专属）**：
  - 提供「定妆三视图 Turnaround Sheet」3 个标准预览位命名（TURN_FRONT/TURN_SIDE/TURN_BACK），与 4 角预览共存并优先展示为徽章；
  - 「显著特征记忆点」3-6 条 tag 编辑器；
  - 「常服锁死开关」boolean，开启后 rebuild 的 clothes_prompt_override 固定且随机配饰全部从 negative 中屏蔽；
  - 「Ref Image 锚点图」3 格上传（FaceID/IP-Adapter 专用），独立于 AssetBinding.reference_image_paths 单独存储（字段结构清晰）。
- **FR-2 视觉画风与艺术风格一致性（所有类型通用）**：
  - 「底模锁定」只读展示 checkpoint 名 + 警告"不同底模会导致风格漂移，请勿中途换"；
  - 「风格 Style LoRA」下拉框 + 权重字段；
  - 「统一风格 Prompt 模板」只读显示当前 GENRE_STYLE_KEYWORDS 注入的 style_terms + editable 自定义附加词；
  - 「统一 Negative 规范化」只读展示当前 _extra_negative + genre_negative_extra + settings.COMFYUI_NEGATIVE_PROMPT 三段合并文本；
- **FR-3 场景与空间一致性（SCENE 专属）**：
  - 「多视角预览位」强约束：WIDE_PANORAMA/MID_ESTABLISH/ALT_ANGLE 必须各自打标"主视角/对侧视角/机位 B"徽章，并提供主相机标注 tag；
  - 「场景多空间锚点描述」textarea（关键家具/门窗方位）；
  - 「底图参考图」上传 2 格（Img2Img 垫图锚点）；
- **FR-4 镜头语言与动作连贯性（CHARACTER 可用；SCENE 标记机位）**：
  - 「角色动作预设」CHARACTER 每角预览位标记：FRONT_FULL 对应 standing T-pose；SIDE_HALF 对应 profile 90°；FACE_CLOSEUP 对应 shoulders up（可编辑）；
  - 「运镜提示词模板」CHARACTER 可选 push in / over shoulder；SCENE 可选 establishing / pan；
  - 「180°轴线标记」SCENE 对话框内可选左右；
- **FR-5 影调布光与后期一致性（所有类型通用，SCENE 强化）**：
  - 「主光源设定」SCENE：主光源类型（日/夕/夜/室内暖灯）+ 色温（K 值）+ 方向（顶/侧/逆）；
  - 「统一 LUT 调色标签」枚举：GUZHUANG_WARM / CINEMATIC_TEAL_ORANGE 等；
  - 「TTS/配音音色标签」CHARACTER：voice_preset + emotion_preset（供 Step4 读取占位字段）。

### 全局 CRUD 与前端交互（核心 2）
- **FR-6 数据层持久化**：一致性配置通过 asset.consistency_config_json TEXT JSON 大字段 + asset_preview 新增 3 列（preview_camera_tag/lighting_tag/pose_tag）完整持久化，ensure_runtime_columns 保证老库无损。
- **FR-7 list_assets API 回显**：list_assets 返回每个资产新增 consistency_config 对象（含 5 维子字段），每张 preview 返回 3 个新 tag；
- **FR-8 save_consistency_config API**：后端路由 POST /assets/{id}/consistency 专门接口，与 save_binding 解耦独立事务；
- **FR-9 前端卡片结构改造**：现有 4 结构（封面/预览网格/绑定模式表单/参考图）保留，新增 2 子 Tab「🔒 一致性配置」「🧾 制作日志」；一致性评分徽章显示在标题行；
- **FR-10 一致性配置实时驱动 rebuild**：勾选常服锁死/主光源设定后，下一次调用 rebuild_assets 时 Prompt/Negative 直接引用 consistency_config。

## Non-Functional Requirements
- **NFR-1（向后兼容）**：老项目（缺列/缺 JSON key）必须全量用字段默认值，零报错；UI 层对 undefined 字段显示占位文案。
- **NFR-2（性能）**：list_assets 解析 7 资产 JSON 耗时 < 20ms；不引入 N+1 查询。
- **NFR-3（类型安全）**：新增 Pydantic ConsistencyConfig Schema，所有字段带 Literal 枚举 / default_factory；前端 TypeScript 接口 interface 同步定义。
- **NFR-4（可验证）**：每项 AC 都有可观测的 rule/rubric，能通过 HTTP API + 浏览器快照验证。
- **NFR-5（可维护性）**：5 维度字段命名在 TS/Python/SQLite 三处完全一致；采用 camelCase in JSON / snake_case in DB / PascalCase in UI 标签。

## Constraints
- **Technical 1**：只允许向 assets 表新增 1 TEXT 列 `consistency_config_json` 和向 asset_previews 表新增 3 个 TEXT 列 `camera_tag TEXT / pose_tag TEXT / lighting_tag TEXT`；禁止新建除了 ConsistencyConfig schema 以外的独立表（保证轻量）。
- **Technical 2**：ComfyUI 推理不换模型，不新增节点；Prompt 改动仅限 asset_service 的 prompt 构造层。
- **Technical 3**：前端不得拆文件，所有改动在 Step2AssetsView.vue 单文件内（现有 595 行，可扩到 ~850 行）。
- **Business 1**：所有一致性字段**必须保证用户可以不填**，空值不影响现有出图逻辑。
- **Dependencies**：依赖 FastAPI lifespan + ensure_runtime_columns（已存在）；依赖已有 12 GENRE_STYLE_CHOICES（已存在）。

## Assumptions
- 用户会在 Step2 完成"资产冻结"后才进入 Step3 Storyboard，Step3 可直接读 consistency_config（本期 Step3 读结构不改代码）。
- ComfyUI 端未来会加 IP-Adapter/FaceID/OpenPose 节点时，本期保存的 ref_images/pose_tags 字段可直接复用，结构无需迁移。
- 用户对"可连载级一致性"的最低标准是：**全剧同角色不换脸+服装不变+同场景光影一致**，这三项是本期的核心 PASS 阈值。

## Acceptance Criteria

### AC-1：CHARACTER 卡展示 5 维一致性完整面板
- **Type**：`rule`
- **Given**：打开 Step2，Tab=人物 CHARACTER 2，卡片已展开（点击滚动到页面）
- **When**：点击卡片的「🔒 一致性配置」子 Tab
- **Then**：面板内存在 5 个维度分区（1-角色形象含三视图tag/显著特征/常服锁死/Ref图上传；2-画风；3-空间；4-镜头动作；5-影调布光+音色标签）
- **Pass Condition**：5 个分区全部 DOM 可见；每个分区至少 1 个可交互控件（input/select/textarea/checkbox）；"一致性 X/5"徽章标题行可见
- **Evidence**：browser_snapshot Step2 CHARACTER 卡片+一致性 Tab；snapshot 结构里至少出现 5 个 heading 分区标签

### AC-2：CHARACTER 「常服锁死」开关 rebuild 后 Prompt/Seed/Neg 生效
- **Type**：`rule`
- **Given**：凌风卡片勾选"常服锁死=true" + 显著特征填"azure-blue robe, jade hairpin, tear mole under left eye"并保存；项目 genre_style=GUZHUANG_XIANXIA
- **When**：调用 POST rebuild_assets，出图完成后凌风 FRONT_FULL / BACK_FULL prompt_text GET
- **Then**：① 两张预览 seed 完全相同（同角色 4 角 seed 同 hash 前缀）；② Prompt 明确包含常服锁死特征 3 项词汇；③ Negative 包含"random accessories, gradient fabric, different outfit"禁词
- **Pass Condition**：HTTP GET list_assets，凌风 4 预览 seed（可从 prompt_text 读 hash 验证）相同；prompt_text 包含 3 个特征词；negative 拼接含禁配饰
- **Evidence**：PowerShell / Python 脚本对 list_assets JSON 做 grep，3 项条件全 true

### AC-3：SCENE 「主光源设定」rebuild 后光影一致
- **Type**：`rule`
- **Given**：下山路 SCENE 卡设置主光源=sunset_golden_hour（夕阳光），色溫 2700K，方向=side_left，保存后 rebuild
- **When**：下山路 WIDE_PANORAMA + MID_ESTABLISH + ALT_ANGLE 三张预览 prompt_text GET
- **Then**：3 张 prompt 前缀都含"warm sunset golden hour lighting, 2700K color temperature, side left key light, long cast shadows"；lighting_tag 全部打标为"SUNSET_SIDE_2700K"
- **Pass Condition**：3 张 preview prompt_text 都包含"sunset golden hour"和"2700K"；lighting_tag 字段非空
- **Evidence**：list_assets JSON 3 张 preview 全部 grep 命中 + browser_take_screenshot 场景 Tab 下山路 3 缩略图色调肉眼呈金黄暖调

### AC-4：一致性配置持久化与 API 回显
- **Type**：`rule`
- **Given**：任意资产填好 5 维字段并 save（例如：青铜长剑 PROP 填风格词+Negative规范）
- **When**：FastAPI worker 重启（杀进程+重拉）后 GET list_assets 同资产
- **Then**：consistency_config 字段与重启前逐字段相等（deep equal）
- **Pass Condition**：Python 脚本 deepdiff diff=空；无任何缺 key 报错
- **Evidence**：save 前 JSON→存文件→重启后 GET→diff 输出 {} 0 differences

### AC-5：视觉画风一致性面板注入 rebuild Prompt
- **Type**：`rule`
- **Given**：任意资产卡设置 Style LoRA 权重=0.8 + 自定义风格附加词"misty atmospheric palette"并 save
- **When**：rebuild 后该资产 cover prompt_text GET
- **Then**：Prompt 含"misty atmospheric palette"；Negative 合并含三段（_extra_negative + COMFYUI_NEG + genre_negative_extra）文本
- **Pass Condition**：cover prompt_text 中命中自定义附加词；后端 debug 接口（或读 prompt_text）Negative 长度 > 300 chars（三段拼接）
- **Evidence**：grep list_assets JSON cover prompt_text 命中附加词

### AC-6：五维覆盖度评分徽章算法正确
- **Type**：`rubric`
- **Dimension**：Step2 卡片一致性覆盖度徽章直观性与算法正确性
- **Scale**：1-5
- **Anchors**：1 = 无徽章、算法错字；3 = 有徽章但颜色/算法不对应字段；5 = 徽章同时显示数字（X/5）+ 颜色映射（<2红/<4黄/≥4绿），且 5 维度判定规则与字段非空严格一致
- **Pass Threshold**：>= 4
- **Evidence**：browser_snapshot 捕获 3 个资产卡徽章（人物/场景/道具）+ DOM evaluate 读取徽章文本与 backgroundColor 匹配规则

### AC-7：老项目无一致性配置字段时，UI 与出图零崩溃
- **Type**：`rule`
- **Given**：用 sqlite3 CLI 手动 INSERT 一条 assets 行 consistency_config_json 为 NULL（或删列模拟老库）后重启后端
- **When**：GET list_assets + 前端渲染 Step2 + rebuild 该资产
- **Then**：① list_assets 返回 consistency_config 为默认空结构零报错；② 前端显示占位文案"尚未配置→点🔒开始锁定"；③ rebuild Prompt 使用 _trim_style_for_asset_type 默认值不崩溃
- **Pass Condition**：后端 HTTP500 0 次；前端无 console error；出图 COMPLETED 率 100%
- **Evidence**：uvicorn error log grep 0 条 500 + browser_evaluate console.errors.length=0

## Open Questions
- [x] 五维结构 5 个维度字段名是否采用 FR-1~FR-5 对应的嵌套：{character:{...}, style:{...}, scene:{...}, camera:{...}, lighting:{...}} → **已决定**：采用扁平 key（字符级 face_tags / lock_outfit / style_lora_name / lighting_preset / voice_preset）避免深层缺 key 崩溃，同时保持 5 个分组在 UI 层。
- [ ] 用户是否需要「一键应用模板」按钮（例如："古风仙侠标准角色一致性模板"把 5 个维度默认值一次填好）？→ **暂不实现**，如用户反馈需要在 v2 加。
- [ ] TTS/配音音色一致性字段是否需要在本期真正对接 Step4 edge-tts voice？→ **本期仅存字段供 Step4 读取**，不修改 Step4 service。
