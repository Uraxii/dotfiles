# Python Rules

- Type hints: all fn sigs. `-> None` explicit. No untyped public API.
- No `type: ignore` w/o inline comment why.
- `pathlib` over `os.path`. Always.
- No mutable default args (`def f(x=[])` forbidden).
- Context mgrs for all resources (files, locks, connections).
- `dataclass` or `NamedTuple` over raw dict for structured data.
- f-strings over `.format()` over `%`.
- No star imports (`from x import *`).
- `__all__` in every public module.
- Comprehensions ≤1 nested. 2+ nested → explicit loop.
- `logging` over `print` in library/app code.
- `pytest` conventions: `test_` prefix, fixtures over setUp.
- No bare `assert` in prod code (stripped w/ `-O`). Use `raise`.
- `collections.abc` for type annotations, not `typing` (3.9+).
- Imports: stdlib → third-party → local, separated by blank line.
