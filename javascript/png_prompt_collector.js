(function () {
    "use strict";
    const TOP_LEVEL_TAB_ID = "tab_llm_prompt_studio";
    const GENERATE_TABS_ID = "llm_prompt_studio_main_tabs";
    function appRoot() { return typeof gradioApp === "function" ? gradioApp() : document; }
    function setInputValue(input, value) {
        const prototype = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
        if (setter) setter.call(input, value); else input.value = value;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function tabButton(container, panelId, label) {
        if (!container) return null;
        const buttons = Array.from(container.querySelectorAll("button"));
        return buttons.find((button) => (button.getAttribute("aria-controls") || "").split(/\s+/).includes(panelId)) || buttons.find((button) => button.textContent.trim() === label) || null;
    }
    function openPngBatchStudio() {
        const root = appRoot();
        const topButton = tabButton(root.querySelector("#tabs"), TOP_LEVEL_TAB_ID, "LLM 提示词工作室");
        if (topButton) topButton.click();
        const batchButton = tabButton(root.querySelector(`#${GENERATE_TABS_ID}`), "llm_prompt_studio_batch_tab", "批处理");
        if (batchButton) batchButton.click();
        window.requestAnimationFrame(() => {
            const pngBatchButton = tabButton(root, "llm_prompt_studio_png_batch_tab", "PNG 润色 / 扩写");
            if (pngBatchButton) pngBatchButton.click();
            const panel = root.querySelector("#llm_prompt_studio_png_batch_tab");
            panel?.scrollIntoView({ behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
        });
    }
    function status(kind, headline, detail) {
        const escapeHtml = (value) => String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;");
        const safeKind = ["idle", "success", "warning", "error"].includes(kind) ? kind : "idle";
        const suffix = detail ? `<span>${escapeHtml(detail)}</span>` : "";
        return `<div class="ppc-status ppc-status--${safeKind}" role="status" aria-live="polite"><strong>${escapeHtml(headline)}</strong>${suffix}</div>`;
    }
    function sendBatch(batch, targetId, label) {
        if (typeof batch === "string") {
            try { batch = JSON.parse(batch); }
            catch (_error) { return status("error", "JSON 批次无效", "无法解析当前批次。" ); }
        }
        const records = Array.isArray(batch?.records) ? batch.records.slice(0, 200) : [];
        if (!records.length) return status("warning", "没有可发送的逐图 Prompt", "请先导入 PNG 或 JSON 批次。" );
        const target = appRoot().querySelector(`#${targetId}`);
        if (!target) return status("error", `未找到 ${label}`, "请确认接收扩展已启用并重新加载 Forge。" );
        const input = target.matches("textarea, input") ? target : target.querySelector("textarea, input");
        if (!input) return status("error", `${label} 接收控件不可用`, "接收扩展没有暴露兼容的 JSON 字段。" );
        const value = JSON.stringify({ schema_version: "prompt_batch.v1", producer: { name: "sd-webui-png-prompt-collector" }, records });
        setInputValue(input, value);
        if (targetId === "llm_prompt_studio_png_batch_payload") openPngBatchStudio();
        if (targetId === "ranbooru_prompt_batch_payload") {
            const importButton = appRoot().querySelector("#ranbooru_prompt_batch_import_btn");
            if (!importButton) return status("error", "Ranbooru 导入按钮不可用", "批次尚未写入缓存。" );
            importButton.click();
        }
        return status("success", `已发送 ${records.length} 条到 ${label}`, targetId === "ranbooru_prompt_batch_payload" ? "已触发 Ranbooru 导入，请查看其导入结果。" : "每张图片仍保持独立记录。" );
    }
    function sendBatchToLlm(batch) { return sendBatch(batch, "llm_prompt_studio_png_batch_payload", "LLM Prompt Studio"); }
    function sendBatchToRanbooru(batch) { return sendBatch(batch, "ranbooru_prompt_batch_payload", "Ranbooru"); }
    window.pngPromptCollector = { openPngBatchStudio, sendBatchToLlm, sendBatchToRanbooru };
})();
