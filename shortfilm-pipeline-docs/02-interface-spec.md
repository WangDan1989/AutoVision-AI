# 接口规约文档

## 1. 目的

本文定义在“AI 参与 3D 资产生成”的新架构下，系统内部模块和第三方本地组件之间使用的统一请求响应结构、错误码、超时、重试和熔断规则。目标如下：

- 统一 AI 3D 建模后端、LLM 后端、TTS、Lip Sync 与运行时模块的交互方式。
- 将资产生成期与拍摄运行期的错误收敛为统一标准。
- 保证资产草稿失败不污染拍摄链路，运行期错误不破坏整体剧情推进。

本文为 HLD 级接口规约，不强制限定传输层必须为 HTTP；模块内可使用本地服务、CLI、IPC 或进程内调用，但抽象请求和响应结构保持一致。

## 2. 统一包结构

### 2.1 通用请求包

```json
{
  "request_id": "req_01K0ASSET001",
  "trace_id": "trace_asset_char_lin_v2",
  "module": "asset_generation_orchestrator",
  "action": "submit_generation_job",
  "timestamp_ms": 1792729200000,
  "deadline_ms": 1792729500000,
  "payload": {},
  "meta": {
    "project_id": "proj_demo",
    "asset_id": "char_lin",
    "asset_type": "character",
    "operator": "user"
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 单次请求唯一标识 |
| `trace_id` | string | 是 | 跨模块链路追踪 ID |
| `module` | string | 是 | 发起请求模块 |
| `action` | string | 是 | 目标动作 |
| `timestamp_ms` | integer | 是 | 请求创建时间 |
| `deadline_ms` | integer | 否 | 请求截止时间 |
| `payload` | object | 是 | 业务数据 |
| `meta` | object | 否 | 工程、资产、场景、操作者等上下文 |

约束：

- `payload` 只放业务参数，不承载重试、并发等控制参数。
- 所有时间戳采用 Unix Epoch 毫秒。
- `meta` 允许扩展，但下游模块不得依赖未在文档中声明的字段。

### 2.2 通用响应包

```json
{
  "request_id": "req_01K0ASSET001",
  "trace_id": "trace_asset_char_lin_v2",
  "success": true,
  "code": "OK",
  "message": "job accepted",
  "data": {},
  "error": null,
  "degraded": false,
  "duration_ms": 62
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 回传原请求 ID |
| `trace_id` | string | 是 | 回传原链路 ID |
| `success` | boolean | 是 | 是否成功完成 |
| `code` | string | 是 | 标准结果码 |
| `message` | string | 是 | 简要说明 |
| `data` | object/null | 是 | 成功结果或降级结果 |
| `error` | object/null | 是 | 失败详情 |
| `degraded` | boolean | 是 | 是否发生降级 |
| `duration_ms` | integer | 是 | 处理耗时 |

### 2.3 标准错误对象

```json
{
  "category": "generation_backend_timeout",
  "retryable": true,
  "source": "asset_generation_gateway",
  "details": {
    "backend": "generator_a",
    "job_id": "job_char_lin_002",
    "attempt": 1
  }
}
```

约束：

- `category` 用于熔断、重试与告警归类。
- `retryable` 由源模块明确给出。
- `details` 可包含排障信息，但不得泄露敏感路径、密钥或个人信息。

## 3. 模块动作规约

## 3.1 AI 资产生成编排

### `submit_generation_job`

请求 `payload`：

```json
{
  "asset_type": "character",
  "source_mode": "text_to_3d",
  "backend": "generator_a",
  "design_input": {
    "prompt": "二十多岁的冷静女情报员，现代写实风格，短发，风衣，便于绑定标准人形骨架",
    "negative_prompt": "低模卡通、夸张比例、四肢缺失、面部塌陷",
    "reference_images": []
  },
  "constraints": {
    "target_format": "glb",
    "needs_rig": true,
    "target_rig_profile_id": "humanoid_v1"
  }
}
```

成功响应 `data`：

```json
{
  "job_id": "job_char_lin_002",
  "status": "queued",
  "backend": "generator_a"
}
```

### `query_generation_job`

请求 `payload`：

```json
{
  "job_id": "job_char_lin_002"
}
```

响应 `data`：

```json
{
  "job_id": "job_char_lin_002",
  "status": "processing",
  "progress": 0.64,
  "draft_asset_id": "draft_char_lin_002"
}
```

### `retry_generation_job`

请求 `payload`：

```json
{
  "job_id": "job_char_lin_002",
  "reason": "backend_timeout"
}
```

## 3.2 资产后处理

### `postprocess_generated_asset`

请求 `payload`：

```json
{
  "draft_asset_id": "draft_char_lin_002",
  "steps": [
    "normalize_scale",
    "normalize_material",
    "rig_or_retarget",
    "export_glb"
  ],
  "target_rig_profile_id": "humanoid_v1"
}
```

成功响应 `data`：

```json
{
  "revision_id": "char_lin_rev_002",
  "status": "review_pending",
  "runtime_asset_path": "assets/drafts/characters/char_lin/rev_002/char_lin.glb"
}
```

## 3.3 资产质检与发布

### `run_quality_checks`

请求 `payload`：

```json
{
  "revision_id": "char_lin_rev_002",
  "checks": [
    "mesh_integrity",
    "material_integrity",
    "scale_integrity",
    "rig_integrity",
    "godot_import"
  ]
}
```

成功响应 `data`：

```json
{
  "report_id": "quality_char_lin_rev_002",
  "status": "passed",
  "summary": {
    "mesh_integrity": "pass",
    "material_integrity": "pass",
    "scale_integrity": "pass",
    "rig_integrity": "pass",
    "godot_import": "pass"
  }
}
```

### `publish_asset_revision`

请求 `payload`：

```json
{
  "asset_id": "char_lin",
  "revision_id": "char_lin_rev_002",
  "lock_for_runtime": true
}
```

成功响应 `data`：

```json
{
  "asset_id": "char_lin",
  "active_revision_id": "char_lin_rev_002",
  "published": true
}
```

## 3.4 LLM 网关

### `generate_dialogue`

请求 `payload`：

```json
{
  "backend": "ollama",
  "character_id": "char_lin",
  "persona_id": "persona_lin",
  "prompt_context": {
    "scene_goal": "在茶馆中交换情报",
    "story_constraints": [
      "不得脱离主线",
      "不得改变人物立场"
    ],
    "history": [
      {
        "speaker": "char_zhou",
        "text": "你确定没有人跟踪你？"
      }
    ]
  },
  "generation": {
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 120
  },
  "fallback_line": "按计划行动，别暴露身份。"
}
```

成功响应 `data`：

```json
{
  "backend": "ollama",
  "text": "放心，我绕了三条街才过来，没人发现。",
  "finish_reason": "stop",
  "token_usage": {
    "prompt_tokens": 502,
    "completion_tokens": 21
  }
}
```

降级响应 `data`：

```json
{
  "backend": "fallback",
  "text": "按计划行动，别暴露身份。",
  "finish_reason": "fallback_preset"
}
```

## 3.5 TTS 与 Lip Sync

### `synthesize_or_load_cache`

请求 `payload`：

```json
{
  "text": "放心，我绕了三条街才过来，没人发现。",
  "voice_id": "zh_cn_female_01",
  "sample_rate": 22050,
  "cache_key": "sha256:3d8f8d...",
  "allow_cache": true
}
```

成功响应 `data`：

```json
{
  "cache_hit": true,
  "audio_path": "audio/dialogue-cache/3d8f8d.wav",
  "duration_ms": 3210
}
```

### `generate_lipsync`

请求 `payload`：

```json
{
  "audio_path": "audio/dialogue-cache/3d8f8d.wav",
  "character_id": "char_lin",
  "cache_key": "sha256:3d8f8d"
}
```

成功响应 `data`：

```json
{
  "cache_hit": false,
  "track_path": "cache/lipsync/3d8f8d.json",
  "frame_count": 86
}
```

## 3.6 事件引擎与渲染导出

### `advance_event`

请求 `payload`：

```json
{
  "scene_id": "scene_01",
  "event_id": "evt_010",
  "runtime_state": {
    "characters": {
      "char_lin": "idle",
      "char_zhou": "talking"
    },
    "variables": {
      "distance_lin_zhou": 1.8
    }
  }
}
```

响应 `data`：

```json
{
  "next_events": [
    "evt_011"
  ],
  "actions": [
    {
      "type": "generate_dialogue",
      "target": "char_lin"
    },
    {
      "type": "switch_camera",
      "target": "cam_close_lin"
    }
  ]
}
```

### `export_video`

请求 `payload`：

```json
{
  "mode": "script_auto",
  "resolution": {
    "width": 1920,
    "height": 1080
  },
  "fps": 30,
  "codec": "h264",
  "output_path": "exports/ep_001/final.mp4"
}
```

成功响应 `data`：

```json
{
  "output_path": "exports/ep_001/final.mp4",
  "frame_count": 5430,
  "duration_ms": 181000
}
```

## 4. 标准错误码

### 4.1 命名规则

- `OK`：成功
- `E1xxx`：校验类
- `E2xxx`：资源与资产类
- `E3xxx`：后端与调用链类
- `E4xxx`：运行时与质量门禁类
- `E5xxx`：存储、导出与日志类

### 4.2 错误码表

| 错误码 | 分类 | 说明 | 可重试 |
| --- | --- | --- | --- |
| `OK` | success | 请求成功 | 否 |
| `E1001` | validation | 缺少必填字段 | 否 |
| `E1002` | validation | 字段格式非法 | 否 |
| `E1003` | validation | 脚本引用不存在 | 否 |
| `E1004` | validation | 资产提示词非法或为空 | 否 |
| `E2001` | resource | 资产文件不存在 | 否 |
| `E2002` | resource | 音频文件不存在 | 否 |
| `E2003` | resource | 动作片段不存在 | 否 |
| `E2004` | resource | 草稿资产不存在 | 否 |
| `E2005` | resource | 资产版本未批准 | 否 |
| `E3001` | backend_unreachable | 后端不可达 | 是 |
| `E3002` | backend_timeout | 后端超时 | 是 |
| `E3003` | backend_overloaded | 后端繁忙或限流 | 是 |
| `E3004` | backend_invalid_response | 后端响应无法解析 | 否 |
| `E3005` | circuit_open | 熔断器已打开 | 否 |
| `E3006` | generation_job_failed | 资产生成作业失败 | 视原因而定 |
| `E3007` | postprocess_failed | 资产后处理失败 | 是 |
| `E4001` | runtime | 触发器条件求值失败 | 否 |
| `E4002` | runtime | 状态机切换非法 | 否 |
| `E4003` | runtime | 动作优先级冲突未解决 | 否 |
| `E4004` | runtime | 预设台词缺失，无法降级 | 否 |
| `E4005` | quality_gate | 资产质量门禁未通过 | 否 |
| `E4006` | runtime_asset_lock | 运行期引用了未锁定资产版本 | 否 |
| `E5001` | storage | 工程保存失败 | 是 |
| `E5002` | storage | 缓存写入失败 | 是 |
| `E5003` | export | 导出编码失败 | 是 |
| `E5004` | log | 日志落盘失败 | 是 |

## 5. 超时规则

### 5.1 默认超时

| 模块动作 | 默认超时 | 说明 |
| --- | --- | --- |
| `submit_generation_job` | 10 秒 | 只负责接收与排队 |
| `query_generation_job` | 2 秒 | 快速状态查询 |
| `postprocess_generated_asset` | 10 分钟 | 模型清洗、材质整理、导出 |
| `run_quality_checks` | 2 分钟 | 质量门禁检查 |
| `generate_dialogue` | 90 秒 | 本地大模型推理 |
| `synthesize_or_load_cache` | 30 秒 | TTS 或缓存读取 |
| `generate_lipsync` | 20 秒 | 音频转嘴型 |
| `advance_event` | 200 毫秒 | 事件推进必须轻量 |
| `export_video` | 无固定上限 | 任务级监控和取消 |

规则：

- 长耗时资产生成作业采用异步任务模型，`submit_generation_job` 不等待最终模型产出。
- 若请求自带 `deadline_ms`，以更严格者为准。
- 运行时事件引擎不等待资产生成任务完成。

## 6. 重试规则

### 6.1 允许重试

- `E3001`、`E3002`、`E3003`
- `E3007` 中的瞬时工具调用失败
- `E5001`、`E5002`、`E5003`、`E5004` 中的瞬时 I/O 异常

### 6.2 禁止重试

- 校验错误
- 质量门禁未通过
- 未批准资产被运行期引用
- 后端响应结构非法
- 熔断器已打开

### 6.3 默认重试策略

| 模块 | 最大重试次数 | 间隔策略 |
| --- | --- | --- |
| 资产生成提交 | 1 次 | 固定等待 1 秒 |
| 资产后处理 | 1 次 | 固定等待 2 秒 |
| LLM 调用 | 2 次 | 指数退避：1 秒、2 秒 |
| TTS 调用 | 1 次 | 固定等待 500 毫秒 |
| Lip Sync 调用 | 1 次 | 固定等待 500 毫秒 |
| 导出写盘 | 2 次 | 指数退避：1 秒、2 秒 |

规则：

- 所有重试必须复用原 `trace_id`。
- 非幂等的资产生成作业只能在“未成功入队”时自动重试。
- 一旦运行期已完成降级，不再继续重试以阻塞时间线。

## 7. 熔断规则

### 7.1 适用范围

- 对 LLM 后端调用启用熔断器。
- 对 AI 建模后端的“提交入口”启用健康门禁和短期开关。
- TTS 与 Lip Sync 仍采用“失败即降级”，不单独启用熔断器。

### 7.2 状态

- `closed`：正常放行
- `open`：短时间内拒绝请求
- `half_open`：放行少量探测请求

### 7.3 打开条件

LLM 熔断：

1. 最近 10 次请求中失败率大于等于 50%，且样本数不少于 4。
2. 连续 3 次出现 `E3001` 或 `E3002`。

AI 建模提交门禁：

1. 连续 3 次作业提交失败。
2. 最近 5 分钟内后端健康检查持续失败。

### 7.4 打开后的行为

- LLM 熔断打开后，对话生成直接降级到预设台词。
- AI 建模提交门禁打开后，不再接受新的生成作业，但不影响已批准资产拍摄。

## 8. 双网关适配规约

### 8.1 LLM 适配

统一入参：

- `backend`
- `model`
- `prompt_context`
- `generation.temperature`
- `generation.top_p`
- `generation.max_tokens`

统一出参：

- `text`
- `finish_reason`
- `token_usage.prompt_tokens`
- `token_usage.completion_tokens`

### 8.2 AI 建模适配

统一入参：

- `asset_type`
- `source_mode`
- `design_input.prompt`
- `design_input.reference_images`
- `constraints.target_format`
- `constraints.needs_rig`
- `constraints.target_rig_profile_id`

统一出参：

- `job_id`
- `status`
- `draft_asset_id`
- `preview_paths`
- `output_files`

原则：

- 网关层不得依赖底层后端专有字段。
- 所有适配器都必须输出统一的草稿资产结构。

## 9. 日志与可观测性

每个模块至少记录：

- `timestamp`
- `level`
- `trace_id`
- `request_id`
- `module`
- `action`
- `code`
- `message`
- `duration_ms`
- `degraded`

额外要求：

- 资产生成链路必须能关联到 `asset_id`、`revision_id`、`job_id`。
- 运行期链路必须能关联到 `scene_id`、`event_id`、`character_id`。
- 质检失败必须保留可追踪的质量报告 ID。
