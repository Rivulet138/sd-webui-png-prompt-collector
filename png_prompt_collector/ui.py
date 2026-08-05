from __future__ import annotations

import html
import threading
import uuid
from pathlib import Path

import gradio as gr
from modules import shared

from .service import build_prompt_batch_with_stats, collect_positive_prompts, export_prompt_batch, import_prompt_batch

UI_CSS = (Path(__file__).parents[1] / "style.css").read_text(encoding="utf-8")
_COLLECTION_TASKS: dict[str, threading.Event] = {}
_COLLECTION_TASKS_LOCK = threading.Lock()

def create_ui():
    with gr.Blocks(analytics_enabled=False, css=UI_CSS, elem_id="png_prompt_collector") as interface:
        gr.Markdown("## PNG 正向 Prompt 逐图收集器", elem_classes="ppc-heading")
        with gr.Accordion("导入图片或 JSON", open=True, elem_id="ppc_collection_workspace", elem_classes="ppc-workflow-section"):
            with gr.Row(elem_classes="ppc-shell"):
                with gr.Column(scale=1):
                    uploads = gr.File(label="导入 PNG 原图", file_count="multiple", file_types=[".png"], type="filepath", elem_id="ppc_uploads")
                    directory = gr.Textbox(label="PNG 目录", placeholder=r"E:\images\outputs", elem_id="ppc_directory", visible=not shared.cmd_opts.hide_ui_dir_config)
                    recursive = gr.Checkbox(label="包含子目录", value=True, elem_id="ppc_recursive")
                    deduplicate = gr.Checkbox(label="按图片内容去重（SHA-256）", value=True, elem_id="ppc_deduplicate")
                    with gr.Row():
                        collect = gr.Button("读取逐图 Prompt", variant="primary", elem_id="ppc_collect")
                        cancel = gr.Button("取消", elem_id="ppc_cancel")
                        clear = gr.Button("清空", elem_id="ppc_clear")
                with gr.Column(scale=1):
                    json_import = gr.File(label="导入 prompt_batch.v1 JSON", file_types=[".json"], type="filepath", elem_id="ppc_json_import")
                    import_button = gr.Button("载入 JSON 批次", elem_id="ppc_import_json")
                    status = gr.HTML(_status("idle", "等待导入", ""), elem_id="ppc_collection_status")
        with gr.Accordion("逐图正向 Prompt", open=True, elem_id="ppc_records_section", elem_classes="ppc-workflow-section"):
            records = gr.Dataframe(headers=["记录", "序号", "图片", "完整正向 Prompt"], datatype=["str", "number", "str", "str"], interactive=False, wrap=True, elem_id="ppc_prompt_records")
        with gr.Accordion("发送到其他扩展", open=True, elem_id="ppc_llm_handoff", elem_classes="ppc-workflow-section"):
            with gr.Row():
                send_llm = gr.Button("批量发送到 LLM 工作室", variant="primary", elem_id="ppc_send_to_llm")
                send_ranbooru = gr.Button("批量发送到 Ranbooru", elem_id="ppc_send_to_ranbooru")
            llm_status = gr.HTML(_status("idle", "尚未发送批次", ""), elem_id="ppc_llm_status")
        with gr.Accordion("JSON 导出", open=False, elem_id="ppc_export_result", elem_classes="ppc-workflow-section"):
            export = gr.File(label="导出 prompt_batch.v1 JSON", interactive=False, elem_id="ppc_download")
        with gr.Accordion("未读取文件", open=False, elem_id="ppc_errors_section", elem_classes="ppc-workflow-section"):
            errors = gr.Textbox(show_label=False, lines=5, interactive=False, elem_id="ppc_errors")
        payload = gr.JSON(value={"schema_version": "prompt_batch.v1", "producer": {"name": "sd-webui-png-prompt-collector"}, "records": []}, elem_id="ppc_prompt_batch_payload", visible=False)
        collection_task_id = gr.State(lambda: uuid.uuid4().hex)
        outputs = [status, records, payload, export, errors]
        collect.click(_collect, [uploads, directory, recursive, deduplicate, collection_task_id], outputs)
        cancel.click(_cancel, inputs=collection_task_id, outputs=status, queue=False)
        import_button.click(_import, [json_import], outputs)
        send_llm.click(None, [payload], [llm_status], js="(batch) => window.pngPromptCollector.sendBatchToLlm(batch)")
        send_ranbooru.click(None, [payload], [llm_status], js="(batch) => window.pngPromptCollector.sendBatchToRanbooru(batch)")
        clear.click(_clear, outputs=[uploads, directory, *outputs, llm_status])
    return [(interface, "PNG Prompt Collector", "png_prompt_collector")]

