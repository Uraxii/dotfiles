# image-approval-pipeline (n8n starter workflow)

A starter n8n workflow that ports the retired in-house `workflow-runner`
image-approval pipeline (branch `eb198d5`, never merged) to n8n **built-in
nodes only** (no custom TypeScript nodes).

Flow: a human approves or edits a render prompt **once**, then a deterministic
tail renders the image on ComfyUI, downscales it, and proves connectivity to
the review-serve app. An optional A/B branch compares the approved prompt
against a variant.

This is a **starter template**, not a finished automation. Some nodes are
proven-working; others are honest, clearly-labeled stubs. See the table below.

## Import

1. Open the n8n editor at http://127.0.0.1:5678
2. Top-right menu -> **Import from File**
3. Select `image-approval-pipeline.n8n.json`
4. Open the **Approve prompt** (Form Trigger) node and copy its test URL to
   run the form.

## Node map (retired step -> n8n node)

| Retired step (`steps.py`) | n8n node | Type |
| --- | --- | --- |
| `approval_gate` | **Approve prompt** | Form Trigger (`formTrigger`) |
| `vars:` block | **Runtime variables** | Edit Fields (`set`) |
| `comfy_render` | **Build ComfyUI graph** -> **Submit render** -> **Poll wait 2s** -> **Poll history** -> **Render done?** -> **Extract image ref** -> **Fetch image** | Code + HTTP Request + Wait + IF |
| `image_downscale` | **Downscale (PIL)** | Execute Command (`executeCommand`) |
| `publish_artifact` | **Publish reachability probe** -> **Compose review URL** | HTTP Request + Edit Fields |
| `ab_compare` | **Build variant graph (B)** -> **Submit variant render** -> **A/B publish probe** | Code + HTTP Request |

## approval_gate

n8n's real human-in-the-loop primitive for a web form is the **Form Trigger**
node (`n8n-nodes-base.formTrigger`), which renders a form page and starts the
workflow when the human submits. Because approval is the first step here, the
Form Trigger doubles as both the entry point and the approval gate: it shows
the current prompt in an editable textarea, and whatever the human submits
becomes `approved_prompt` downstream.

For an approval gate in the **middle** of a flow (not the entry), n8n offers
the **n8n Form** node (`n8n-nodes-base.form`) or the **Wait** node
(`n8n-nodes-base.wait`) with resume mode "On Form Submitted" / "On Webhook
Call". Both exist in n8n Community edition. We use the Form Trigger because the
retired pipeline's approval is step 1.

## Runtime variables

The retired YAML had a `vars:` block resolved at invocation. Here the same
variables live in one place: the **Runtime variables** (Edit Fields) node,
right after the trigger. Change them there; every downstream node reads them by
expression, e.g. `{{ $('Runtime variables').first().json.comfy_server }}`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `comfy_server` | `http://host.containers.internal:8188` | ComfyUI base URL (host reachable from the n8n container) |
| `review_server` | `http://host.containers.internal:9099` | review-serve base URL |
| `max_height` | `1080` | downscale target height (px) |
| `project` | `image-approval` | review-serve project name |
| `artifact_id` | `image-approval-latest` | stable artifact id |
| `variant_prompt` | `a red fox in snow, oil painting, dramatic light` | second prompt for A/B |
| `approved_prompt` | `{{ $json.prompt }}` | the human-approved prompt from the form |

`approved_prompt` is intentionally an expression, not a constant: it captures
whatever the human submitted at the Form Trigger.

## comfy_render

Mirrors the retired ComfyUI submit/poll/fetch pattern against
`spikes/comfyui-driver/workflow.json`:

1. **Build ComfyUI graph** (Code node) inlines the template graph and injects
   the approved prompt into node `6` (CLIPTextEncode positive) and a **fresh
   random seed** into node `3` (KSampler). The fresh seed every call is
   required: an identical graph is a silent ComfyUI cache hit that returns
   empty outputs.
