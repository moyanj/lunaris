"""
宿主能力（Host Capabilities）注册模块

定义和管理 WASM 模块可访问的宿主功能。宿主能力是可扩展的安全边界，
允许 WASM 模块调用特定的宿主功能，同时保持沙箱隔离。

主要组件：
    - normalize_host_capabilities: 规范化能力名称列表
    - HostContext: 宿主上下文，用于检查能力是否启用
    - CapabilityRegistry: 能力注册表，管理所有可用能力

能力命名规范：
    - 必须以小写字母开头
    - 只能包含小写字母、数字、连字符、下划线
    - 长度 1-64 字符
    - 示例: "simd", "network", "filesystem"

当前实现的能力：
    - simd: 模拟 SIMD 支持（用于测试）

扩展新能力：
    1. 定义能力常量（如 MOCK_SIMD_CAPABILITY）
    2. 在 CapabilityRegistry 中添加注册方法
    3. 在 register_all 中调用注册方法
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from wasmtime import FuncType, Linker, Store, ValType

# 能力名称正则表达式
# 格式：以小写字母开头，包含小写字母、数字、连字符、下划线，长度 1-64
CAPABILITY_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

# 模拟 SIMD 能力名称（用于测试）
MOCK_SIMD_CAPABILITY = "simd"

# 默认启用的能力列表
DEFAULT_PROVIDED_CAPABILITIES = (MOCK_SIMD_CAPABILITY,)


def normalize_host_capabilities(capabilities: Iterable[str] | None) -> list[str]:
    """规范化宿主能力列表

    验证并规范化能力名称，确保符合命名规范。
    去重后按字母顺序排序返回。

    Args:
        capabilities: 能力名称迭代器，可以是 None

    Returns:
        规范化后的能力名称列表（去重、排序）

    Raises:
        ValueError: 能力名称不符合命名规范

    Examples:
        >>> normalize_host_capabilities(["simd", "network"])
        ['network', 'simd']
        >>> normalize_host_capabilities(None)
        []
        >>> normalize_host_capabilities(["invalid capability"])
        ValueError: invalid host capability group: invalid capability
    """
    normalized: set[str] = set()
    for item in capabilities or []:
        # 验证能力名称格式
        if not item or item != item.strip() or not CAPABILITY_NAME_RE.fullmatch(item):
            raise ValueError(f"invalid host capability group: {item}")
        normalized.add(item)
    # 返回排序后的列表（确保一致性）
    return sorted(normalized)


@dataclass(frozen=True)
class HostContext:
    """宿主上下文

    包含当前启用的能力集合，用于在运行时检查能力是否可用。

    Attributes:
        enabled_capabilities: 已启用的能力集合（frozenset）

    Examples:
        >>> ctx = HostContext(frozenset(["simd"]))
        >>> ctx.require("simd")  # 成功
        >>> ctx.require("network")  # 抛出 RuntimeError
    """
    enabled_capabilities: frozenset[str]

    def require(self, capability: str) -> None:
        """检查能力是否启用

        在调用宿主功能前检查所需能力是否已启用。
        如果能力未启用，抛出 RuntimeError。

        Args:
            capability: 需要检查的能力名称

        Raises:
            RuntimeError: 能力未启用

        Examples:
            >>> ctx = HostContext(frozenset(["simd"]))
            >>> ctx.require("simd")  # 成功
            >>> ctx.require("network")  # RuntimeError: missing host capability group: network
        """
        if capability not in self.enabled_capabilities:
            raise RuntimeError(f"missing host capability group: {capability}")


class CapabilityRegistry:
    """宿主能力注册表

    管理所有可用的宿主能力，负责将能力函数注册到 WASM Linker。
    通过 register_all 方法统一注册所有启用的能力。

    扩展新能力的步骤：
        1. 在模块级别定义能力常量（如 MOCK_SIMD_CAPABILITY）
        2. 在 CapabilityRegistry 中添加 _register_xxx 方法
        3. 在 register_all 中添加对应的能力检查和注册调用

    Examples:
        >>> registry = CapabilityRegistry()
        >>> registry.register_all(linker, store, host_context, ["simd"])
    """

    def register_all(
        self,
        linker: Linker,
        store: Store,
        host_context: HostContext,
        enabled_capabilities: Iterable[str],
    ) -> None:
        """注册所有启用的能力

        根据启用的能力列表，调用相应的注册方法将宿主函数注册到 Linker。

        Args:
            linker: WASM Linker，用于注册宿主函数
            store: WASM Store，用于创建函数实例
            host_context: 宿主上下文，用于能力检查
            enabled_capabilities: 启用的能力名称列表

        Note:
            - 只注册在 enabled_capabilities 中的能力
            - 未知的能力会被忽略（不报错）
        """
        enabled = set(enabled_capabilities)
        # 注册模拟 SIMD 能力（如果启用）
        if MOCK_SIMD_CAPABILITY in enabled:
            self._register_mock_simd(linker, store, host_context)

    def _register_mock_simd(
        self,
        linker: Linker,
        store: Store,
        host_context: HostContext,
    ) -> None:
        """注册模拟 SIMD 能力

        注册 lunaris:simd/ping 函数，用于测试宿主能力系统。
        函数返回 1 表示 SIMD 能力可用。

        Args:
            linker: WASM Linker
            store: WASM Store
            host_context: 宿主上下文

        Note:
            - 这是模拟实现，实际不提供 SIMD 指令
            - 仅用于测试能力和权限系统
        """

        def simd_ping() -> int:
            """SIMD ping 函数

            检查 SIMD 能力是否启用，返回 1 表示可用。
            如果能力未启用，抛出 RuntimeError。
            """
            host_context.require(MOCK_SIMD_CAPABILITY)
            return 1

        # 注册到 lunaris:simd 模块的 ping 函数
        linker.define_func(
            "lunaris:simd",
            "ping",
            FuncType([], [ValType.i32()]),
            simd_ping,
        )


# 全局能力注册表实例
REGISTRY = CapabilityRegistry()
