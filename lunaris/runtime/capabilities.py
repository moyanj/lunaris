from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from wasmtime import FuncType, Linker, Store, ValType

CAPABILITY_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
MOCK_SIMD_CAPABILITY = "simd"
DEFAULT_PROVIDED_CAPABILITIES = (MOCK_SIMD_CAPABILITY,)


def normalize_host_capabilities(capabilities: Iterable[str] | None) -> list[str]:
    normalized: set[str] = set()
    for item in capabilities or []:
        if not item or item != item.strip() or not CAPABILITY_NAME_RE.fullmatch(item):
            raise ValueError(f"invalid host capability group: {item}")
        normalized.add(item)
    return sorted(normalized)


@dataclass(frozen=True)
class HostContext:
    enabled_capabilities: frozenset[str]

    def require(self, capability: str) -> None:
        if capability not in self.enabled_capabilities:
            raise RuntimeError(f"missing host capability group: {capability}")


class CapabilityRegistry:
    def register_all(
        self,
        linker: Linker,
        store: Store,
        host_context: HostContext,
        enabled_capabilities: Iterable[str],
    ) -> None:
        enabled = set(enabled_capabilities)
        if MOCK_SIMD_CAPABILITY in enabled:
            self._register_mock_simd(linker, store, host_context)

    def _register_mock_simd(
        self,
        linker: Linker,
        store: Store,
        host_context: HostContext,
    ) -> None:
        def simd_ping() -> int:
            host_context.require(MOCK_SIMD_CAPABILITY)
            return 1

        linker.define_func(
            "lunaris:simd",
            "ping",
            FuncType([], [ValType.i32()]),
            simd_ping,
        )


REGISTRY = CapabilityRegistry()
