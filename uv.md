# 使用 uv 运行项目

## 初始化环境

```powershell
uv sync
```

## 运行 GUI

```powershell
uv run python launch_gui.pyw
```

或：

```powershell
uv run shxy-save-editor
```

## 运行 CLI

```powershell
uv run shxy-save-cli scan
```

## 运行测试

```powershell
uv run python -m unittest discover -s tests -v
```
