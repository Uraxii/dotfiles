# Judge workflow template

Adapt and pass to the Workflow tool. Fill CLIPS/PAIRED/AV/LONG/CONTROL
(clip path lists from the capture manifest), GDD_8_8B (verbatim text),
SEV_A/SEV_B (lists from GDD 11a incl. game-specific entries),
MILESTONES (from GDD 11a gate 6), REAL_POOL (paths to real-game clips),
PREV (previous build clip dir or null). Judges read files themselves
(Read supports images; extract frames with ffmpeg first if the runner
cannot ingest animated WebP directly - 8 evenly spaced frames + the
first/last frame per clip is the fallback sampling).

```js
export const meta = {
  name: 'demo-video-judge',
  description: 'GDD 11a gates over a captured clip set',
  phases: [
    { title: 'Control' }, { title: 'Defects' }, { title: 'Presentation' },
    { title: 'MOS' }, { title: 'Discrimination' }, { title: 'Milestones' },
    { title: 'Regression' },
  ],
}
const { clips, paired, av, longs, control, gdd88, sevA, sevB, milestones, realPool, prev } = args

const DEFECT = { type: 'object', required: ['findings'], properties: { findings: { type: 'array', items: {
  type: 'object', required: ['defect', 'severity', 'timestamp'], properties: {
    defect: { type: 'string' }, severity: { enum: ['A', 'B', 'C'] },
    timestamp: { type: 'string' }, detail: { type: 'string' } } } } } }
const PRESENT = { type: 'object', required: ['findings'], properties: { findings: { type: 'array', items: {
  type: 'object', required: ['axis', 'kind', 'timestamp'], properties: {
    axis: { type: 'string' }, kind: { enum: ['MISSING', 'MISMATCH'] },
    timestamp: { type: 'string' }, detail: { type: 'string' } } } } } }
const MOS = { type: 'object', required: ['goal', 'input', 'react', 'variety', 'feel'],
  properties: Object.fromEntries(['goal','input','react','variety','feel']
    .map(k => [k, { type: 'integer', minimum: 1, maximum: 5 }])) }
const YN = { type: 'object', required: ['answer'], properties: { answer: { type: 'boolean' }, why: { type: 'string' } } }

phase('Control')
const ctrl = await parallel([() => agent(
  `Judge ONLY capture pipeline health of ${control}: encoding artifacts, banding, dropped frames, hitching. Findings as defects.`,
  { schema: DEFECT, label: 'control' })])
if (ctrl[0]?.findings?.length) return { abort: 'PIPELINE_DIRTY', findings: ctrl[0].findings }

const vote3 = (prompt, schema, labelBase, ph) => parallel([0,1,2].map(i => () =>
  agent(prompt + `\n(independent vote ${i + 1})`, { schema, label: `${labelBase}:v${i}`, phase: ph })))
const majority = votes => { const seen = {}; votes.filter(Boolean).flatMap(v => v.findings).forEach(f => {
  const k = `${f.defect || f.axis}|${f.severity || f.kind}`; (seen[k] ||= { f, n: 0 }).n++ })
  return Object.values(seen).filter(e => e.n >= 2).map(e => e.f) }

// Defect + presentation + MOS: one pipeline, no barrier between passes.
const judged = await pipeline(
  [...clips, ...paired.map(p => ({ ...p, pairedView: true }))],
  async (c, _, i) => {
    const path = c.path || c
    const extra = c.pairedView ? ' This clip is host|client side by side of the SAME moment: any divergence between halves (position, state, HUD) is defect host/client view divergence, severity A.' : ''
    const defects = majority(await vote3(
      `Watch ${path}. Report ONLY defects visible in the frames.${extra}\nSeverity A candidates: ${sevA}\nSeverity B candidates: ${sevB}\nTransient small clipping = severity C.`,
      DEFECT, `defect:${i}`, 'Defects'))
    return { path, paired: !!c.pairedView, defects }
  },
  async (r, _, i) => ({ ...r, presentation: majority(await vote3(
    `Style guide (authoritative):\n${gdd88}\nWatch ${r.path}. Report every declared element MISSING and every visible MISMATCH vs the guide. Judge conformance to the declaration, not taste.`,
    PRESENT, `present:${i}`, 'Presentation')) }),
  async (r, _, i) => { const votes = (await vote3(
    `Watch ${r.path} (bots are playing). Rate 1-5 with these anchors: [PASTE 5-LEVEL ANCHORS FOR goal-directedness, input plausibility, reactivity, variety, game feel FROM docs/eval/gameplay-video-eval.md]. Median-honest, no politeness inflation.`,
    MOS, `mos:${i}`, 'MOS')).filter(Boolean)
    const med = k => votes.map(v => v[k]).sort((a, b) => a - b)[Math.floor(votes.length / 2)]
    return { ...r, mos: { goal: med('goal'), input: med('input'), react: med('react'), variety: med('variety'), feel: med('feel') } } })

// Gate math in plain code
const flat = judged.filter(Boolean)
const sevACount = flat.flatMap(r => r.defects).filter(f => f.severity === 'A').length
const sevBCount = flat.flatMap(r => r.defects).filter(f => f.severity === 'B').length
const missing = flat.flatMap(r => r.presentation).filter(f => f.kind === 'MISSING').length
const mismatch = flat.flatMap(r => r.presentation).filter(f => f.kind === 'MISMATCH').length
const axes = ['goal','input','react','variety','feel']
const mos = Object.fromEntries(axes.map(k => [k, flat.reduce((s, r) => s + r.mos[k], 0) / flat.length]))
const gates = []
gates.push({ gate: 1, pass: sevACount === 0, sevACount })
gates.push({ gate: 2, pass: sevBCount <= 3, sevBCount })
gates.push({ gate: 3, pass: missing === 0 && mismatch <= 2, missing, mismatch })
gates.push({ gate: 4, pass: axes.every(k => mos[k] >= 3.5), mos })
if (gates.some(g => !g.pass)) return { verdict: 'FAIL', gates, evidence: flat }

phase('Discrimination')
const pool = [...clips.slice(0, 15).map(p => ({ p, real: false })), ...realPool.map(p => ({ p, real: true }))]
const dis = await parallel(pool.map((c, i) => () =>
  agent(`Watch ${c.p}. Is this footage from a shipped commercial game? Answer boolean.`,
    { schema: YN, label: `turing:${i}`, phase: 'Discrimination' }).then(v => v && { ...c, said: v.answer })))
const ok = dis.filter(Boolean)
const detection = ok.filter(c => c.said === c.real).length / ok.length
gates.push({ gate: 5, pass: detection <= 0.70, detection })

phase('Milestones')
const ms = await parallel(longs.flatMap(v => milestones.map((m, i) => () =>
  agent(`Watch ${v}. Is this milestone visibly reached: "${m}"? Boolean + timestamp in why.`,
    { schema: YN, label: `ms:${i}`, phase: 'Milestones' }).then(r => ({ video: v, m, hit: !!r?.answer })))))
gates.push({ gate: 6, pass: ms.every(x => x.hit), matrix: ms })

if (prev) {
  phase('Regression')
  const pairsN = Math.min(20, clips.length)
  const reg = await parallel(Array.from({ length: pairsN }, (_, i) => () =>
    agent(`Clip A: ${prev}/${i}.webp  Clip B: ${clips[i].path || clips[i]}. Which looks more like a real game? Answer boolean: true if B (new build) is at least as good.`,
      { schema: YN, label: `reg:${i}`, phase: 'Regression' })))
  const wins = reg.filter(Boolean).filter(r => r.answer).length
  gates.push({ gate: 7, pass: wins >= pairsN * 0.4, winsForNew: wins, pairs: pairsN })
} else { gates.push({ gate: 7, pass: true, note: 'no previous build' }) }

return { verdict: gates.every(g => g.pass) ? 'PASS' : 'FAIL', gates, mos, evidence: flat }
```

Post-run (main loop, not workflow): for every failed gate finding,
`ffmpeg -ss <timestamp> -i <clip> -frames:v 1 <keyframe.png>`, file the
bug, mark verdicts PROVISIONAL until golden-set calibration exists.
