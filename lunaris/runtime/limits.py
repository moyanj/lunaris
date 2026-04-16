from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


def _normalize_limit(value: Any) -> int:
    if value is None:
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


@dataclass
class ExecutionLimits:
    max_fuel: int = 0
    max_memory_bytes: int = 0
    max_module_bytes: int = 0

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]]) -> "ExecutionLimits":
        if not data:
            return cls()
        return cls(
            max_fuel=_normalize_limit(data.get("max_fuel")),
            max_memory_bytes=_normalize_limit(data.get("max_memory_bytes")),
            max_module_bytes=_normalize_limit(data.get("max_module_bytes")),
        )

    @classmethod
    def from_proto(cls, proto: Any) -> "ExecutionLimits":
        if proto is None:
            return cls()
        return cls(
            max_fuel=_normalize_limit(getattr(proto, "max_fuel", 0)),
            max_memory_bytes=_normalize_limit(getattr(proto, "max_memory_bytes", 0)),
            max_module_bytes=_normalize_limit(getattr(proto, "max_module_bytes", 0)),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "max_fuel": self.max_fuel,
            "max_memory_bytes": self.max_memory_bytes,
            "max_module_bytes": self.max_module_bytes,
        }

    def clamp(
        self,
        defaults: Optional["ExecutionLimits"] = None,
        maximums: Optional["ExecutionLimits"] = None,
    ) -> "ExecutionLimits":
        defaults = defaults or ExecutionLimits()
        maximums = maximums or ExecutionLimits()
        return ExecutionLimits(
            max_fuel=_resolve_limit(
                self.max_fuel,
                defaults.max_fuel,
                maximums.max_fuel,
            ),
            max_memory_bytes=_resolve_limit(
                self.max_memory_bytes,
                defaults.max_memory_bytes,
                maximums.max_memory_bytes,
            ),
            max_module_bytes=_resolve_limit(
                self.max_module_bytes,
                defaults.max_module_bytes,
                maximums.max_module_bytes,
            ),
        )


def _resolve_limit(requested: int, default: int, maximum: int) -> int:
    effective = requested if requested > 0 else default
    if maximum > 0 and (effective <= 0 or effective > maximum):
        return maximum
    return max(effective, 0)
