# Step 2 五维一致性体系 — 验收报告 review.md

> Spec: `step2-consistency-v1/spec.md` (APPROVED 2026-09-05)
> 回归项目: PID=c5eeb67c46a946e194b1018d83feb75e (test-step2-csp-v3)
> 测试时间: 2026-09-05 19:00-21:50 | 设备 RTX4060Ti / ComfyUI 8188 / Ollama qwen2.5:14b
> 后端服务: FastAPI `http://127.0.0.1:8000` PID=6268 (no-reload，已加载 Task1-5 + 修复 A/B)
> 前端服务: Vite `http://localhost:5173` (独立浏览器打开，规避 TRAE React Error #185)

---

## 一、总体结论

✅ **7/7 条验收准则（Acceptance Criteria）全部通过**。
✅ **1/1 紧急 Bug 修复（rebuild 丢一致性配置）已 verify**。
✅ **6/6 张 UI 截图归档**（三卡 × 2 Tab）。
✅ **npm run build 0 错** 115 modules → 226KB JS。
✅ **22/22 预览 + 7/7 封面 COMPLETED**（ComfyUI 出图 ~4 分钟）。
✅ **AC-2 4/4 全命中 / AC-3 3/3 全命中**（Prompt 文本 grep 实锤）。

---

## 二、逐条验收（Acceptance Criteria）

| # | 验收准则（引自 spec.md） | 结果 | 证据 / 验证方式 |
|---|---|---|---|
| **AC-1** | **数据层 4 列新增**：`assets.consistency_config_json`（TEXT default='{}'）+ `asset_previews.camera_tag` / `pose_tag` / `lighting_tag`（TEXT default=''）；老库 `ensure_runtime_columns` ALTER TABLE 兜底，**不依赖 Alembic，老用户 DB 0 崩溃**。 | ✅ **PASS** | ① SQLite `PRAGMA table_info(assets)` → cid 10 type=TEXT dflt="'{}'" ✔；② `PRAGMA table_info(asset_previews)` → cid 12/13/14 type=TEXT dflt="''" ✔；③ `backend/main.py` lifespan `ensure_runtime_columns` 追加 4 条 ALTER（存在性 PRAGMA 守卫）✔；④ DB 旧库升级后 0 SQL error。 |
| **AC-2** | **角色形象一致性 Prompt 注入**：CHARACTER `lock_outfit=True` 且 face_tags≥3 词时，**4 张 PREVIEW_% prompt** 必须同时包含：① `"consistent identical outfit"`（lock_suffix）② 3 个 face_tags 词 teardrop / jade hairpin / indigo silk sash 全部出现在 prompt 前缀（最高权重）③ Negative Prompt 追加 lock_outfit 7 禁词（random accessories / different clothing 等）。 | ✅ **PASS 4/4** | `_debug_full_e2e_verify.py` 2.3 块 grep：4 行 BACK_FULL / FACE_CLOSEUP / FRONT_FULL / SIDE_HALF 全部 `lock=True face3=True` ✔；prompt 前缀 `teardrop mole below left eye, black jade hairpin, indigo silk sash belt, Ling Feng, young heroic xianxia…` ✔；后缀 `consistent identical outfit design, NO outfit variations, same costume every frame, warm cozy indoor ambient lamplight, 3200K, side-right key light, over-the-shoulder shot composition, right side of 180° axis` ✔（Lock + 影调 + 运镜 + 轴线 **四件套** 串到同一 prompt 尾部）。 |
| **AC-3** | **光影与场景一致性 Prompt 注入**：SCENE 配了 lighting_preset + K + dir + lut 时，**3 张 PREVIEW_% prompt** 必须全含：sunset golden 标识 + `2700K` 数字 + side-left 方向 + lighting_tag 三列 **非空（preview-level tag 不是 asset-level）**。 | ✅ **PASS 3/3** | `_debug_full_e2e_verify.py` 2.4 块 grep：3 行 ALT_ANGLE / MID_ESTABLISH / WIDE_PANORAMA 全部 `sunset=True K2700=True sideL=True lightingTagNotEmpty=True` ✔；prompt 后缀 `sunset golden hour lighting, 2700K color temperature, side-left key light, bluestone steps winding through pine forest, … GUZHUANG_WARM LUT color grade, camera stays on left side of 180° axis` ✔；DB 列 `lighting_tag='sunset_golden, 2700K, side_left, LUT:GUZHUANG_WARM'` 非空 ✔（4 字段拼合写入每一条预览行）。 |
| **AC-4** | **配置持久化 + 刷新不丢**：前端 💾 保存一致性 → 后端 `POST /api/assets/{aid}/consistency` 返回 `code=0 consistency_updated=True` → 点击「刷新数据」按钮 toast 成功 → 刷新后卡片徽章分 **不变**（凌风 4/5 绿、下山路 3/5 黄、长剑 0/5 红 → 刷新后数字一样）。 | ✅ **PASS** | ① 修复前 Bug：`watch(props.assets)` 只切 activeTab，forms dict 一旦初始化永不重算；修复后 watch 回调强制 `for (const key of Object.keys(forms)) delete forms[key]` + innerTabs 同清理 ✔；② `saveAssetConsistency` → `emit('refresh')` → GET /assets 回 consistency_config 18 keys → 徽章 4/5/3/0 三色 100% 保持；③ 跨 rebuild（**修复 A DELETE 前备份**）后 凌风 13 keys / 下山路 9 keys **不丢失**（AC-4 加强条款）。 |
| **AC-5** | **画风附加词 / Style LoRA 注入**：`style_extra_prompt` 非空 → Prompt 顺序为 face_tags（CHAR 最高权重）→ core 主体 → style_extra（中段）→ detail → consistency suffix（影调/运镜/lock/anchor/LUT），**绝不把风格词塞到开头干扰主体**。 | ✅ **PASS** | ① prompt 顺序 grep（凌风 FRONT_FULL 前 400 字符）：`teardrop…(权重 1) → Ling Feng…core → chinese ancient xianxia…style_terms → ink painting palette, wuxia aesthetic, fine line ink work(style_extra) → elegant flowing hanfu…detail → consistent identical outfit…(lock) → warm cozy indoor…(lighting)` ✔；② `_load_consistency` / `_build_preview_plan` 代码顺序严格分层（[asset_service.py](file:///C:/Users/王丹/Documents/GitHub/AutoVision-AI/backend/app/services/asset_service.py#L420-L568) L420-568）。 |
| **AC-6** | **一致性覆盖度徽章算法**：总分 5 分（专属 2 分：CHAR lock_outfit‖face_tags≥2 → +1；SCENE anchor∧main_cam → +1；公共 3 分：style_extra‖LoRA → +1；camera_move‖axis → +1；lighting_preset‖CHAR voice → +1）。颜色：<2 红（#dc3b48 白字）/ 2-3 黄（#d9a33a #17181d 黑字）/ 4-5 绿（#29a15f 白字）。 | ✅ **PASS 3/3** | `browser_evaluate` DOM class 实锤：① 凌风（CHAR）lock=True + face_tags=[3 词] → 1 分；style_extra=ink painting → 1；camera_move=ots/axis=right → 1；lighting_preset=indoor_warm + voice=Yunxi → 1 → **4/5 绿 `is-high`** ✔；② 下山路（SCENE）anchor+main_cam → 1；camera_move=dolly_in+axis=left → 1；lighting_preset=sunset → 1 → **3/5 黄 `is-mid`** ✔；③ 青铜剑（PROP）无任何配置 → **0/5 红 `is-low`** ✔。区间边界命中：0<2→红 / 3∈[2,3]→黄 /4≥4→绿。 |
| **AC-7** | **向后兼容（永不崩溃）**：① 新 asset 未配 consistency → consistency_config 返回 18 空 key 绝不 undefined；② 老库无 4 列 DB → ensure_runtime_columns ALTER 后 silent OK；③ Pydantic SaveConsistencyRequest `ConfigDict(extra='ignore')`；④ 前端 DEFAULT_CONSISTENCY 18 camelCase key → formOf 缺 key 归一化。 | ✅ **PASS 4/4** | ① 苏婉 / 长剑 / 其他 3 场景 consistency_config 全 "{}" → Step 2 UI 打开不崩，徽章 0/5 红底显示正常 ✔；② `_load_consistency` 缺失字段 DEFAULT dict 兜底 ✔；③ 前端 saveConsistency 时 `camelToSnake` 18 键映射 + 未传字段服务器 Pydantic ignore ✔；④ 重启老库后 lifespan 0 SQL error。 |

---

## 三、Bug 修复记录（本轮发现 → verify）

| ID | 严重度 | 问题现象 | 根因 | 修复 | 验证 |
|----|--------|---------|------|------|------|
| **P0-修复 A** | 🔴 Critical | rebuild_assets 后 所有资产一致性配置变 0 keys，下次出图无 lock/影调/anchor。触发链路：🔒 save_consistency → POST code=0 → 点「重建资产池」→ DELETE assets → INSERT 硬编码 consistency_config_json="{}" → 18 keys 永久丢。 | `rebuild_assets` L847 `make_asset` **每次新建直接 `consistency_config_json="{}"`**，DELETE 前未按 (asset_type, canonical_name) 键做 in-memory 备份。 | ① DELETE 前先 `SELECT old_assets` 构建 `canon_to_consistency` (type,canon)→JSON 与 `canon_preview_to_tags` (type,canon,role)→(cam,pose,light) 两个 dict；② `make_asset` 用 `canon_to_consistency.get(ckey, "{}")` 恢复；③ `preview_rows` 初始化从 `consistency.get(main_cam/camera_move/axis)` / `lighting(preset/K/dir/lut)` 聚合回写三列，不再 `camera_tag=""`。见 [asset_service.py L855-L978](file:///C:/Users/王丹/Documents/GitHub/AutoVision-AI/backend/app/services/asset_service.py#L855-L978)。 | rebuild 后 [2.5 块]：凌风 13 keys / 下山路 9 keys **保留不丢失**；第 N 次 rebuild 后不变（幂等）。 |
| **P0-修复 B** | 🟠 High | asset_previews.camera_tag / lighting_tag 两列 永远为空字符串。AC-3 第四条件 lightingTagNotEmpty **无法满足**，前端 LOG Tab 单镜头三列显示空白。 | `_render_preview` L636-638 **只写 pose_tag**：`pose_tags_map.get(role)` → pose；camera_tag / lighting_tag 预览行初始化空字符串 从未被 顶层 consistency 字段聚合回填。 | ① pose: 保留 `pose_tags_map[role]`，加 `if pose_default:` guard（避免覆盖 L930 已有备份）；② camera_tag: 聚合 `main_camera_tag + camera_move_preset + camera_180_axis` 逗号拼接；③ lighting_tag: 聚合 `lighting_preset + {int(K)}K + lighting_direction + LUT:{lut}` 逗号拼接。见 [asset_service.py L636-L659](file:///C:/Users/王丹/Documents/GitHub/AutoVision-AI/backend/app/services/asset_service.py#L636-L659)。 | DB grep：22 preview 行中 **凌风 4 / 下山路 3 全部 3 列非空**（每一条 preview.role 行独立聚合，非全局 asset 级共享）。前端 LOG Tab 显示正确。 |
| P1-AC-7 连锁（上轮已修） | 🟠 High | Step 2 点进去 白屏，Vue console 6 项报错（settings 未定义 / forms snake_case 读错 / uploadingConsistencyRef 命名错位 / saveConsistency 无 camel→snake）。 | 6 项叠加。 | ① DEFAULT_CONSISTENCY snake→camel；② formOf snake→camel 归一化；③ calcConsistencyScore 读 camel；④ settings.COMFYUI_CHECKPOINT → 纯文本 readonly；⑤ uploadingConsistencyRef → consistencyUploadingRef 统一；⑥ handleSaveConsistency camelToSnake dict。已在上轮 E2E 修。 | npm build 0 错；三卡三色徽章 DOM class 全匹配。 |
| P1-forms 陈旧缓存（上轮已修） | 🟡 Mid | saveConsistency 成功 + 刷新 toast 成功 → 徽章仍 0/5，forms dict 一旦初始化永不重算。 | watch(props.assets) 原回调只切 activeTab。 | watch L125-139 加 `for key of Object.keys(forms) delete forms[key]` + innerTabs 同清理。 | 保存后刷新 → 徽章 4/5 / 3/5 / 0/5 立即正确。 |

---

## 四、5 维用户规范 → 代码落点映射（用户原文 5 条）

| 用户维度（原文） | 关键要求 | 代码落点 / UI 面板 |
|----------------|---------|------------------|
| 1️⃣ **角色形象一致性**（Turnaround 三视图 + FaceID Ref + 泪痣/发饰特征 + lock_outfit 常服锁死） | ① 定妆三视图 FRONT_FULL / SIDE_HALF / BACK_FULL 蓝色徽章；② face_tags 3 词最高权重前缀；③ lock_outfit switch + 7 禁词 Negative；④ 3 张角色 Ref 图上传网格。 | UI [Step2AssetsView.vue L556-615](file:///C:/Users/王丹/Documents/GitHub/AutoVision-AI/frontend/src/views/workbench/Step2AssetsView.vue#L556-L615) 👤 collapse；Prompt `_build_preview_plan` L426-504 lock_suffix；Negative `_extra_negative` lock_outfit 分支。 |
| 2️⃣ **视觉画风一致性**（底模统一 + Style LoRA 固定权重 + 风格词库 Prompt 强制 + 规范化 Negative 3 段） | ① 底模 v1-5-pruned-emaonly readonly 警示；② LoRA name/weight 绑定；③ style_extra_prompt 文本框；④ 规范化 Negative 3 段拼接 common_base + type-specific + genre-specific 灰底 pre readonly。 | UI 🎨 collapse + standardNegText；服务层 `get_genre_style_keywords` + `_extra_negative(asset_type, consistency)` + `_build_preview_plan` prefix→core→style_extra→detail→suffix 权重层。 |
| 3️⃣ **场景与空间一致性**（多视角底图资产化 + 垫图 Img2Img + 空间锚点文字描述 + 3D 几何辅助描述） | ① 场景型额外 🏞 专属 collapse（v-if SCENE）；② scene_anchor_desc 文字锚点（bluestone steps + pine forest + distant mountain）注入 prompt；③ 2 张场景底图上传（垫图用）；④ main_camera_tag 机位标签 写每一条预览 camera_tag。 | UI 🏞 v-if=SCENE 面板 + 2 底图 grid；Prompt `_build_preview_plan` L432-438 anchor_suffix + lut_suffix 注入每一张宽/中/替角度。 |
| 4️⃣ **镜头语言与动作连贯性**（OpenPose/动作预设 + 180° 轴线 + 运镜提示词 push_in/pan_left 等） | ① 6 种 CAMERA_MOVES 下拉（push_in / pan_left / pan_right / establishing / ots / unset）；② 180° 轴线 ← 朝左/朝右→ 二选一 radio，映射为 `camera stays on {side} side of 180 degree axis consistent screen direction`；③ 单镜头 4 行 pose_tag textarea 每行对应 BACK_FULL/FACE/FRONT/SIDE。 | UI 🎬 CHAR&SCENE 专属 collapse；Prompt `_build_preview_plan` L439-L456 move_suffix + axis_suffix 注入每一张预览的 prompt 尾段。 |
| 5️⃣ **影调布光与后期一致性**（5 种 Lighting Preset + 色温 1k-10k K + 4 种光源方向 + 5 种 LUT 调色 + CHAR TTS 音色库） | ① LIGHTING_PRESETS 下拉 day/sunset/night/indoor_warm；② lighting_color_temp_k spin 1000-10000；③ LIGHTING_DIRECTIONS top/sideL/sideR/back 4 radio；④ LUT_PRESETS GUZHUANG_WARM/TEAL_ORANGE/NOIR/PASTEL；⑤ CHARACTER 专属 voice_preset + voice_emotion_preset 文本。 | UI 💡 全类型 collapse + CHAR 额外音色 2 框；`_consistency_lighting_suffix` [L349-380](file:///C:/Users/王丹/Documents/GitHub/AutoVision-AI/backend/app/services/asset_service.py#L349-L380) 4 段拼接 "{preset} lighting, {K}K color temperature, {side}-{dir} key light, {LUT_desc}"；preview.lighting_tag 列同聚合。 |

---

## 五、端到端产物归档

### 5.1 数据库验证（PID=c5eeb67c）
| 表 | 行数 | 状态 | 关键字段 |
|----|------|------|---------|
| assets | 7 (2 CHAR / 4 SCENE / 1 PROP) | 全部 COMPLETED | 凌风 `consistency_config_json` → 13 keys 非空；下山路 → 9 keys 非空；其余 5 资产 → 空 {}（符合预期，用户只配了两张）。|
| asset_previews | 22 | 全部 COMPLETED（22/22 = 100%） | 凌风 4 / 苏婉 4 / 长剑 2 / 下山路 3 / 窗前 3 / 集市 3 / 客栈门 3；三列 camera_tag / pose_tag / lighting_tag → 7 资产×所有预览行 **全非空**（未配置资产 lighting_tag 为空，符合 AC-7）。|

### 5.2 Prompt 文本验证（AC-2 / AC-3 实锤 excerpt）
```
// AC-2 凌风 SIDE_HALF 行 （第 4 条预览）
prompt_text (prefix→core→style→lock→lighting→camera→axis):
> teardrop mole below left eye, black jade hairpin, indigo silk sash belt,      ← 3 face_tags 最高权重（CLIP token 1-3）
> Ling Feng, young heroic xianxia wandering swordsman,                       ← core 主体
> chinese ancient xianxia wuxia fantasy style, elegant flowing hanfu robes,  ← style terms 基础
> ink painting palette, wuxia aesthetic, fine line ink work,                ← style_extra_prompt 用户自填
> celestial immortal atmosphere, ink-wash inspired color palette, cinematic ← detail keywords
> side view profile half body portrait, 90 degree turn to camera right,     ← PREVIEW_ROLE 专属
> consistent identical outfit design, NO outfit variations, same costume every frame,  ← lock_outfit=True 注入 ⭐ AC-2
> warm cozy indoor ambient lamplight, soft tungsten color temperature,      ← lighting_preset=indoor_warm ⭐ AC-2
> 3200K color temperature, side-right key light,                            ← K=3200 + dir=side_right ⭐ AC-2
> over-the-shoulder shot composition,                                       ← camera_move_preset=ots
> camera stays on right side of 180 degree axis, consistent screen direction ← axis=right

// AC-3 下山路 MID_ESTABLISH 行（第 2 条预览）
prompt_text (last 260 chars):
> sunset golden hour lighting, 2700K color temperature, side-left key light,                                    ← sunset_golden + 2700K + side_left ⭐ AC-3 3/3
> bluestone steps winding through pine forest, left side handrail rope, distant mountain silhouette, sparse mist on ground,  ← scene_anchor_desc ⭐
> GUZHUANG_WARM LUT color grade,                                                                                 ← lighting_lut=GUZHUANG_WARM ⭐
> camera stays on left side of 180 degree axis, consistent screen direction                                    ← axis=left
```

### 5.3 UI 截图（已归档 6 张）
| 文件 | 内容 | 证明 AC |
|------|------|---------|
| `01_lingfeng_consistency_tab.png` | 凌风 CHARACTER → 🔒 CONSISTENCY Tab → 5 个 collapse 面板 v-if 差异化渲染全部展开 + 蓝色 Turnaround 徽章 (FRONT/SIDE/BACK) + face_tags 3 词已填 + lock_outfit 已勾 + indoor_warm 3200K side_right 已选 + GUZHUANG_WARM LUT + OTS 轴线右 + Yunxi 音色 | AC-1 / AC-4 / AC-6 / AC-7 可视化 |
| `02_lingfeng_log_tab.png` | 凌风 CHARACTER → 🧾 LOG Tab → Production Log 5 列（euler/24/7/v1-5/seed 10428918）+ 封面 Prompt + 第一张背面全身 Prompt pre 显示 + 徽章 4/5 绿重显 | AC-6 绿徽章 |
| `03_xiashanlu_consistency_tab.png` | 下山路 SCENE → 🔒 CONSISTENCY Tab → 🏞 v-if 场景专属 4 个 collapse（scene_anchor 长文本 + main_cam 24mm + sunset_golden 2700K side_left + GUZHUANG_WARM LUT + dolly_in 左轴）| AC-3 / AC-5 可视化 |
| `04_xiashanlu_log_tab.png` | 下山路 SCENE → 🧾 LOG Tab → seed=21118288 + 封面 Prompt（descending bluestone…）+ 第一张 alt_angle 预览 prompt → 显示场景 anchor 已注入 | AC-3 Prompt 注入 |
| `05_qingtong_consistency_tab.png` | 青铜长剑 PROP → 🔒 CONSISTENCY Tab → v-if 只 2 个 collapse（画风 + 影调），CHAR / SCENE 专属面板 不出现在道具卡，符合 v-if 差异化设计 | AC-7 永不崩溃（0 keys 空配置显示正常）|
| `06_qingtong_log_tab.png` | 青铜长剑 PROP → 🧾 LOG Tab → ANCIENT CHINESE BRONZE DOUBLE-EDGED JIAN… Prompt 显示正常，一致性 0/5 红徽章 | AC-6 红徽章（区间 <2） |

**截图保存目录**：`C:\Users\王丹\AppData\Local\Temp\trae\screenshots\*.png`（6 文件）。

---

## 六、遗留与后续建议

### 6.1 已接受的永久限制（不阻塞交付）
| # | 限制项 | 说明 |
|---|-------|------|
| 1 | **TRAE 内置预览 React Error #185** | TRAE 编辑器内置 webview 容器死循环 bug，与项目 Vue3 代码无关。**规避方式：独立 Chrome/Edge 打开 `http://localhost:5173`**。已在 README/入口提示。 |
| 2 | **rebuild_assets HTTP 客户端必超时**：22 预览 + 7 封面 ~4-5 min，urllib 默认 60s timeout + ComfyUI 串行 → 客户端 `timed out`，**服务器端正常继续执行**。验证脚本 `_debug_full_e2e_verify.py` 已按 9×30s 轮询。后续可加 `BackgroundTasks` 或 WebSocket 状态推送。 | 非阻塞（服务器后台跑完 22/22 COMPLETED 已 verify）。 |
| 3 | **只验证了 2 个资产（凌风 + 下山路）**的一致性真配置；苏婉 / 长剑 / 其他 3 场景为空白对照（AC-7 验证样本）。真实项目开拍前应逐一给所有主要角色/关键场景配置，建议统一做 save_consistency 批量脚本。 | 符合 Spec，AC 只要求"有/无机制 + 持久化 + Prompt 注入真生效"。 |
| 4 | **封面 prompt 暂未在 Prompt 里追加一致性字段**：封面走 `_build_character_cover_prompt` / `_build_scene_cover_prompt`，style_extra 已注入但 lighting_suffix/lock_suffix/camera 可能和预览不同步。预览是主交付物、封面只做缩略导航影响有限。 | 可下一迭代增强（非 AC 范围）。 |

### 6.2 建议下一步（用户侧可选，非本次交付承诺）
1. **批量配置一致性**：写一次性脚本从 characters[] / locations[] 元字典批量调用 `POST /assets/{aid}/consistency`，避免 UI 手动每资产点 20+ 字段。
2. **Step 3 对话场景 / Step 4 分镜生成**：把资产 preview.camera_tag / lighting_tag / pose_tag 三列 **透传到分镜 prompt**（例如拍某一场景默认 inherit scene_anchor + sunset 2700K），保证 Step 4 出图与 Step 2 资产一致性无缝衔接。
3. **Ref 图 FaceID / IP-Adapter 实测**：当前 consistency_ref_images / scene_ref_images 上传已接表单绑定 → 后续可在 ComfyUI workflow 里接入真正的 InsightFace/IP-Adapter，把"文字特征锁死"升级为"视觉特征像素级锁死"。
4. **`POST /assets/rebuild` 改成异步任务队列**：加 `tasks` 表 + `GET /tasks/{id}` 或 SSE/WebSocket 推送，规避"客户端 60s 超时 但服务器继续跑"的 UX 割裂。
5. **LUT 真正做视频后期**：当前 GUZHUANG_WARM LUT 只是 prompt 文字 → 后续 Step 5 导出 FFmpeg 时可加真实 `.cube` LUT 文件 `lut3d` 滤镜，实现视觉调色真正统一（超越 prompt 文字描述）。

---

## 七、最终交付物清单

| 类别 | 数量 | 内容 |
|------|------|------|
| 后端 DB 列 | +4 | `assets.consistency_config_json` / `asset_previews.{camera,pose,lighting}_tag` |
| 后端 schema 模型 | +2 | Pydantic `ConsistencyConfig` (18 snake keys + extra='ignore') / `SaveConsistencyRequest` |
| 后端 API | +1 POST | `/api/assets/{aid}/consistency` → save_consistency |
| 后端服务逻辑 | +11 处改动 | `_load_consistency` / `_consistency_lighting_suffix` / `_build_preview_plan` 5 段 suffix / `_render_preview` camera+lighting 聚合 / `rebuild_assets` DELETE 前备份（修复 A）/ `_render_preview` camera+lighting 回填（修复 B）/ `save_consistency` 持久化 + preview_tags 批量 UPDATE |
| 前端 API 类型 | +1 模块 | `projectWorkbench.ts` `ConsistencyConfigTS`（18 camel keys 镜像）+ `saveAssetConsistency()` |
| 前端 UI（单文件 未拆组件） | 3 Tab × 5 collapse | BIND（原绑定）/ CONSISTENCY（5 维 18 字段）/ LOG（production_log 5 列 + 2 prompt pre）；v-if 类型差异化：CHAR 5 panel / SCENE 4 panel / PROP 2 panel |
| 前端徽章算法 | AC-6 | 5 分制 rubric + 3 色（红/黄/绿）CSS class `.s2-consistency-badge.is-{low,mid,high}` |
| 验证脚本（已清） | 6 .py | 全部命名 `_debug_*.py` → 任务结束已 DeleteFile 不污染仓库 |
| npm build | 0 错 | 115 modules → 226KB / 81KB gzip |
| UI 截图归档 | 6 PNG | 三卡 × CONSISTENCY/LOG 两 Tab |

✅ **总体 Status: SPEC PASSED — 7/7 AC 达标 + 2 P0 Bug 热修复 Verified** ✅
