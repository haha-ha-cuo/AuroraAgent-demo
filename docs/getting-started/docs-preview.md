# 文档本地预览

文档站基于 [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) 构建，依赖通过 uv 管理。

## 安装依赖

在仓库根目录执行：

```bash
uv sync --group docs
```

该命令会创建 `.venv` 虚拟环境、安装 `mkdocs-material`，并生成/更新 `uv.lock` 锁文件。

## 启动本地预览

```bash
uv run mkdocs serve
```

浏览器打开 [http://127.0.0.1:8000](http://127.0.0.1:8000) 即可实时预览。修改 `docs/` 下的 Markdown 或 `mkdocs.yml` 后页面会自动刷新。

## 构建静态站点

```bash
uv run mkdocs build --strict
```

- `--strict` 会在出现断链、缺失页面或配置警告时直接报错退出。
- 产物输出到 `site/` 目录（已被 `.gitignore` 忽略）。

## 常见问题

### 依赖安装失败

若个别依赖在最新 Python 版本下缺少预编译 wheel，确认根目录 `.python-version` 为 `3.13`，删除 `.venv` 后重试：

```bash
rm -rf .venv
uv sync --group docs
```

### 端口被占用

`mkdocs serve` 默认占用 8000 端口，可通过 `--dev-addr` 指定其他端口：

```bash
uv run mkdocs serve --dev-addr 127.0.0.1:8080
```
