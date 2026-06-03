# 历史文档归档

本目录只用于保留 Gatherly Web 的历史阶段资料。归档文件可能包含过期说明、重复内容、旧结构引用或历史部署方案，不作为当前项目事实来源。

当前正式方案以 `docs/` 顶层文档为准：

- [../README.md](../README.md)
- [../project-overview.md](../project-overview.md)
- [../project-structure.md](../project-structure.md)
- [../database-design.md](../database-design.md)
- [../er-diagram.md](../er-diagram.md)
- [../deployment-guide.md](../deployment-guide.md)
- [../maintenance-guide.md](../maintenance-guide.md)
- [../github-workflow.md](../github-workflow.md)
- [../development-guide.md](../development-guide.md)
- [../test-report.md](../test-report.md)

重要说明：

- PythonAnywhere 部署说明只代表旧方案 / 历史阶段。
- SQLite 生产数据库说明只代表旧方案 / 历史阶段；当前正式数据库是 Neon PostgreSQL。
- `app/static/uploads/` 生产存储说明只代表旧方案 / 历史阶段；当前正式上传文件存储是 Cloudflare R2。
- `git pull + reload` 只代表旧部署流程；当前流程是 GitHub PR merge 到 `main` 后 Render 自动部署。

`legacy-2026-06-04/` 保存文档整理时从 `docs/` 顶层移入的旧主题文档。
