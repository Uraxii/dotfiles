#!/usr/bin/env python3
"""Compatibility shim for the renamed artifact-serve entrypoint."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

__all__ = ["build_parser", "db_connect", "main"]

_TARGET = Path(__file__).with_name("artifact-serve.py")
_SPEC = importlib.util.spec_from_file_location("artifact_serve", _TARGET)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"could not load {_TARGET}")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
MODULE = _MODULE
build_parser = MODULE.build_parser
db_connect = MODULE.db_connect
main = MODULE.main

if __name__ == "__main__":
    raise SystemExit(int(main()))
