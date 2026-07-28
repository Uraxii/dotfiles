---
name: comfyui
description: Drive a local ComfyUI instance headlessly over its HTTP API to run any exported workflow graph (txt2img, img2img, or other generation pipelines), inject parameters such as prompt text and seed into the workflow JSON, and save the resulting image(s) to disk. Use when the user asks to generate, render, or produce an image via ComfyUI, mentions txt2img, Stable Diffusion rendering, or wants to run/submit a ComfyUI workflow.
---

# comfyui

Drive ComfyUI over HTTP. Mechanical only, no vision, no judgment: submit ->
poll -> save.

## Run it

```bash
python3 ~/.claude/skills/comfyui/comfyui.py \
  --template <project>/art-workflows/txt2img.json \
  --set 6.inputs.text="a red fox in snow, photograph" \
  --set 3.inputs.seed=$RANDOM \
  --out <project>/renders/fox.png
```

`--set NODE.FIELD.PATH=VALUE`, repeatable. Walks any exported API-format
graph, no hardcoded node ids baked in. Host default
`http://127.0.0.1:8188`, override via `COMFY_HOST` env or `--host`.

Full flag list: `python3 ~/.claude/skills/comfyui/comfyui.py --help`.

## Rules

- Templates live in a durable dir, e.g. `<project>/art-workflows/`. Never
  hand-build a graph JSON per run.
- Vary seed every submission. Identical graph -> ComfyUI serves the cached
  result silently, no image produced. Set seed explicit via
  `--set N.inputs.seed=X` (N = the KSampler node id in that template).
  Tool never guesses which node is sampler.
- Empty outputs = FAILURE, not a skip. Report it. CLI already exits
  non-zero and prints why to stderr on cache hit, timeout, or HTTP error.
- stdout is one JSON object: `prompt_id`, `seed`, `images` (abs paths).
  Parse that, ignore stderr for machine use.
- Never open output image pixels in this context. Pass the path onward to
  a vision critic if judgment is needed.