def _rows(batch):
    return [[r["record_id"], r["index"], r["image"]["filename"], r["prompt"]["positive"]] for r in batch["records"]]

def _collect(uploaded, directory, recursive, deduplicate, task_id="", progress=gr.Progress()):
    task_id = str(task_id or "")
    event = threading.Event()
    with _COLLECTION_TASKS_LOCK:
        if task_id in _COLLECTION_TASKS:
            return _status("warning", "已有读取任务正在运行", "请等待完成或先取消当前任务"), gr.update(), gr.update(), gr.update(), gr.update()
        _COLLECTION_TASKS[task_id] = event
    try:
        def report_progress(completed, total, path):
            progress((completed, total), desc=f"读取 {path.name}", unit="张")

        result = collect_positive_prompts(
            uploaded,
            directory,
            recursive,
            progress=report_progress,
            is_cancelled=event.is_set,
        )
        try:
            build_cancelled = None if result.cancelled_count else event.is_set
            build_result = build_prompt_batch_with_stats(result.records, deduplicate, build_cancelled)
            batch = build_result.batch
        except Exception as exc:
            return _status("error", "无法建立 JSON 批次", str(exc)), [], _empty_batch(), None, str(exc)
    finally:
        with _COLLECTION_TASKS_LOCK:
            if _COLLECTION_TASKS.get(task_id) is event:
                _COLLECTION_TASKS.pop(task_id, None)
    error_text = "\n".join(result.errors)
    cancelled_count = result.cancelled_count + build_result.cancelled_count
    if not result.selected_count:
        return _status("idle", "没有待处理的文件", "请选择 PNG 或 JSON"), [], batch, None, error_text
    if not batch["records"]:
        headline = "读取已取消" if cancelled_count else "未读取到正向 Prompt"
        return _status("warning" if cancelled_count else "error", headline, f"已建立 0/{result.imported_count} 条记录"), [], batch, None, error_text
    kind = "warning" if result.skipped_count or cancelled_count else "success"
    duplicates_removed = build_result.processed_count - len(batch["records"])
    detail = f"读取 {result.imported_count} 张；已建立 {build_result.processed_count}/{result.imported_count} 条；当前批次 {len(batch['records'])} 条"
    if cancelled_count:
        detail += f"；取消时剩余 {cancelled_count} 张"
    if duplicates_removed:
        detail += f"；去除重复图片 {duplicates_removed} 张"
    headline = "读取已取消，已完成记录已保留" if cancelled_count else "逐图 Prompt 已读取"
    return _status(kind, headline, detail), _rows(batch), batch, export_prompt_batch(batch) if batch["records"] else None, error_text

def _import(value):
    try:
        batch = import_prompt_batch(value)
    except Exception as exc:
        return _status("error", "JSON 导入失败", str(exc)), [], _empty_batch(), None, str(exc)
    return _status("success", "JSON 批次已载入", f"共 {len(batch['records'])} 条逐图 Prompt"), _rows(batch), batch, export_prompt_batch(batch), ""


def _clear():
    return None, "", _status("idle", "等待导入", ""), [], _empty_batch(), None, "", _status("idle", "尚未发送批次", "")


def _cancel(task_id=""):
    with _COLLECTION_TASKS_LOCK:
        event = _COLLECTION_TASKS.get(str(task_id or ""))
        if event is None:
            return _status("idle", "当前没有读取任务", "未发送取消请求")
        event.set()
    return _status("warning", "已请求取消读取", "当前图片处理完成后停止；已完成记录会保留")


def _empty_batch():
    return {"schema_version": "prompt_batch.v1", "producer": {"name": "sd-webui-png-prompt-collector"}, "records": []}

def _status(kind, headline, detail):
    safe = kind if kind in {"idle", "success", "warning", "error"} else "idle"
    return f'<div class="ppc-status ppc-status--{safe}" role="status" aria-live="polite"><strong>{html.escape(str(headline))}</strong><span>{html.escape(str(detail))}</span></div>'
