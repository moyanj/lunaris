"""
WASM 执行资源限制模块

定义和管理 WASM 执行的资源限制，包括燃料（fuel）、内存（memory）和模块大小（module）。

核心概念：
    - 燃料（fuel）：限制 WASM 指令执行数量，防止无限循环
    - 内存（memory）：限制 WASM 线性内存大小，防止内存溢出
    - 模块大小（module）：限制 WASM 模块字节码大小，防止加载过大模块

限制语义：
    - 0 表示无限制（不启用该限制）
    - 正整数表示具体限制值
    - 负数或无效值会被规范化为 0

三层解析机制：
    用户请求 → 默认值 → 最大值
    1. 如果用户请求 > 0，使用用户请求
    2. 如果用户请求 ≤ 0，使用默认值
    3. 如果最大值 > 0 且结果 > 最大值，使用最大值
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


def _normalize_limit(value: Any) -> int:
    """规范化限制值

    将任意输入值转换为非负整数。用于处理来自不同来源（配置、Proto、API）
    的限制值，确保一致性。

    Args:
        value: 输入值，可以是 None、数字、字符串等

    Returns:
        规范化后的非负整数
            - None → 0
            - 无法解析 → 0
            - 负数 → 0
            - 正数 → 原值

    Examples:
        >>> _normalize_limit(None)
        0
        >>> _normalize_limit("100")
        100
        >>> _normalize_limit(-5)
        0
        >>> _normalize_limit("invalid")
        0
    """
    if value is None:
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    # 确保非负
    return max(parsed, 0)


@dataclass
class ExecutionLimits:
    """WASM 执行资源限制配置

    定义 WASM 执行的三重资源限制：燃料、内存、模块大小。
    所有限制值为 0 表示无限制（不启用该限制）。

    Attributes:
        max_fuel: 最大燃料消耗（WASM 指令数量），0 表示无限制
        max_memory_bytes: 最大线性内存大小（字节），0 表示无限制
        max_module_bytes: 最大 WASM 模块大小（字节），0 表示无限制

    Examples:
        # 无限制
        limits = ExecutionLimits()

        # 设置具体限制
        limits = ExecutionLimits(
            max_fuel=1_000_000,
            max_memory_bytes=64 * 1024 * 1024,  # 64MB
            max_module_bytes=1024 * 1024,  # 1MB
        )
    """
    max_fuel: int = 0
    max_memory_bytes: int = 0
    max_module_bytes: int = 0

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]]) -> "ExecutionLimits":
        """从字典创建 ExecutionLimits

        用于从 JSON 配置或环境变量字典创建限制对象。

        Args:
            data: 包含限制值的字典，键为 max_fuel、max_memory_bytes、max_module_bytes

        Returns:
            ExecutionLimits 实例，无效值会被规范化为 0

        Examples:
            >>> ExecutionLimits.from_mapping({"max_fuel": 1000})
            ExecutionLimits(max_fuel=1000, max_memory_bytes=0, max_module_bytes=0)
            >>> ExecutionLimits.from_mapping(None)
            ExecutionLimits(max_fuel=0, max_memory_bytes=0, max_module_bytes=0)
        """
        if not data:
            return cls()
        return cls(
            max_fuel=_normalize_limit(data.get("max_fuel")),
            max_memory_bytes=_normalize_limit(data.get("max_memory_bytes")),
            max_module_bytes=_normalize_limit(data.get("max_module_bytes")),
        )

    @classmethod
    def from_proto(cls, proto: Any) -> "ExecutionLimits":
        """从 Protobuf 消息创建 ExecutionLimits

        用于从 Proto 消息解析限制对象，支持 Protobuf 的 ExecutionLimits 消息。

        Args:
            proto: Protobuf 消息对象，需要有 max_fuel、max_memory_bytes、max_module_bytes 属性

        Returns:
            ExecutionLimits 实例，无效值会被规范化为 0

        Examples:
            >>> from lunaris.proto.common_pb2 import ExecutionLimits as ProtoLimits
            >>> proto = ProtoLimits(max_fuel=1000)
            >>> ExecutionLimits.from_proto(proto)
            ExecutionLimits(max_fuel=1000, max_memory_bytes=0, max_module_bytes=0)
        """
        if proto is None:
            return cls()
        return cls(
            max_fuel=_normalize_limit(getattr(proto, "max_fuel", 0)),
            max_memory_bytes=_normalize_limit(getattr(proto, "max_memory_bytes", 0)),
            max_module_bytes=_normalize_limit(getattr(proto, "max_module_bytes", 0)),
        )

    def to_dict(self) -> dict[str, int]:
        """转换为字典格式

        Returns:
            包含所有限制值的字典

        Examples:
            >>> limits = ExecutionLimits(max_fuel=1000)
            >>> limits.to_dict()
            {'max_fuel': 1000, 'max_memory_bytes': 0, 'max_module_bytes': 0}
        """
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
        """钳制资源限制

        使用三层解析机制钳制限制值：
        用户请求 → 默认值 → 最大值

        Args:
            defaults: 默认限制值，当用户请求 ≤ 0 时使用
            maximums: 最大限制值，用于钳制结果（安全边界）

        Returns:
            钳制后的 ExecutionLimits 实例

        Examples:
            >>> user_limits = ExecutionLimits(max_fuel=0)  # 用户未设置
            >>> defaults = ExecutionLimits(max_fuel=1000)  # 默认值
            >>> maximums = ExecutionLimits(max_fuel=10000)  # 最大值
            >>> user_limits.clamp(defaults, maximums)
            ExecutionLimits(max_fuel=1000, max_memory_bytes=0, max_module_bytes=0)
        """
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
    """解析单个限制值

    三层解析机制：
        1. 如果 requested > 0，使用 requested
        2. 如果 requested ≤ 0，使用 default
        3. 如果 maximum > 0 且结果 > maximum，使用 maximum

    Args:
        requested: 用户请求的限制值
        default: 默认限制值
        maximum: 最大限制值（安全边界）

    Returns:
        解析后的限制值，始终 ≥ 0

    Examples:
        >>> _resolve_limit(100, 200, 500)  # 用户请求 100
        100
        >>> _resolve_limit(0, 200, 500)    # 用户未设置，使用默认 200
        200
        >>> _resolve_limit(600, 200, 500)  # 用户请求 600，超过最大值 500
        500
    """
    # 第一层：使用用户请求或默认值
    effective = requested if requested > 0 else default
    # 第二层：钳制到最大值
    if maximum > 0 and (effective <= 0 or effective > maximum):
        return maximum
    # 第三层：确保非负
    return max(effective, 0)
