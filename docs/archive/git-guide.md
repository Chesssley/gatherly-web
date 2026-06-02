# 新手 Git 协作指南

本文档给新手组员使用，聚焦 Pull、Branch、Commit、Push、PR 和删除已合并分支。

## 1. 开始前拉取最新代码

每次开发前先切回 `main` 并同步远程代码：

```bash
git checkout main
git pull origin main
```

## 2. 创建任务分支

每个 Issue 使用独立分支，不直接在 `main` 上开发。

```bash
git checkout -b feature/activity-list
```

推荐分支命名：

- `feature/功能名`
- `fix/问题名`
- `docs/文档名`
- `task/任务编号-简短说明`

## 3. 查看修改状态

```bash
git status
```

提交前确认没有缓存文件、数据库文件、临时文件或无关文件。

## 4. 添加并提交修改

```bash
git add README.md docs/git-guide.md
git commit -m "Update project documentation"
```

提交信息应简短说明本次修改内容。不要把多个无关任务混在同一个 commit 中。

## 5. 推送分支

```bash
git push origin feature/activity-list
```

如果是第一次推送当前分支，也可以使用：

```bash
git push -u origin feature/activity-list
```

## 6. 创建 Pull Request

在 GitHub 仓库页面点击 Compare & pull request，填写：

- 关联的 Issue 编号。
- 本次修改内容。
- 本地验证方式。
- 是否影响数据库、路由或模板。
- 是否包含截图或演示材料。

PR 合并前需要至少完成基本运行检查。

## 7. 合并后同步本地 main

PR 合并后，本地执行：

```bash
git checkout main
git pull origin main
```

## 8. 删除已合并分支

删除本地分支：

```bash
git branch -d feature/activity-list
```

删除远程分支：

```bash
git push origin --delete feature/activity-list
```

只删除已经合并的分支。如果分支尚未合并，先确认是否还需要保留。

## 9. 合并前检查清单

- 页面可以正常打开。
- 链接和路由路径正确。
- 没有提交 `__pycache__`、`.pyc`、`.db`、`.env`、临时文件。
- 没有修改与当前 Issue 无关的业务逻辑。
- 文档或样式变更已在 PR 描述中说明。
# 历史归档，仅供参考

> 本文件为本次文档整理前的旧版材料，可能包含过期结构、重复说明或编码损坏内容。当前 GitHub 协作流程请以 [../development-workflow.md](../development-workflow.md) 为准。
