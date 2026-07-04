# SHXY Save Editor

轻量版《山河小侠》存档编辑器，基于 Python + Tkinter。

## 当前功能

- 自动扫描 Steam 安装目录，定位 SHXY 的 `save/` 文件夹
- 支持手动选择 `save/` 目录或游戏目录
- 自动读取 `global.rmmzsave`，展示存档槽位、地点、时长、保存时间
- 载入单个 `file*.rmmzsave` 存档并修改常用字段
- 支持修改：金钱、学点、当前队伍角色 `_paramPlus` 八维属性
- 支持快捷操作：全队属性批量增加，道具/武器/护甲数量批量填满
- 保存前自动创建 `.bak` 备份
- 支持导出当前存档为 JSON
- 保留命令行工具接口，含 scan/export/import/read/edit/batch-export/compare

## 项目结构

```text
shxy-save-editor/
  launch_gui.pyw          # 双击启动 GUI
  run_gui.bat             # Windows 启动脚本
  pyproject.toml
  src/shxy_save_editor/
    gui.py                # Tkinter 图形界面
    locator.py            # Steam / save 目录发现
    model.py              # 存档槽位与编辑模型
    rmmzsave.py           # .rmmzsave 编解码
    cli.py                # 命令行入口
  tests/
```

## 直接运行 GUI

Windows 下最简单的方法：

1. 安装 Python 3.11+
2. 进入项目目录 `D:\Code\shxy-save-editor`
3. 双击 `run_gui.bat`

也可以命令行运行：

```powershell
cd D:\Code\shxy-save-editor
python launch_gui.pyw
```

## 安装后运行

```powershell
cd D:\Code\shxy-save-editor
python -m pip install -e .
shxy-save-editor
```

## 命令行示例

```powershell
# 扫描 Steam 存档目录
python -m shxy_save_editor.cli scan

# 导出存档为 JSON
python -m shxy_save_editor.cli export file1.rmmzsave

# 批量导出当前目录所有存档
python -m shxy_save_editor.cli batch-export --dir . --clean

# 读取某个字段
python -m shxy_save_editor.cli read file1.rmmzsave party._gold

# 直接修改某个字段
python -m shxy_save_editor.cli edit file1.rmmzsave party._gold 99999999

# 对比两个存档
python -m shxy_save_editor.cli compare file0.rmmzsave file1.rmmzsave --path party._gold
```

## 验证

```powershell
cd D:\Code\shxy-save-editor
python -m unittest discover -s tests -v
```

## 备注

这个游戏的 `.rmmzsave` 不是常见教程里的 LZString，而是：

1. JSON
2. zlib deflate 压缩
3. 每个压缩字节按 Latin-1 字符写入 UTF-8 文本

因此读写时必须保持 `newline=''`，否则 Windows 文本换行转换会破坏压缩数据。
