# AI Shortfilm Pipeline Design Pack

本文档包基于《项目需求文档 V1.8》整理，目标是提供一套严格对齐 PRD、可用于概要设计评审的交付物。

## 文档清单

1. `01-hld-overview.md`
   - HLD 概要设计
   - 包含架构图、模块拆分、核心数据流、双后端适配器、降级策略、第三方集成与高层接口
2. `02-interface-spec.md`
   - 模块统一接口规约
   - 包含请求响应包结构、错误码、超时、重试、熔断规则
3. `03-data-schema.md`
   - 数据结构设计说明
   - 对应 `schemas/` 目录中的 JSON Schema 文件
4. `04-dev-deployment.md`
   - 开发部署文档
   - 包含依赖、端口规划、启动顺序、硬件评估与排障
5. `05-integration-test-outline.md`
   - 集成测试大纲与核心测试用例

## Schema 文件

- `schemas/project.schema.json`
- `schemas/persona.schema.json`
- `schemas/script.schema.json`
- `schemas/camera.schema.json`
- `schemas/cache.schema.json`
- `schemas/log.schema.json`

## 设计约束

- 严格对齐 PRD，不新增产品功能。
- 模块低耦合，单模块异常不应中断剧情推进。
- 默认运行环境为全本地、离线、零付费、全开源组件组合。
- 本批文档为 HLD 级别，不展开 GDScript 底层实现细节。
