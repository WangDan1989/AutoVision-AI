# 接口规约文档

## 1. 目的

本文定义系统内部模块与本地第三方组件接入时采用的统一请求响应结构、错误码、超时策略、重试策略与熔断规则。目标是保证：

- Strata 与 Ollama 可通过统一接口适配。
- 模块之间错误表达一致，便于调试与降级。
- 单模块异常不扩散为整体剧情中断。

本文为 HLD 级接口规约，不限定传输方式必须是 HTTP；模块内可采用方法调用、进程调用或本地 IPC，但抽象数据结构保持一致。

## 2. 统一请求结构

### 2.1 通用请求包

```json
{
  "request_id": "req_01JZ8G5W7VQ7V3P0B9X4WY1K2A",
  "trace_id": "trace_scene_0003",
  "module": "dialogue_service",
  "action": "generate_dialogue",
  "timestamp_ms": 1792726207000,
  "deadline_ms": 1792726237000,
  "payload": {},
  "meta": {
    "project_id": "proj_demo",
    "scene_id": "scene_01",
    "episode_id": "ep_001",
    "operator": "system"
  }
}
```

字段约束：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 单次请求唯一标识 |
| `trace_id` | string | 是 | 跨模块链路跟踪 ID |
| `module` | string | 是 | 发起请求的模块名 |
| `action` | string | 是 | 目标动作 |
| `timestamp_ms` | integer | 是 | 请求创建时间 |
| `deadline_ms` | integer | 否 | 统一超时截止时间 |
| `payload` | object | 是 | 业务负载 |
| `meta` | object | 否 | 工程、场景、角色等上下文 |

约束：

- `payload` 内只放业务参数，不承载链路控制参数。
- 模块不得依赖未声明的 `meta` 字段。
- 所有时间戳采用 Unix Epoch 毫秒。

### 2.2 通用响应包

```json
{
  "request_id": "req_01JZ8G5W7VQ7V3P0B9X4WY1K2A",
  "trace_id": "trace_scene_0003",
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {},
  "error": null,
  "degraded": false,
  "duration_ms": 1850
}
```

字段约束：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 回传原请求 ID |
| `trace_id` | string | 是 | 回传原链路 ID |
| `success` | boolean | 是 | 是否成功完成 |
| `code` | string | 是 | 标准结果码 |
| `message` | string | 是 | 面向日志与调试面板的简要说明 |
| `data` | object/null | 是 | 成功数据或降级结果 |
| `error` | object/null | 是 | 失败时错误详情 |
| `degraded` | boolean | 是 | 是否发生降级 |
| `duration_ms` | integer | 是 | 本次处理耗时 |

### 2.3 标准错误对象

```json
{
  "category": "backend_timeout",
  "retryable": true,
  "source": "ollama_adapter",
  "details": {
    "http_status": 504,
    "backend": "ollama",
    "attempt": 2
  }
}
```

字段说明：

- `category`：错误分类，供熔断与降级规则匹配。
- `retryable`：是否可重试。
- `source`：错误产生模块。
- `details`：可选附加信息，不得泄露敏感路径或系统密钥。

## 3. 模块动作规约

### 3.1 LLM 网关

#### `generate_dialogue`

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

#### `check_backend_health`

请求 `payload`：

```json
{
  "backend": "strata"
}
```

响应 `data`：

```json
{
  "backend": "strata",
  "status": "healthy",
  "latency_ms": 120,
  "circuit_state": "closed"
}
```

### 3.2 TTS 服务

#### `synthesize_or_load_cache`

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

### 3.3 Lip Sync 服务

#### `generate_lipsync`

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

### 3.4 事件引擎

#### `advance_event`

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

### 3.5 渲染导出

#### `export_video`

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

### 4.1 错误码命名规则

- 成功：`OK`
- 校验类：`E1xxx`
- 资源类：`E2xxx`
- 后端与调用链类：`E3xxx`
- 运行时流程类：`E4xxx`
- 存储与导出类：`E5xxx`

### 4.2 错误码表

| 错误码 | 分类 | 说明 | 可重试 |
| --- | --- | --- | --- |
| `OK` | success | 请求成功 | 否 |
| `E1001` | validation | 缺少必填字段 | 否 |
| `E1002` | validation | 字段格式非法 | 否 |
| `E1003` | validation | 脚本引用不存在 | 否 |
| `E2001` | resource | 资产文件不存在 | 否 |
| `E2002` | resource | 音频文件不存在 | 否 |
| `E2003` | resource | 动作片段不存在 | 否 |
| `E3001` | backend_unreachable | 后端不可达 | 是 |
| `E3002` | backend_timeout | 后端超时 | 是 |
| `E3003` | backend_overloaded | 后端繁忙或限流 | 是 |
| `E3004` | backend_invalid_response | 后端响应无法解析 | 否 |
| `E3005` | circuit_open | 熔断器已打开 | 否 |
| `E4001` | runtime | 触发器条件求值失败 | 否 |
| `E4002` | runtime | 状态机切换非法 | 否 |
| `E4003` | runtime | 动作优先级冲突未解决 | 否 |
| `E4004` | runtime | 预设台词缺失，无法降级 | 否 |
| `E5001` | storage | 工程保存失败 | 是 |
| `E5002` | storage | 缓存写入失败 | 是 |
| `E5003` | export | 导出编码失败 | 是 |
| `E5004` | log | 日志落盘失败 | 是 |