2. **Submit render** POSTs `{"prompt": graph}` to `<comfy_server>/prompt` and
   gets a `prompt_id`.
3. **Poll wait 2s** -> **Poll history** GET `<comfy_server>/history/<prompt_id>`
   -> **Render done?** (IF). The IF's false branch loops back to the Wait node.
   This poll loop is intentionally minimal (no max-tries cap yet); see the
   in-canvas "Poll loop" sticky note. **TODO:** add an iteration counter +
   timeout so a stuck render fails loudly instead of looping forever.
4. **Extract image ref** (Code node) pulls the first image's
   filename/subfolder/type out of the history response.
5. **Fetch image** GETs `<comfy_server>/view` with those query params and
   receives the image as a binary file.

## image_downscale (wired STUB)

**Downscale (PIL)** is an Execute Command node that shells out to
`scripts/n8n-container/downscale.py` (a standalone CLI port of the retired
`image_downscale` function: PIL lanczos, never upscales). The script is real
and fully working wherever python3 + Pillow are available.

The node is **disabled by default**, so it passes its input straight through
and does not break the flow. Reason: the official n8n container image ships
neither python3 nor Pillow, so the command cannot run in-container as-is.

To make downscale actually run, pick one:

- **(a)** Mount the script into the container and provide python3 + Pillow,
  then enable the node. This means a custom Containerfile layer or a sidecar,
  which conflicts with the "official image, no custom build" decision.
- **(b)** Run downscale on the **host** out-of-band and have n8n call it over
  HTTP via a tiny host endpoint.

Until one of those is wired, this node is proven only as "the Execute Command
node exists and is correctly wired", not as a working downscale.

## publish_artifact / ab_compare (reachability probe only)

**review-serve has no HTTP endpoint for publishing a new gallery artifact.**
Its `push` operation is CLI-only (`review-serve.py push --project ... --src ...
--id ...`, a subprocess that symlinks a file into a staging dir). review-serve's
only POST endpoints are `/_/api/threads` (+ `/replies`, `/resolve`) for comment
threads, not for publishing.

So **Publish reachability probe** does a `GET <review_server>/_/api/settings`
to prove 2xx connectivity to review-serve from inside the n8n container.
**Compose review URL** then builds the viewer URL the artifact *would* live at
(`<review_server>/_/review?artifact=<artifact_id>`).

To make a real publish work (follow-up, out of scope here), pick one:

- **(a)** Add a small HTTP push endpoint to review-serve, then have this node
  POST the image to it. Recommended.
- **(b)** Use an Execute Command node running `review-serve.py push` with the
  script + its staging dir mounted into the n8n container. This narrows the
  container's mount surface and is likely not worth it.

**ab_compare** mirrors the retired step by **composing** comfy_render +
publish: **Build variant graph (B)** -> **Submit variant render** ->
**A/B publish probe**. These are duplicated-but-clearly-labeled copies of the
render/publish nodes, kept in one importable file (rather than a separate
sub-workflow) for starter-template clarity. They are **disabled by default**;
enable and wire seeds to compare `variant_prompt` against the approved prompt.

## What is proven vs stubbed

| Part | Status |
| --- | --- |
| approval_gate (Form Trigger) | proven pattern (native n8n primitive) |
| Runtime variables | working |
| comfy_render submit/poll/fetch | wired against real endpoints; poll loop is minimal (no timeout cap) |
| image_downscale | wired stub (disabled; needs python3+Pillow in container or a host endpoint) |
| publish_artifact | reachability probe only (no real publish endpoint exists) |
| ab_compare | wired stub (disabled, duplicated-labeled render+publish) |

## Follow-up work

- Add an HTTP push endpoint to review-serve so publish_artifact can actually
  stage an artifact.
- Decide the downscale execution home (container python3+Pillow vs host HTTP
  endpoint) and enable the node.
- Add a max-tries counter + timeout to the ComfyUI poll loop.
