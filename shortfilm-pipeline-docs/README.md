# AI Shortfilm Pipeline Design Pack

本文档包已按新的项目方向更新：AI 不再只负责台词和行为，而是正式参与 3D 资产生成。系统目标变为“AI 生成 3D 资产 + 资产后处理与定稿 + Godot 拍摄渲染”的全本地短片生产管线。

## 文档清单

1. `01-hld-overview.md`
   - HLD 概要设计
   - 包含架构图、预生产与拍摄双数据流、AI 建模网关、资产后处理、版本锁定、降级策略与高层接口
2. `02-interface-spec.md`
   - 模块统一接口规约
   - 包含统一请求响应结构、资产生成作业接口、错误码、超时、重试与熔断规则
3. `03-data-schema.md`
   - 数据结构设计说明
   - 对应 `schemas/` 目录中的 JSON Schema 文件
4. `04-dev-deployment.md`
   - 开发部署文档
   - 包含依赖、端口规划、启动顺序、AI 建模与 LLM 硬件评估、排障
5. `05-integration-test-outline.md`
   - 集成测试大纲与核心测试用例

## Schema 文件

- `schemas/project.schema.json`
- `schemas/persona.schema.json`
- `schemas/script.schema.json`
- `schemas/camera.schema.json`
- `schemas/cache.schema.json`
- `schemas/log.schema.json`
- `schemas/generated-asset.schema.json`
- `schemas/asset-revision.schema.json`
- `schemas/retarget-profile.schema.json`
- `schemas/quality-report.schema.json`

## 当前设计边界

- 严格对齐当前方向：AI 参与 3D 资产生产，不再沿用“AI 不参与画面生成”的旧边界。
- 拍摄运行期与资产生成期低耦合，单模块故障不应中断已定稿资产的剧情生产。
- 资产生成失败时，优先回退到最近一次已批准并锁定的资产版本。
- 默认运行环境为全本地、离线、零付费、全开源组件组合。
- 本批文档为 HLD 级别，不展开 GDScript 底层实现细节。
