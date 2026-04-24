/**
 * Protobuf 消息处理模块
 *
 * 提供 Protobuf 消息的序列化和反序列化功能。
 * 使用 zstd 压缩算法优化传输效率。
 *
 * 主要功能：
 *   - from_bytes: 从字节反序列化消息
 *   - to_bytes: 将消息序列化为字节
 *
 * 消息格式：
 *   - Envelope: 消息信封，包含类型、压缩标志和载荷
 *   - 支持 zstd 压缩（当前禁用）
 *
 * 模块导出：
 *   - common: 通用消息类型
 *   - worker: Worker 相关消息
 *   - client: 客户端相关消息
 */
use anyhow::{Context, Result};
use prost::Message;

/// 通用消息类型模块
#[allow(unused)]
pub mod common {
    include!(concat!(env!("OUT_DIR"), "/lunaris.common.rs"));
}

/// Worker 消息类型模块
#[allow(unused)]
pub mod worker {
    include!(concat!(env!("OUT_DIR"), "/lunaris.worker.rs"));
}

/// 客户端消息类型模块
#[allow(unused)]
pub mod client {
    include!(concat!(env!("OUT_DIR"), "/lunaris.client.rs"));
}

use common::envelope::MessageType;

/// 从字节反序列化消息
///
/// 解析 Envelope，提取消息类型和载荷。
/// 如果启用了压缩，会自动解压缩。
///
/// Args:
///   - bytes: 序列化的字节数据
///
/// Returns:
///   - (payload, message_type): 载荷和消息类型的元组
///
/// Raises:
///   - 解码失败或消息类型未知时返回错误
pub fn from_bytes(bytes: &[u8]) -> Result<(Vec<u8>, MessageType)> {
    let envelope = common::Envelope::decode(bytes).context("Failed to decode Envelope")?;
    let message_type = MessageType::try_from(envelope.r#type).context("Unknown message type")?;

    // 解压缩（如果启用）
    let payload = if envelope.compressed {
        #[cfg(feature = "zstd")]
        {
            zstd::decode_all(&envelope.payload[..]).context("Failed to decompress payload")?
        }
        #[cfg(not(feature = "zstd"))]
        {
            anyhow::bail!("Received compressed message but zstd feature is disabled");
        }
    } else {
        envelope.payload
    };

    Ok((payload, message_type))
}

/// 将消息序列化为字节
///
/// 将消息载荷封装到 Envelope 中并序列化。
/// 当 compress=true 且 zstd feature 启用时使用 zstd 压缩。
///
/// Args:
///   - obj_buf: 消息载荷的字节数据
///   - message_type: 消息类型
///   - compress: 是否启用压缩
///
/// Returns:
///   - 序列化的字节数据
pub fn to_bytes(obj_buf: &Vec<u8>, message_type: MessageType, compress: bool) -> Result<Vec<u8>> {
    #[cfg(feature = "zstd")]
    let (compressed_payload, is_compressed) = if compress {
        let compressed = zstd::encode_all(&obj_buf[..], 3).context("Failed to compress payload")?;
        (compressed, true)
    } else {
        (obj_buf.clone(), false)
    };

    #[cfg(not(feature = "zstd"))]
    let (compressed_payload, is_compressed) = (obj_buf.clone(), false);

    let envelope = common::Envelope {
        r#type: message_type as i32,
        payload: compressed_payload,
        compressed: is_compressed,
    };
    Ok(envelope.encode_to_vec())
}
