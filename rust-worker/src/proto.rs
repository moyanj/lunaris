use anyhow::{Context, Result};
use prost::Message;

#[allow(unused)]
pub mod common {
    include!(concat!(env!("OUT_DIR"), "/lunaris.common.rs"));
}
#[allow(unused)]
pub mod worker {
    include!(concat!(env!("OUT_DIR"), "/lunaris.worker.rs"));
}
#[allow(unused)]
pub mod client {
    include!(concat!(env!("OUT_DIR"), "/lunaris.client.rs"));
}

use common::envelope::MessageType;

pub fn from_bytes(bytes: &[u8]) -> Result<(Vec<u8>, MessageType)> {
    let envelope = common::Envelope::decode(bytes).context("Failed to decode Envelope")?;
    let message_type = MessageType::try_from(envelope.r#type).context("Unknown message type")?;

    let payload = if envelope.compressed {
        zstd::decode_all(&envelope.payload[..]).context("Failed to decompress payload")?
    } else {
        envelope.payload
    };

    Ok((payload, message_type))
}

pub fn to_bytes(obj_buf: &Vec<u8>, message_type: MessageType) -> Result<Vec<u8>> {
    let compressed_payload: Vec<u8> = obj_buf.clone();
    /*
    zstd::encode_all(&mut compressed_payload, &obj_buf[..], 3)?;*/
    let envelope = common::Envelope {
        r#type: message_type as i32,
        payload: compressed_payload,
        compressed: false,
    };
    Ok(envelope.encode_to_vec())
}
