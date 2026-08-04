(function () {
    "use strict";
    const TARGET_ID = "llm_prompt_studio_source_tags";
    const TOP_LEVEL_TAB_ID = "tab_llm_prompt_studio";
    const GENERATE_TABS_ID = "llm_prompt_studio_main_tabs";
    function appRoot() { return typeof gradioApp === "function" ? gradioApp() : document; }
    function componentInput(componentId) {
        const component = appRoot().querySelector(`#${componentId}`);
        if (!component) return null;
        return component.matches("textarea, input") ? component : component.querySelector("textarea, input");
    }
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
    function openPromptStudio() {
        const root = appRoot();
        const topButton = tabButton(root.querySelector("#tabs"), TOP_LEVEL_TAB_ID, "LLM 提示词工作室");
        if (topButton) topButton.click();
        const generateButton = tabButton(root.querySelector(`#${GENERATE_TABS_ID}`), "llm_prompt_studio_generate_tab", "生成");
        if (generateButton) generateButton.click();
    }
    function status(kind, headline, detail) {
        const escapeHtml = (value) => String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;");
        const safeKind = ["idle", "success", "warning", "error"].includes(kind) ? kind : "idle";
        const suffix = detail ? `<span>${escapeHtml(detail)}</span>` : "";
        return `<div class="ppc-status ppc-status--${safeKind}" role="status" aria-live="polite"><strong>${escapeHtml(headline)}</strong>${suffix}</div>`;
    }
    function sendToLlmPromptStudio(prompt, mode) {
        const incoming = String(prompt || "").trim();
        if (!incoming) return status("warning", "没有可发送的正向 tag", "请先读取并汇总 PNG。");
        const input = componentInput(TARGET_ID);
        if (!input) return status("error", "未找到 LLM Prompt Studio", "请确认扩展已启用并重新加载 Forge。");
        const current = String(input.value || "").trim();
        const append = (mode === "追加" || mode === "Append") && current;
        const value = append ? `${current.replace(/[\s,]+$/, "")}, ${incoming}` : incoming;
        setInputValue(input, value);
        openPromptStudio();
        input.focus({ preventScroll: true });
        const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        input.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
        return status("success", `${append ? "已追加" : "已覆盖"} LLM Prompt Studio 源标签`, `${value.length} 个字符`);
    }
    window.pngPromptCollector = { sendToLlmPromptStudio, openPromptStudio };
})();
