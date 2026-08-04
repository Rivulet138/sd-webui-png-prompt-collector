# PNG Positive Prompt Collector

Forge Neo / AUTOMATIC1111 extension for collecting positive prompt tags from previously generated PNG images.

## Features

- Imports multiple PNG files or scans a local directory.
- Reads Forge/A1111 generation metadata and keeps only the positive prompt.
- Uses Forge's active PNG reader, so installed metadata adapters such as ComfyUI PNG Info are supported automatically.
- Splits comma-separated tags without breaking nested prompt syntax such as weighted groups or LoRA tags.
- Deduplicates tags in first-seen order, with optional case-sensitive matching.
- Shows occurrence and source-image counts.
- Sends the collected tags to LLM Prompt Studio in overwrite or append mode.
- Exports the collected positive tags as a UTF-8 TXT file.

Negative prompts and generation parameters are never included in the collected output.

## Usage

1. Restart Forge Neo after placing this folder under `extensions`.
2. Open the **PNG Tag 汇总** tab.
3. Upload PNG originals, or select a local directory.
4. Click **读取并汇总**.
5. Download the generated TXT file, or use **发送并打开 LLM Prompt Studio**.

## LLM Prompt Studio integration

When `sd-webui-llm-prompt-studio` is enabled, the collector can write its result
to the studio's visible source-tag field and open the **生成** tab. The
transfer supports replacing the current source tags or appending to them. It
does not call the configured LLM automatically.

## Development

Run tests from this extension directory with Forge Neo's Python environment:

```powershell
E:\sd-webui-forge-neo\venv\Scripts\python.exe -m unittest discover -s tests -v
```
