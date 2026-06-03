# Gatherly Web 文档索引

最后更新时间：2026-06-04

本目录整理 Gatherly Web / 聚场项目的中文详细文档。顶层 [README.md](../README.md) 面向 GitHub 访问者，使用英文；本目录下文档面向课程交付、组员协作和新手开发者，使用中文。

## 推荐阅读顺序

1. [项目概述](project-overview.md)
2. [项目结构](project-structure.md)
3. [需求说明](requirements.md)
4. [数据库设计](database-design.md)
5. [GitHub 协作规范](github-workflow.md)
6. [开发指南](development-guide.md)
7. [测试报告](test-report.md)
8. [会议记录](meeting-notes.md)

## 文档列表

| 文档 | 用途 | 适合阅读对象 | 最后更新时间 |
|---|---|---|---|
| [project-overview.md](project-overview.md) | 说明项目背景、目标用户、核心价值和主要页面 | 老师、组员、新成员 | 2026-06-04 |
| [project-structure.md](project-structure.md) | 解释当前真实仓库目录、关键文件和高风险文件 | 新手开发者、维护者 | 2026-06-04 |
| [requirements.md](requirements.md) | 按模块整理用户故事、功能说明和验收标准 | 产品、开发、测试 | 2026-06-04 |
| [product-backlog.md](product-backlog.md) | 根据 GitHub Issues 和当前模块整理 Backlog | Scrum 记录维护者、组员 | 2026-06-04 |
| [database-design.md](database-design.md) | 根据 `app/models.py` 说明真实数据模型字段和关系 | 后端、数据库、测试 | 2026-06-04 |
| [er-diagram.md](er-diagram.md) | Mermaid ER 图，反映当前 SQLAlchemy 模型关系 | 后端、答辩展示 | 2026-06-04 |
| [github-workflow.md](github-workflow.md) | 说明 clone、分支、commit、push、PR、review、merge 流程 | 所有组员 | 2026-06-04 |
| [issue-management.md](issue-management.md) | 统一 Issue 编号、Labels、Milestones 和 Project Board 规则 | Scrum 记录维护者、组员 | 2026-06-04 |
| [development-guide.md](development-guide.md) | 说明本地运行、虚拟环境、分支命名、PR 模板和自测清单 | 开发者 | 2026-06-04 |
| [style-guide.md](style-guide.md) | 根据当前 CSS 和模板整理视觉规范 | 前端、页面维护者 | 2026-06-04 |
| [test-report.md](test-report.md) | 记录当前功能测试用例、预期结果和验证状态 | 测试、答辩准备 | 2026-06-04 |
| [meeting-notes.md](meeting-notes.md) | 按 Sprint 整理会议记录、问题和下一步计划 | 全体组员、课程检查 | 2026-06-04 |
| [deployment-guide.md](deployment-guide.md) | 说明本地运行，以及 Render + Neon PostgreSQL + Cloudflare R2 部署方案 | 运行维护、答辩演示 | 2026-06-04 |

## 归档说明

旧版重复文档、编码损坏文档或已被新主题文档替代的内容保留在 [archive/](archive/) 下，仅作为过程记录。当前项目说明、运行方式、数据库结构和 ER 图请以本目录顶层文档为准。

本次整理移动到 `docs/archive/legacy-2026-06-04/` 的旧文件包括：

- `development-workflow.md`
- `feature-guide.md`
- `setup-and-deployment.md`
- `testing-guide.md`

## 截图目录

截图统一放在 [screenshots/](screenshots/) 中。已有截图不会被删除。当前 ER 图的主要引用改为 [er-diagram.md](er-diagram.md) 中的 Mermaid 源图；旧图片 `screenshots/er-diagram.png` 保留为历史截图。
