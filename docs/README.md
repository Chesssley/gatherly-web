# Gatherly Web 文档索引

最后更新：2026-06-04

本目录整理 Gatherly Web 项目的中文文档。顶层 [README.md](../README.md) 使用英文，面向 GitHub 访问者；`docs/` 下文档面向课程交付、组员协作和维护。

当前正式架构：

- Render：Web runtime / production entry。
- Neon PostgreSQL：正式关系型数据库。
- Cloudflare R2：用户上传图片和认证材料对象存储。
- GitHub：代码、文档和 migrations 版本控制。
- Flask-Migrate / Alembic：数据库迁移。

旧的 PythonAnywhere + SQLite + 本地上传图片方案只属于历史阶段，不作为当前正式部署方案。

## 当前正式架构文档

| 文档 | 用途 |
|---|---|
| [deployment-guide.md](deployment-guide.md) | Render + Neon PostgreSQL + Cloudflare R2 部署流程。 |
| [database-design.md](database-design.md) | 当前 Neon PostgreSQL 数据库模型和字段设计。 |
| [er-diagram.md](er-diagram.md) | 当前 `app/models.py` 对应 Mermaid ER 图。 |
| [maintenance-guide.md](maintenance-guide.md) | 日常维护、数据库维护、R2、Render、GitHub 和安全处理。 |

## 推荐阅读顺序

1. [project-overview.md](project-overview.md)
2. [project-structure.md](project-structure.md)
3. [database-design.md](database-design.md)
4. [er-diagram.md](er-diagram.md)
5. [deployment-guide.md](deployment-guide.md)
6. [maintenance-guide.md](maintenance-guide.md)
7. [github-workflow.md](github-workflow.md)
8. [development-guide.md](development-guide.md)
9. [test-report.md](test-report.md)

## 文档列表

| 文档 | 用途 | 当前架构状态 |
|---|---|---|
| [project-overview.md](project-overview.md) | 项目定位、目标用户、核心功能和主要页面。 | 应以 Render + Neon + R2 为正式架构背景。 |
| [project-structure.md](project-structure.md) | 当前真实仓库目录、关键文件和存储边界。 | 已说明 `migrations/`、`wsgi.py`、R2 service、本地 fallback。 |
| [requirements.md](requirements.md) | 用户故事、功能说明和验收标准。 | 产品需求文档，不作为部署来源。 |
| [product-backlog.md](product-backlog.md) | Backlog 和 Issue 对应关系。 | 任务管理文档。 |
| [database-design.md](database-design.md) | 当前真实数据库模型字段、约束、关系和迁移流程。 | 正式数据库为 Neon PostgreSQL。 |
| [er-diagram.md](er-diagram.md) | Mermaid ER 图。 | 以当前 `app/models.py` 为准。 |
| [er-diagram.mmd](er-diagram.mmd) | Mermaid 源文件。 | 与 `er-diagram.md` 同步。 |
| [deployment-guide.md](deployment-guide.md) | Render、Neon、R2、GitHub 和迁移部署流程。 | 当前正式部署方案。 |
| [maintenance-guide.md](maintenance-guide.md) | 维护流程、安全规则和泄露处理。 | 当前正式维护方案。 |
| [development-guide.md](development-guide.md) | 本地开发、迁移命令、PR 和自测。 | SQLite / 本地上传仅 local fallback。 |
| [github-workflow.md](github-workflow.md) | 分支、commit、push、PR、review、merge 流程。 | 与 GitHub PR -> Render auto deploy 流程配套。 |
| [issue-management.md](issue-management.md) | Issue 编号、Labels、Milestones 和 Project Board 规则。 | 协作管理文档。 |
| [test-report.md](test-report.md) | 手动测试和验证结果。 | 验证当前代码和文档状态。 |
| [style-guide.md](style-guide.md) | 视觉与 CSS 规范。 | 前端维护文档。 |
| [meeting-notes.md](meeting-notes.md) | Sprint 会议记录。 | 过程记录。 |

## 归档说明

旧部署方案、重复文档、历史文档和不再作为事实来源的内容保留在 [archive/](archive/) 下。

归档规则：

- 归档内容只作为历史阶段记录。
- PythonAnywhere、SQLite 生产数据库、本地上传图片生产存储、服务器 Bash 中 `git pull` 后 reload，只能出现在 archive 中并标注为旧方案。
- 当前部署、数据库、图片存储、维护流程以本目录顶层文档为准。

## 截图目录

截图统一放在 [screenshots/](screenshots/) 中。`screenshots/er-diagram.png` 是历史截图；当前 ER 图事实来源以 [er-diagram.md](er-diagram.md) 和 [er-diagram.mmd](er-diagram.mmd) 为准。
