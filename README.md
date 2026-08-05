# PNG Positive Prompt Collector

Forge Neo / AUTOMATIC1111 扩展，用于从历史 PNG 原图中逐张读取完整正向 Prompt。

## 功能

- 导入多张 PNG，或扫描本机目录及子目录。
- 读取 Forge/A1111 生成元数据，只保留每张图片的完整正向 Prompt。
- 一张图片对应一条记录，不拆分、不汇总、不同图片之间不合并 Prompt。
- 可按图片内容 SHA-256 去除重复图片。
- 导入和导出统一的 `prompt_batch.v1` JSON。
- 将逐图批次发送到 LLM 工作室进行批量润色/扩写，或发送到 Ranbooru 缓存。
- LLM 结果可按顺序逐条追加到 txt2img 或 img2img 正向 Prompt。

负面 Prompt 和生成参数不会进入导出结果。

## 使用

1. 重启 Forge Neo，打开 **PNG Prompt Collector**。
2. 上传 PNG 原图、填写本机目录，或导入 `prompt_batch.v1` JSON。
3. 点击 **读取逐图 Prompt**。
4. 检查逐图表格后导出 JSON，或发送到 LLM 工作室 / Ranbooru。

## LLM 工作室联动

启用 `sd-webui-llm-prompt-studio` 后，Collector 会把全部逐图记录发送到，不设置批次数量上限。
**批处理 > PNG 润色 / 扩写**。LLM 工作室保持输入顺序和一图一条关系，批处理完成后可用
**追加并下一条** 依次写入原生 txt2img / img2img 正向 Prompt。

## 开发

```powershell
E:\sd-webui-forge-neo\venv\Scripts\python.exe -m unittest discover -s tests -v
```
