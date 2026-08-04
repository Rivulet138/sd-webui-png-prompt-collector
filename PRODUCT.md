# Product

## Register

product

## Users

Local Stable Diffusion WebUI Forge Neo users who reuse positive prompts from previously generated PNG originals and move those prompts through LLM Prompt Studio or Ranbooru before image generation.

## Product Purpose

Read one complete positive prompt from each PNG, preserve every image as an independent record, deduplicate only identical image bytes, and exchange batches through the shared `prompt_batch.v1` JSON contract. Success means users can import, inspect, polish, export, and append records without prompts from different images being merged.

## Brand Personality

Direct, compact, and work-focused. Chinese labels should expose the next concrete action and keep data boundaries visible.

## Anti-references

Avoid aggregation dashboards, decorative marketing layouts, hidden cross-plugin actions, nested cards, oversized headings, and controls that obscure whether an operation affects one image or the whole batch.

## Design Principles

1. Preserve one-image-one-record identity throughout the workflow.
2. Expose import, export, handoff, and per-record append actions where users need them.
3. Keep advanced or secondary content collapsible without hiding the primary path.
4. Reuse Forge and Gradio interaction patterns so the extension feels native.
5. Report limits, partial failures, deduplication, and completion states explicitly.

## Accessibility & Inclusion

Support keyboard-operable native controls, meaningful labels, live status announcements, readable contrast, reduced-motion preferences, and responsive layouts without page-level horizontal overflow on desktop or mobile.
