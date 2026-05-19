# 新手 Git 协作指南

## 1. 克隆项目

```bash
git clone 仓库地址
cd gatherly-web
```

## 2. 拉取最新代码

开始写代码前先同步远程更新：

```bash
git pull
```

## 3. 创建分支

每个任务使用单独分支：

```bash
git checkout -b feature/activity-list
```

分支名建议使用英文小写和短横线。

## 4. 查看修改

```bash
git status
```

## 5. 提交代码

```bash
git add .
git commit -m "Add activity list page"
```

提交信息要简短说明本次修改内容。

## 6. 推送分支

```bash
git push origin feature/activity-list
```

## 7. 创建 Pull Request

在 GitHub 页面打开仓库，点击 Compare & pull request，填写修改说明后提交。

## 8. 合并前检查

- 页面能正常打开。
- 链接路径正确。
- 没有提交无关文件。
- 文档或样式变更已经说明清楚。
