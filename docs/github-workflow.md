# GitHub 协作规范

最后更新时间：2026-06-04

本文面向 GitHub 和 Web 开发新手，说明 Gatherly Web 的协作流程。

## 基本原则

- 不要直接 push 到 `main`。
- 一个 Issue 对应一个分支。
- 一个分支对应一个 Pull Request。
- Pull Request 合并前需要至少一次代码或文档检查。
- 合并后同步本地 `main`，再开始下一个任务。

## Clone 仓库

```bash
git clone https://github.com/Chesssley/gatherly-web.git
cd gatherly-web
```

如果使用 GitHub Desktop：

1. 打开 GitHub Desktop。
2. 选择 `File -> Clone repository`。
3. 选择 `Chesssley/gatherly-web`。
4. 选择本地保存位置。
5. Clone 完成后点击 `Open in Visual Studio Code`。

## 更新 main

开始新任务前，先切回 `main` 并拉取最新代码：

```bash
git switch main
git pull --ff-only origin main
```

如果本地有未提交改动，不要直接 pull。先提交、stash，或确认这些改动是否需要保留。

GitHub Desktop 中的操作：

1. Current Branch 选择 `main`。
2. 点击 `Fetch origin`。
3. 如果有更新，点击 `Pull origin`。

## 为每个 Issue 单独建分支

分支命名建议：

```text
feat/us-04-01-create-activity-page
fix/bug-02-clean-test-circles
docs/doc-04-reorganize-docs-er
ui/ui-01-card-style
enh/enh-03-auto-dismiss-flash
```

命令示例：

```bash
git switch main
git pull --ff-only origin main
git switch -c docs/doc-04-reorganize-docs-er
```

GitHub Desktop 中的操作：

1. 确认当前分支是 `main`。
2. 点击 Current Branch。
3. 点击 `New Branch`。
4. 输入分支名。
5. 创建后再开始修改文件。

## 修改并自测

修改完成后检查状态：

```bash
git status
```

基础自测：

```bash
python -m compileall app
python -c "from app import create_app; app = create_app(); print('app loaded')"
python run.py
```

如果只改文档，也要检查链接路径、标题层级和文件名是否正确。

## Commit

先查看改动：

```bash
git diff
```

添加文件：

```bash
git add README.md docs/
```

提交：

```bash
git commit -m "docs(DOC-04): reorganize documentation and ER diagram"
```

提交信息格式：

```text
type(ISSUE-ID): short description
```

常见 type：

- `feat`
- `fix`
- `docs`
- `style`
- `test`
- `refactor`
- `enh`

## Push

```bash
git push -u origin docs/doc-04-reorganize-docs-er
```

之后同一分支继续提交时可以使用：

```bash
git push
```

## Pull Request

在 GitHub 页面或 GitHub Desktop 中创建 Pull Request。

PR 标题建议：

```text
[DOC-04] Reorganize documentation and ER diagram
```

PR 描述建议：

```markdown
## Summary
- Rewrote README in English.
- Reorganized docs by topic.
- Regenerated database design and ER diagram from app/models.py.

## Verification
- [ ] Checked documentation links.
- [ ] Ran python -m compileall app.
- [ ] Loaded Flask app factory.

Closes #55
Related to #85
```

## Code Review

Review 时重点检查：

- 是否只修改了 Issue 范围内的文件。
- 是否引入了不允许的新技术或依赖。
- 路由、模型、模板、CSS 是否和当前代码一致。
- 文档路径是否能点击。
- 测试说明是否真实，不伪造结果。

## Merge 后同步 main

PR 合并后，所有成员更新本地 `main`：

```bash
git switch main
git pull --ff-only origin main
```

如果旧分支不再需要，可以删除：

```bash
git branch -d docs/doc-04-reorganize-docs-er
```

远程分支可在 GitHub PR 页面删除。

## VS Code 配合方式

- 用 VS Code 打开仓库根目录，不要只打开单个文件。
- 左侧 Source Control 可以查看改动。
- 修改前确认左下角分支名。
- 运行终端命令时确认终端路径是仓库根目录。
- 文档和代码都可以在 VS Code 中预览或搜索。

## 禁止事项

- 不要直接 push 到 `main`。
- 不要把多个不相关 Issue 混在一个 PR。
- 不要提交 `.env`、本地数据库、缓存、虚拟环境或上传备份文件。
- 不要擅自改 `app/models.py`、`app/__init__.py`、`run.py`、`requirements.txt`。
- 不要引入 React、Vue、Bootstrap、新数据库或新依赖。
