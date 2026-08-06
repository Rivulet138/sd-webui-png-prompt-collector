# PNG Positive Prompt Collector

Forge Neo / AUTOMATIC1111 扩展，用于从历史 PNG 原图逐张读取完整正向 Prompt，并以“一张图片一条记录”的方式发送给 LLM Prompt Studio 或 Ranbooru。

## 核心功能

- 上传多张 PNG，或扫描本地目录及子目录。
- 读取 Forge / A1111 PNG 元数据中的完整正向 Prompt。
- 一张图片对应一条记录，不拆分、不汇总、不合并不同图片的 Prompt。
- 可按图片文件内容的 SHA-256 去除重复图片。
- 支持 `prompt_batch.v1` JSON 导入和导出。
- 可把完整批次发送到 LLM Prompt Studio 润色/扩写，或发送到 Ranbooru 缓存。
- 长批次可取消；已经读取完成的记录会保留。

负面 Prompt 和生成参数不会进入导出结果。

## 安装

在 Forge Neo 的 `extensions` 目录执行：

```powershell
git clone https://github.com/Rivulet138/sd-webui-png-prompt-collector.git
```

重新启动 Forge Neo，然后在浏览器执行一次 `Ctrl + F5`。

## 面板说明

### 导入图片或 JSON

| 控件 | 作用 |
| --- | --- |
| `导入 PNG 原图` | 选择一张或多张 PNG |
| `PNG 目录` | 扫描本地目录；Forge 隐藏目录配置时不显示 |
| `包含子目录` | 同时扫描目录下的子目录 |
| `按图片内容去重（SHA-256）` | 只去除文件内容完全相同的图片 |
| `读取逐图 Prompt` | 读取图片元数据并建立批次 |
| `取消` | 当前图片处理完成后停止，保留已完成记录 |
| `清空` | 清空当前页面的文件、记录、导出和状态 |
| `导入 prompt_batch.v1 JSON` | 载入此前导出的兼容批次 |

插件只使用一个当前读取取消事件，不维护任务 ID、跨标签页任务所有者或“已有任务正在运行”的阻止状态。

### 逐图正向 Prompt

读取完成后立即显示结果表格：

| 列 | 内容 |
| --- | --- |
| `记录` | 批次内稳定记录 ID |
| `序号` | 原始读取顺序 |
| `图片` | 图片文件名 |
| `完整正向 Prompt` | 该图片自己的完整正向 Prompt |

这里显示的是从 PNG 元数据读出的原始正向 Prompt，不是 LLM 生成结果。LLM 处理后的结果在 LLM Prompt Studio 的 PNG 批处理面板中查看。

### 发送到其他扩展

- `批量发送到 LLM 工作室`：把整批逐图 Prompt 发送到 LLM Prompt Studio 的 `批处理 > PNG 润色 / 扩写`。LLM 会保持顺序和一图一条关系。
- `批量发送到 Ranbooru`：把整批记录直接交给 Ranbooru 导入缓存，不经过 LLM 改写。

这两个按钮用途不同：前者用于生成新的润色/扩写结果，后者用于保存和顺序复用原始记录。

未安装目标扩展时，按钮会报告目标不可用；PNG 读取、去重、表格和 JSON 导入导出仍可独立使用。

### JSON 导出

下载当前 `prompt_batch.v1` 批次。导出保持一图一条，不包含负面 Prompt 和生成参数。

### 未读取文件

显示无法解析、没有正向 Prompt 或读取失败的文件。单个文件失败不会清空其他成功记录。

## 使用流程

### 只收集和导出

1. 上传 PNG 或填写目录。
2. 根据需要启用子目录和 SHA-256 去重。
3. 点击 `读取逐图 Prompt`。
4. 在表格中检查每张图片的正向 Prompt。
5. 展开 `JSON 导出` 下载批次。

### 发送到 LLM 后生图

1. 读取 PNG 批次。
2. 点击 `批量发送到 LLM 工作室`。
3. 打开 LLM Prompt Studio 的 `批处理 > PNG 润色 / 扩写`。
4. 选择润色或扩写并执行批处理。
5. 使用 LLM 面板的 `追加并下一条`，按顺序写入 txt2img / img2img。

### 发送到 Ranbooru 缓存

1. 读取或导入批次。
2. 点击 `批量发送到 Ranbooru`。
3. 在 Ranbooru 的 `Tag 缓存管理` 中查看和使用记录。

## 链路与数据契约

完整联动链路为：

```text
PNG 文件
  -> Collector 读取完整正向 Prompt
  -> prompt_batch.v1（一图一条）
  -> LLM Prompt Studio 润色/扩写（可选）
  -> Ranbooru 缓存或 Forge txt2img / img2img
```

最小记录结构：

```json
{
  "schema_version": "prompt_batch.v1",
  "producer": {"name": "sd-webui-png-prompt-collector"},
  "records": [
    {
      "record_id": "...",
      "index": 1,
      "image": {"filename": "example.png"},
      "prompt": {"positive": "1girl, solo, ..."}
    }
  ]
}
```

SHA-256 去重只比较图片字节，不会因为两张不同图片碰巧使用相同 Prompt 而删除其中一条。

## 取消行为

点击 `取消` 后：

- 当前正在读取的图片完成后停止。
- SHA-256 建批阶段也会响应取消。
- 已完成的记录继续显示并可导出。
- 状态栏报告已完成数量和剩余数量。

没有后台任务租约、任务所有者或跨标签页互斥。

## 开发与验证

```powershell
cd E:\sd-webui-forge-neo\extensions\sd-webui-png-prompt-collector
E:\sd-webui-forge-neo\venv\Scripts\python.exe -m unittest discover -s tests -v
E:\sd-webui-forge-neo\venv\Scripts\python.exe -m ruff check png_prompt_collector scripts tests
E:\sd-webui-forge-neo\venv\Scripts\python.exe -m compileall -q png_prompt_collector scripts tests
```

回归测试覆盖 PNG 元数据解析、一图一条、SHA-256 去重、取消、JSON 契约，以及与 LLM Prompt Studio / Ranbooru 的往返联动。

修改 Python 或 JavaScript 后需要重启 Forge，并执行 `Ctrl + F5`。
