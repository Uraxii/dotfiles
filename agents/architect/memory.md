# Architect — Memory

## Decisions & Notes

### 2026-03-12 — Practice projects design
Designed 4 games with escalating complexity. Established shared conventions (unidirectional data flow: state → update → render → DOM). Key architectural decisions:
- RPS: outcome lookup matrix over if-else (ADR-001)
- Tic-tac-toe: flat array for 3x3, minimax AI (ADR-002, ADR-003)
- Checkers: 2D array for 8x8 diagonal movement, upfront mandatory capture scan (ADR-004, ADR-005)
- Chess: clone-and-check for move legality, move history for en passant, modal promotion state (ADR-006, ADR-007, ADR-008)

Pattern: single-file HTML/JS with state/update/render separation works for all 4 games. The pattern scales well from trivial (RPS) to complex (Chess).
