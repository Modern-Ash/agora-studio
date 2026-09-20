"""Trusted local startup wiring for Agora Core flavor projection providers.

The browser never chooses or supplies a provider. The operator names a factory at process start;
Studio only hands the returned object to Agora Core's public read service.
"""

from __future__ import annotations

import re
from importlib import import_module

_SPEC = re.compile(
    r"(?P<module>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*):(?P<name>[A-Za-z_][A-Za-z0-9_]*)\Z"
)


class FlavorProjectorError(Exception):
    """A startup flavor-projector option is unusable."""


def load_flavor_projector(spec: str) -> object:
    match = _SPEC.fullmatch(spec)
    if match is None:
        raise FlavorProjectorError(f"flavor projector must be MODULE:FACTORY, got {spec!r}")
    try:
        factory = getattr(import_module(match.group("module")), match.group("name"))
    except (ImportError, AttributeError) as error:
        raise FlavorProjectorError(f"flavor projector {spec} cannot be imported") from error
    try:
        is_instance = not isinstance(factory, type) and hasattr(factory, "projection_schema")
        return factory if is_instance else factory()
    except Exception as error:
        raise FlavorProjectorError(f"flavor projector {spec} failed to initialize") from error
