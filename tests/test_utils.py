"""Lunaris utils 模块的单元测试。"""

from lunaris.utils import IDGenerator, proto2bytes, bytes2proto
from lunaris.proto.worker_pb2 import NodeStatus


def test_id_generator_unique():
    """测试 Snowflake ID 生成器的唯一性。"""
    gen = IDGenerator(1)
    ids = {gen.get_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_id_generator_monotonic():
    """测试 Snowflake ID 单调递增。"""
    gen = IDGenerator(1)
    prev = int(gen.get_id())
    for _ in range(100):
        curr = int(gen.get_id())
        assert curr > prev
        prev = curr


def test_id_generator_worker_id_validation():
    """测试 Worker ID 范围校验。"""
    IDGenerator(0)
    IDGenerator(1023)
    try:
        IDGenerator(1024)
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_proto_roundtrip():
    """测试 proto 编解码往返。"""
    msg = NodeStatus()
    msg.worker_id = 42
    msg.running_tasks = 3
    msg.load = 0.75

    encoded = proto2bytes(msg, compress=False)
    decoded = bytes2proto(encoded)
    assert isinstance(decoded, NodeStatus)
    assert decoded.worker_id == 42
    assert decoded.running_tasks == 3


def test_proto_roundtrip_compressed():
    """测试 proto 压缩编解码往返。"""
    msg = NodeStatus()
    msg.worker_id = 42
    msg.running_tasks = 3
    msg.load = 0.75

    encoded = proto2bytes(msg, compress=True)
    decoded = bytes2proto(encoded)
    assert isinstance(decoded, NodeStatus)
    assert decoded.worker_id == 42
    assert decoded.running_tasks == 3
