from __future__ import annotations

import html
from pathlib import Path

import gradio as gr
from modules import shared

from .service import collect_positive_prompts, write_export_file


UI_CSS = (Path(__file__).parents[1] / "style.css").read_text(encoding="utf-8")


def create_ui():
    with gr.Blocks(analytics_enabled=False, css=UI_CSS, elem_id="png_prompt_collector") as interface:
        gr.Markdown("## PNG 正向提示词汇总", elem_classes="ppc-heading")
        with gr.Row(equal_height=False, elem_classes="ppc-shell"):
            with gr.Column(scale=5, min_width=320, elem_classes=["ppc-input-column", "ppc-workflow-section"], elem_id="ppc_collection_workspace"):
                uploads = gr.File(label="导入 PNG 原图", file_count="multiple", file_types=[".png"], type="filepath", height=230, elem_id="ppc_uploads")
                with gr.Accordion("读取本机目录", open=False, visible=not shared.cmd_opts.hide_ui_dir_config):
                    directory = gr.Textbox(label="PNG 目录", placeholder=r"E:\images\outputs", elem_id="ppc_directory")
                    recursive = gr.Checkbox(label="包含子目录", value=True, elem_id="ppc_recursive")
                with gr.Row(elem_classes="ppc-options"):
                    deduplicate = gr.Checkbox(label="去除重复 tag", value=True, elem_id="ppc_deduplicate")
                    ignore_case = gr.Checkbox(label="去重时忽略大小写", value=True, elem_id="ppc_ignore_case")
                with gr.Row(elem_classes="ppc-actions"):
                    collect_button = gr.Button("读取并汇总", variant="primary", elem_id="ppc_collect")
                    clear_button = gr.Button("清空", elem_id="ppc_clear")
            with gr.Column(scale=7, min_width=360, elem_classes=["ppc-output-column", "ppc-workflow-section"], elem_id="ppc_collection_status"):
                status = gr.HTML(_status_html("idle", "等待导入 PNG", ""), elem_id="ppc_status")
                result_text = gr.Textbox(label="汇总后的正向 prompt tag", lines=11, max_lines=24, interactive=False, show_copy_button=True, elem_id="ppc_result")
                with gr.Column(elem_classes=["ppc-llm-link", "ppc-workflow-section"], elem_id="ppc_llm_handoff"):
                    gr.Markdown("### LLM Prompt Studio 联动")
                    with gr.Row(elem_classes="ppc-llm-controls"):
                        llm_transfer_mode = gr.Radio(label="发送方式", choices=["覆盖", "追加"], value="覆盖", scale=2, elem_id="ppc_transfer_mode")
                        send_to_llm = gr.Button("发送并打开 LLM Prompt Studio", scale=3, elem_id="ppc_send_to_llm")
                    llm_status = gr.HTML(_status_html("idle", "等待发送到 LLM Prompt Studio", ""), elem_id="ppc_llm_status")
                with gr.Column(elem_id="ppc_export_result", elem_classes="ppc-workflow-section"):
                    download = gr.File(label="导出 TXT", interactive=False, elem_id="ppc_download")
        with gr.Accordion("Tag 统计", open=False, elem_classes="ppc-workflow-section"):
            summary_table = gr.Dataframe(headers=["Tag", "出现次数", "来源图片数"], datatype=["str", "number", "number"], value=[], row_count=(0, "dynamic"), col_count=(3, "fixed"), type="array", height=420, interactive=False, wrap=True, column_widths=["70%", "15%", "15%"], elem_id="ppc_summary")
        with gr.Accordion("未读取文件", open=False, elem_id="ppc_errors_section", elem_classes="ppc-workflow-section"):
            errors = gr.Textbox(show_label=False, lines=5, max_lines=12, interactive=False, elem_id="ppc_errors")
        outputs = [status, result_text, summary_table, download, errors]
        collect_button.click(fn=run_collection, inputs=[uploads, directory, recursive, deduplicate, ignore_case], outputs=outputs)
        send_to_llm.click(fn=None, inputs=[result_text, llm_transfer_mode], outputs=llm_status, js="(prompt, mode) => window.pngPromptCollector.sendToLlmPromptStudio(prompt, mode)")
        clear_button.click(fn=clear_collection, outputs=[uploads, directory, *outputs, llm_status])
    return [(interface, "PNG Tag 汇总", "png_prompt_collector")]


def run_collection(uploaded_files, directory, recursive, deduplicate, ignore_case):
    try:
        imported = collect_positive_prompts(uploaded_files=uploaded_files, directory=directory, recursive=recursive, deduplicate=deduplicate, ignore_case=ignore_case)
    except Exception as exc:
        return _status_html("error", "读取失败", str(exc)), "", [], None, str(exc)
    result = imported.collection
    rows = [[item.tag, item.occurrences, item.source_count] for item in result.summaries]
    error_text = "\n".join(imported.errors)
    if imported.selected_count == 0:
        return _status_html("idle", "没有待处理的 PNG", error_text or "请导入 PNG，或填写可读取的本机目录。"), "", [], None, error_text
    if imported.imported_count == 0:
        return _status_html("error", "未读取到正向提示词", f"检查了 {imported.selected_count} 张 PNG。"), "", [], None, error_text
    export_path = write_export_file(result.text)
    details = [f"读取 {imported.imported_count}/{imported.selected_count} 张 PNG", f"{len(result.summaries)} 个唯一 tag"]
    if deduplicate:
        details.append(f"去除 {result.duplicates_removed} 个重复项")
    if imported.skipped_count:
        details.append(f"跳过 {imported.skipped_count} 张")
    return _status_html("warning" if imported.skipped_count else "success", "汇总完成，部分文件未读取" if imported.skipped_count else "汇总完成", " · ".join(details)), result.text, rows, export_path, error_text


def clear_collection():
    return None, "", _status_html("idle", "等待导入 PNG", ""), "", [], None, "", _status_html("idle", "等待发送到 LLM Prompt Studio", "")


def _status_html(kind: str, headline: str, detail: str) -> str:
    safe_kind = kind if kind in {"idle", "success", "warning", "error"} else "idle"
    detail_html = f"<span>{html.escape(str(detail))}</span>" if detail else ""
    return f'<div class="ppc-status ppc-status--{safe_kind}" role="status" aria-live="polite"><strong>{html.escape(str(headline))}</strong>{detail_html}</div>'
