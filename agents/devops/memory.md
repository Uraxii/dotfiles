# DevOps — Memory

## Lessons

### Node.js 24 TypeScript auto-detection breaks data file scripts (2026-03-12)
Node.js 24 implicitly enables TypeScript parsing, which causes `readFileSync` on large JS data files to fail with cryptic `<anonymous_script>:1` errors — the file content is treated as code. Workaround: use `vm.runInNewContext()` with `const` replaced by `var`. This affects any script that reads a large `.js` file containing a variable assignment (e.g., `const FFXIV_ITEMS = {...};`). `.cjs`, `.mjs`, `--input-type=commonjs`, `--no-experimental-strip-types`, and stdin piping all failed. Only `vm` worked.

### Session-start environment checks prevent mid-session blocks (2026-03-12)
The Node.js 24 issue consumed significant implementation time because it was only discovered when trying to filter data mid-session. A 30-second environment check at session start (run a small test script that reads/writes a data file) would have surfaced it immediately and allowed a workaround to be established before implementation began.

### winget installs may not update PATH in current shell (2026-03-12)
Installing Python via `winget install Python.Python.3.12` succeeded but the binary wasn't findable in the current bash session. New installs may require a shell restart or manual PATH addition.
