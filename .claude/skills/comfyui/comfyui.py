#!/usr/bin/env python3
"""comfyui.py -- generic ComfyUI HTTP API driver: inject parameters into
any exported API-format workflow JSON via dotted-path --set, submit it,
poll for completion, and save every produced image.

Promoted from spikes/comfyui-driver/run.sh, which hardcoded node ids 6
(prompt text) and 3 (seed) to one workflow. --set walks any dotted path,
so this works against any workflow export, not just that one graph.

No --seed flag: which node is "the" sampler is not reliably detectable
across arbitrary graphs, so guessing would silently inject the seed into
the wrong node. Set it explicitly instead, e.g.:
    --set 3.inputs.seed=12345
and vary it on every submission. ComfyUI caches node execution, so an
identical graph completes instantly with no image, and this tool treats
that as a failure (see ComfyCacheHit below), never a silent success.

Usage:
    comfyui.py --template workflow.json \\
        --set 6.inputs.text="a red fox in snow" \\
        --set 3.inputs.seed=12345 \\
        --out /tmp/renders/fox.png

Prints one JSON object to stdout: {"prompt_id", "seed", "images": [...]}.
Human progress goes to stderr. Exits non-zero on a cache hit, timeout,
HTTP error, or a bad --set path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_HOST = "http://127.0.0.1:8188"
DEFAULT_TIMEOUT_SEC = 300.0  # spike's proven cadence: 150 polls x 2s
POLL_INTERVAL_SEC = 2.0
HTTP_TIMEOUT_SEC = 30.0  # per-request socket timeout, not the render wait
DEFAULT_OUT = Path("out.png")

RenderStatus = Literal["done", "cached", "pending"]


class ComfyCacheHit(Exception):
    """Raised when a completed history entry has no images: the graph was
    byte-identical to a prior run and ComfyUI served the cached (empty)
    result instead of rendering."""


@dataclass
class ImageRef:
    """One image reference from a ComfyUI history entry."""

    filename: str
    subfolder: str
    type: str


def coerce_literal(raw: str) -> int | float | str:
    """Parse raw as int, else float, else keep it as a plain string."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def parse_set_flag(flag: str) -> tuple[str, str]:
    """Split one --set PATH=VALUE argument into (path, raw_value)."""
    path, sep, value = flag.partition("=")
    if not sep:
        raise ValueError(f"--set must be PATH=VALUE, got {flag!r}")
    return path, value


def apply_set(graph: dict, dotted_path: str, raw_value: str) -> None:
    """Walk a dotted path like '6.inputs.text' into graph and set the
    leaf to raw_value, coerced to int/float when it parses as one."""
    parts = dotted_path.split(".")
    if len(parts) < 2:
        raise ValueError(f"--set path needs at least NODE.FIELD: {dotted_path!r}")
    node_id, *steps = parts
    if node_id not in graph:
        raise ValueError(f"--set: no node {node_id!r} in template")
    target = graph[node_id]
    for step in steps[:-1]:
        if not isinstance(target, dict) or step not in target:
            raise ValueError(f"--set: path {dotted_path!r} not found at {step!r}")
        target = target[step]
    leaf = steps[-1]
    if not isinstance(target, dict):
        raise ValueError(f"--set: path {dotted_path!r} does not resolve to an object")
    target[leaf] = coerce_literal(raw_value)


def extract_image_refs(entry: dict) -> list[ImageRef]:
    """Flatten every image any output node produced in one history entry."""
    refs = []
    for output in entry.get("outputs", {}).values():
        for img in output.get("images", []):
            refs.append(
                ImageRef(
                    filename=img["filename"],
                    subfolder=img.get("subfolder", ""),
                    type=img.get("type", "output"),
                )
            )
    return refs


def classify_history_entry(entry: dict) -> RenderStatus:
    """'done' once images are ready, 'cached' when ComfyUI silently
    served a prior identical run (completed, no images), else 'pending'."""
    if extract_image_refs(entry):
        return "done"
    if entry.get("status", {}).get("completed", False):
        return "cached"
    return "pending"


def find_seed(graph: dict) -> int | float | str | None:
    """First 'seed' input anywhere in the graph, for reporting only --
    never used to decide where to inject a seed."""
    for node in graph.values():
        inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
        if "seed" in inputs:
            return inputs["seed"]
    return None