## 5. 超时规则

### 5.1 默认超时

| 模块动作 | 默认超时 | 说明 |
| --- | --- | --- |
| `check_backend_health` | 2 秒 | 快速健康检查 |
| `generate_dialogue` | 90 秒 | 适配本地大模型推理 |
| `synthesize_or_load_cache` | 30 秒 | TTS 或缓存读取 |
| `generate_lipsync` | 20 秒 | 音频转嘴型 |
| `advance_event` | 200 毫秒 | 事件推进必须轻量 |
| `export_video` | 无固定上限 | 由任务级监控控制 |
| `saveProject` | 5 秒 | 单工程写盘 |

规则：

- 若请求自带 `deadline_ms`，以更严格者为准。
- 事件引擎不等待长耗时任务同步完成，应通过任务状态或回调推进后续逻辑。
- 导出任务属于长任务，不使用普通请求超时，而采用任务取消与进度监控。

## 6. 重试规则

### 6.1 允许重试的场景

- `E3001` 后端不可达
- `E3002` 后端超时
- `E3003` 后端繁忙
- `E5001`、`E5002`、`E5003`、`E5004` 中的瞬时 I/O 异常

### 6.2 禁止重试的场景

- 任何校验类错误
- 后端响应结构非法
- 脚本、资源、动作等静态引用缺失
- 熔断器已打开

### 6.3 默认重试策略

| 模块 | 最大重试次数 | 间隔策略 |
| --- | --- | --- |
| LLM 调用 | 2 次 | 指数退避：1 秒、2 秒 |
| TTS 调用 | 1 次 | 固定等待 500 毫秒 |
| Lip Sync 调用 | 1 次 | 固定等待 500 毫秒 |
| 工程保存 | 1 次 | 固定等待 300 毫秒 |
| 导出写盘 | 2 次 | 指数退避：1 秒、2 秒 |

规则：

- 所有重试必须带原始 `trace_id`，`request_id` 可更新但需保留父请求引用。
- 重试只对幂等动作启用。
- 触发降级后立即停止进一步重试，避免时间线阻塞。

## 7. 熔断规则

### 7.1 适用范围

- 仅对 LLM 后端调用启用熔断器。
- TTS 与 Lip Sync 默认采用“失败即降级”策略，不启用独立熔断器。

### 7.2 状态机

- `closed`：正常放行。
- `open`：短时间内直接拒绝请求，返回 `E3005`。
- `half_open`：允许少量探测请求进入。

### 7.3 打开条件

满足以下条件之一即打开：

1. 最近 10 次 LLM 请求中失败率大于等于 50%，且样本数不少于 4。
2. 连续 3 次出现 `E3001` 或 `E3002`。

### 7.4 恢复条件

- 熔断打开 30 秒后进入 `half_open`。
- `half_open` 下连续 2 次探测成功则恢复为 `closed`。
- `half_open` 下任意 1 次失败则重新进入 `open`。

### 7.5 打开后的行为

- 对话生成服务不再等待后端恢复，直接回退预设台词。
- 调试面板显示当前熔断状态与最近失败原因。

## 8. 双后端适配规约

### 8.1 统一入参

无论底层使用 Strata 还是 Ollama，业务层均使用以下统一字段：

- `backend`
- `model`
- `prompt_context`
- `generation.temperature`
- `generation.top_p`
- `generation.max_tokens`

### 8.2 统一出参

- `text`
- `finish_reason`
- `token_usage.prompt_tokens`
- `token_usage.completion_tokens`

### 8.3 后端差异处理原则

- Strata 与 Ollama 的模型名、HTTP 路径、参数命名、流式响应差异全部在适配器内部处理。
- 适配器必须将底层网络错误、状态码错误、解析错误转换为标准错误码。
- 网关层不得依赖任一后端的专有字段。

## 9. 日志与可观测性规约

每个模块至少记录以下字段：

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

- 错误日志必须能关联到场景、角色、事件或导出任务。
- 对话生成、TTS、Lip Sync、导出任务需记录耗时统计，供性能排查。
