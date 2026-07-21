# comfyui-driver spike

Proof that ComfyUI can be driven headless from the shell via its HTTP API:
submit a workflow graph, poll for completion, fetch the output image. No LLM,
no websocket, just curl and stdlib python for JSON handling.

Verified end to end on 2026-07-20 against the ComfyUI server running on
`http://127.0.0.1:8188` (version 0.27.0, local-git deploy, RTX 3080).
A 1024x1024 SDXL image (12 steps) took roughly 15 seconds.

## Files

- `~/dotfiles/spikes/comfyui-driver/run.sh`
  End-to-end driver script (bash + curl + python3 stdlib).
- `~/dotfiles/spikes/comfyui-driver/workflow.json`
  Minimal txt2img workflow template in ComfyUI API format. The script
  injects the positive prompt (node `6`) and seed (node `3`) at runtime.
- `~/dotfiles/spikes/comfyui-driver/out.png`
  Sample output from the verified run.

## Usage

```sh
~/dotfiles/spikes/comfyui-driver/run.sh "your prompt here" 12345 /path/to/out.png
```

All arguments optional: prompt defaults to a test prompt, seed to `$RANDOM`,
output path to `out.png` next to the script. Override the server with
`COMFY_HOST=http://host:port`.

## API flow

1. `POST /prompt` with body `{"prompt": <graph>}`, returns `prompt_id`.
2. Poll `GET /history/<prompt_id>` every 2 s until an entry with
   `outputs.*.images[]` appears (up to 5 minutes).
3. `GET /view?filename=...&subfolder=...&type=...` downloads the image.

## Gotchas learned

- ComfyUI caches node execution. Re-submitting a byte-identical graph
  completes instantly with `outputs: {}` and no image entry. The script
  detects this and exits with an error; a real runner should always vary
  the seed (the default `$RANDOM` seed handles that).
- `subfolder` in the image record is often an empty string; keep it as an
  empty query parameter to `/view`, do not drop it.
- Checkpoint names come from `GET /object_info/CheckpointLoaderSimple`
  (`.CheckpointLoaderSimple.input.required.ckpt_name[0]`). Available on
  this machine at the time of the spike: `RealVisXL_V5.0_fp16.safetensors`,
  `autismmixSDXL_autismmixConfetti.safetensors`,
  `experimental/pony-v7-base.safetensors`,
  `ltxv-2b-0.9.8-distilled-fp8.safetensors`, `sd_xl_base_1.0.safetensors`.
  The template uses `sd_xl_base_1.0.safetensors`.

## Server notes

The running server is a local git install (launch args
`main.py --listen 127.0.0.1 --port 8188`), likely from `~/comfy`.
There is also a stopped podman container `comfyui`
(image `localhost/studio-comfyui:latest`) mapped to the same port; only one
can own 8188 at a time.