def resolve_output_paths(out: Path, refs: list[ImageRef]) -> list[Path]:
    """Where to save each ref: --out as a directory when it is one or
    ends in '/', a literal path for a single image, else a numbered
    prefix, so a batch render keeps every image instead of the spike's
    first-only behavior."""
    if out.is_dir() or str(out).endswith("/"):
        return [out / ref.filename for ref in refs]
    if len(refs) == 1:
        return [out]
    stem, suffix = out.stem, out.suffix or ".png"
    return [out.with_name(f"{stem}-{i}{suffix}") for i in range(len(refs))]


def http_get_json(url: str) -> dict:
    """GET url and parse the JSON body."""
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_SEC) as resp:
        return json.load(resp)


def submit_prompt(host: str, graph: dict) -> str:
    """POST the graph to /prompt, return the queued prompt_id."""
    body = json.dumps({"prompt": graph}).encode("utf-8")
    request = urllib.request.Request(
        f"{host}/prompt",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SEC) as resp:
        return json.load(resp)["prompt_id"]


def poll_history(host: str, prompt_id: str, timeout_sec: float) -> dict:
    """Poll GET /history/<id> every POLL_INTERVAL_SEC until an entry is
    done. Raises ComfyCacheHit on a silent cache hit, TimeoutError past
    timeout_sec."""
    deadline = time.monotonic() + timeout_sec
    while True:
        history = http_get_json(f"{host}/history/{prompt_id}")
        entry = history.get(prompt_id)
        status = classify_history_entry(entry) if entry else "pending"
        if status == "done":
            return entry
        if status == "cached":
            raise ComfyCacheHit(
                f"prompt {prompt_id}: graph fully cached, no image "
                "produced -- vary the seed or prompt and resubmit"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for prompt {prompt_id}")
        time.sleep(POLL_INTERVAL_SEC)


def download_image(host: str, ref: ImageRef, dest: Path) -> None:
    """GET /view for one image ref and write its bytes to dest."""
    query = urllib.parse.urlencode(
        {"filename": ref.filename, "subfolder": ref.subfolder, "type": ref.type}
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f"{host}/view?{query}", timeout=HTTP_TIMEOUT_SEC) as resp:
        dest.write_bytes(resp.read())


def render(
    template: Path, sets: list[str], host: str, out: Path, timeout_sec: float
) -> dict:
    """Build the graph, submit it, wait for images, save them all."""
    graph = json.loads(template.read_text(encoding="utf-8"))
    for flag in sets:
        path, raw_value = parse_set_flag(flag)
        apply_set(graph, path, raw_value)

    print(f"comfyui: submitting {template}", file=sys.stderr)
    prompt_id = submit_prompt(host, graph)
    print(f"comfyui: queued prompt_id={prompt_id}", file=sys.stderr)

    entry = poll_history(host, prompt_id, timeout_sec)
    refs = extract_image_refs(entry)
    dest_paths = resolve_output_paths(out, refs)
    for ref, dest in zip(refs, dest_paths):
        download_image(host, ref, dest)
        print(f"comfyui: saved {dest}", file=sys.stderr)

    return {
        "prompt_id": prompt_id,
        "seed": find_seed(graph),
        "images": [str(p.resolve()) for p in dest_paths],
    }


def resolve_host(cli_value: str | None) -> str:
    """--host > COMFY_HOST env > DEFAULT_HOST."""
    return cli_value or os.environ.get("COMFY_HOST") or DEFAULT_HOST


def build_parser() -> argparse.ArgumentParser:
    """Construct the render CLI."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--template", required=True, type=Path,
        help="ComfyUI workflow JSON, exported in API format",
    )
    parser.add_argument(
        "--set", dest="sets", action="append", default=[], metavar="PATH=VALUE",
        help="repeatable dotted-path injection, e.g. 6.inputs.text='a fox' "
        "or 3.inputs.seed=12345 (int/float literals are coerced)",
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT,
        help=f"output path, prefix, or directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--host", default=None,
        help="ComfyUI base URL (default: COMFY_HOST env, else "
        f"{DEFAULT_HOST})",
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT_SEC,
        help=f"seconds to poll before giving up (default: {DEFAULT_TIMEOUT_SEC})",
    )
    return parser


def main(argv: list[str]) -> int:
    """CLI entry point: render one workflow and print its result JSON."""
    args = build_parser().parse_args(argv)
    host = resolve_host(args.host)
    try:
        result = render(args.template, args.sets, host, args.out, args.timeout)
    except (ComfyCacheHit, TimeoutError, ValueError, OSError) as exc:
        print(f"comfyui: {exc}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"comfyui: HTTP error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
