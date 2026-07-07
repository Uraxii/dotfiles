---
name: demo-video-judge
description: Judge a captured clip set for a nikki-net demo against the GDD section 11a gates (defects, presentation conformance vs GDD 8/8b, believability MOS, real-game discrimination, milestones, regression) using a fan-out VLM judge workflow, then file bugs with clip paths and timestamps. Use when the user says "judge these clips", "run the video benchmark", "evaluate <demo> build", or after demo-video-capture completes.
---

# demo-video-judge

Input: a `captures/<demo>/<build>/` directory from demo-video-capture,
plus the demo's GDD (`docs/<GAME>-GDD.md`). Protocol of record:
`docs/eval/gameplay-video-eval.md` sections 3 and 7-9. Gates of record:
the demo GDD section 11a (fallback: `docs/GDD-TEMPLATE.md` section 11).

## Hard rules

- Gates run IN ORDER; first failure stops the run (report it, do not
  keep scoring a failed build).
- 3 judge votes per clip per instrument: majority for binary defects,
  median for 5-point ratings. Judges never see sidecar metadata or
  build identity.
- Presentation gate: the judge prompt embeds the demo GDD sections 8 and
  8b VERBATIM. Missing/vague style declarations = the GDD fails, not the
  game; stop and report that instead.
- Anchored scales only. Never ask a judge for a 0-100 number.
- Every Sev-A flag is verified by re-reading the exact clip+timestamp
  before it is reported (adversarial second look: try to refute it).
- Control clip is judged FIRST. Control dirty = pipeline broken = abort.
- Audio checks run only on the 5 AV clips; WebP is silent.
- Calibration debt: until a human-labeled golden set exists with
  kappa >= 0.6 per axis, mark every verdict PROVISIONAL in the report.

## Procedure

1. Validate inputs: manifest complete (bucket counts, paired clips, AV
   clips, control), GDD sections 8/8b/11a present and filled.
2. Build the run from `references/judge-workflow.md` (Workflow script
   template: pipeline clips through defect pass -> presentation pass ->
   MOS pass; barrier only for discrimination pool, milestone check, and
   Bradley-Terry). Frames for judging: extract with ffmpeg at native
   fps; pass clips, not stills, where the runner supports video input.
3. Gate order: 1 Sev-A=0, 2 Sev-B<=3/30, 3 presentation (0 MISSING,
   <=2 MISMATCH/30), 4 MOS>=3.5 per axis, 5 discrimination <=70%,
   6 milestones all present in all 3 long videos, 7 no Bradley-Terry
   regression vs previous build (skip 7 with a note if no prior build).
4. On gate failure: for each offending finding, extract the evidence
   keyframe (ffmpeg at the flagged timestamp), then file a bug: title,
   gate, clip path, timestamp, keyframe path, expected-vs-observed.
5. Report the GDD 11c verdict block: per-gate PASS/FAIL/PROVISIONAL,
   defect table with clip paths, MOS table with CIs, discrimination
   rate, milestone matrix, bugs filed. Never a single blended score.
