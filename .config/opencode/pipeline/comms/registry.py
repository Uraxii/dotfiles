"""Registry of available comms providers + active-provider resolver."""
from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path
from typing import Callable

from .provider import CommsProvider

__all__ = [
    "CommsRegistry",
    "UnknownProviderError",
    "get_registry",
    "resolve_provider_name",
]

log = logging.getLogger(__name__)


class UnknownProviderError(Exception):
    """Raised when [comms].provider names a key not in the registry."""


# Factory function: zero-arg, returns a fully-constructed CommsProvider.
# Slack factory loads env file + reads tokens internally.
ProviderFactory = Callable[[], CommsProvider]


class CommsRegistry:
    """Process-global registry. Construct once via `get_registry()`."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}
        self._instances: dict[str, CommsProvider] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        """Idempotent: re-register same name replaces factory + clears cache."""
        self._factories[name] = factory
        self._instances.pop(name, None)

    def names(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._factories)

    def get(self, name: str) -> CommsProvider:
        """Return provider instance by name. Raises UnknownProviderError on miss."""
        if name not in self._factories:
            raise UnknownProviderError(
                f"Unknown comms provider {name!r}. "
                f"Registered providers: {self.names()!r}. "
                f"Set [comms].provider in <project>/.pipeline/pipeline.toml "
                f"or override via COMMS_PROVIDER env var."
            )
        if name not in self._instances:
            self._instances[name] = self._factories[name]()
        return self._instances[name]

    def active_provider(self, project_path: Path) -> CommsProvider:
        """Resolve active provider from config + env. See resolve_provider_name."""
        name = resolve_provider_name(project_path)
        return self.get(name)


_REGISTRY: CommsRegistry | None = None


def get_registry() -> CommsRegistry:
    """Lazy global. First call triggers builtin registrations."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CommsRegistry()
        _register_builtins(_REGISTRY)
    return _REGISTRY


def _register_builtins(reg: CommsRegistry) -> None:
    # Import inline to avoid forcing slack-bolt dependency on registry import.
    from .slack.provider import build_slack_provider  # noqa: PLC0415
    reg.register("slack", build_slack_provider)


def resolve_provider_name(project_path: Path) -> str:
    """Resolution order (first match wins):
      1. env COMMS_PROVIDER (testing/ops override; footgun acknowledged)
      2. <project>/.pipeline/pipeline.toml [comms].provider
      3. default "slack"

    On env override active, log a single INFO line so operators see it
    in router.log.
    """
    override = os.environ.get("COMMS_PROVIDER", "").strip()
    if override:
        log.info("comms: env override active provider=%s", override)
        return override
    toml_path = project_path / ".pipeline" / "pipeline.toml"
    if toml_path.is_file():
        try:
            with toml_path.open("rb") as fh:
                cfg = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError):
            return "slack"
        comms = cfg.get("comms", {})
        name = comms.get("provider")
        if isinstance(name, str) and name:
            return name
    return "slack"
