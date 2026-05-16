"""Test comms/registry.py: R1, R2, R3."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from comms.registry import (
    CommsRegistry,
    UnknownProviderError,
    get_registry,
    resolve_provider_name,
)


def _make_registry_with_fake() -> CommsRegistry:
    reg = CommsRegistry()
    fake_provider = MagicMock()
    fake_provider.name = "slack"
    reg.register("slack", lambda: fake_provider)
    return reg


# --- R1: default slack when no toml ---


def test_default_slack_when_no_toml(tmp_path: Path) -> None:
    """R1: Missing [comms] section -> active_provider().name == 'slack'."""
    project = tmp_path / "project"
    project.mkdir()
    # No pipeline.toml exists.
    reg = _make_registry_with_fake()
    provider = reg.active_provider(project)
    assert provider.name == "slack"


def test_default_slack_when_comms_section_absent(tmp_path: Path) -> None:
    """Missing [comms].provider key -> default slack."""
    project = tmp_path / "project"
    pipeline_dir = project / ".pipeline"
    pipeline_dir.mkdir(parents=True)
    toml = pipeline_dir / "pipeline.toml"
    toml.write_bytes(b"[other]\nkey = \"value\"\n")
    name = resolve_provider_name(project)
    assert name == "slack"


# --- R2: unknown provider hard error ---


def test_unknown_provider_hard_error(tmp_path: Path) -> None:
    """R2: [comms].provider = 'discord' -> UnknownProviderError listing registered."""
    project = tmp_path / "project"
    pipeline_dir = project / ".pipeline"
    pipeline_dir.mkdir(parents=True)
    toml = pipeline_dir / "pipeline.toml"
    toml.write_bytes(b"[comms]\nprovider = \"discord\"\n")

    reg = _make_registry_with_fake()
    with pytest.raises(UnknownProviderError) as exc_info:
        reg.active_provider(project)
    msg = str(exc_info.value)
    assert "discord" in msg
    assert "slack" in msg


def test_unknown_provider_error_message_lists_registered() -> None:
    """UnknownProviderError includes list of registered providers."""
    reg = CommsRegistry()
    reg.register("slack", lambda: MagicMock())
    with pytest.raises(UnknownProviderError) as exc_info:
        reg.get("discord")
    assert "['slack']" in str(exc_info.value) or "slack" in str(exc_info.value)


# --- R3: env override ---


def test_env_override_wins_over_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R3: COMMS_PROVIDER env var wins over toml."""
    project = tmp_path / "project"
    pipeline_dir = project / ".pipeline"
    pipeline_dir.mkdir(parents=True)
    toml = pipeline_dir / "pipeline.toml"
    toml.write_bytes(b"[comms]\nprovider = \"slack\"\n")

    monkeypatch.setenv("COMMS_PROVIDER", "foo")
    name = resolve_provider_name(project)
    assert name == "foo"


def test_env_override_empty_falls_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty COMMS_PROVIDER falls through to toml."""
    project = tmp_path / "project"
    monkeypatch.setenv("COMMS_PROVIDER", "")
    name = resolve_provider_name(project)
    assert name == "slack"


def test_registry_idempotent_register() -> None:
    """Re-registering same name replaces factory + clears cached instance."""
    reg = CommsRegistry()
    p1 = MagicMock()
    p1.name = "slack"
    p2 = MagicMock()
    p2.name = "slack"
    reg.register("slack", lambda: p1)
    _ = reg.get("slack")  # prime cache
    reg.register("slack", lambda: p2)  # should clear cache
    assert reg.get("slack") is p2


def test_get_registry_returns_singleton() -> None:
    """get_registry() returns same instance on repeated calls."""
    import comms.registry as mod
    # Reset singleton.
    original = mod._REGISTRY
    mod._REGISTRY = None
    try:
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2
    finally:
        mod._REGISTRY = original


def test_get_registry_registers_slack_builtin() -> None:
    """get_registry() registers 'slack' as a builtin."""
    import comms.registry as mod
    original = mod._REGISTRY
    mod._REGISTRY = None
    try:
        reg = get_registry()
        assert "slack" in reg.names()
    finally:
        mod._REGISTRY = original
