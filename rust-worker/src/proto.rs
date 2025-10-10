use anyhow::{Context, Result, anyhow};
use prost::Message;
use zstd::stream;

pub mod common {
    include!(concat!(env!("OUT_DIR"), "/lunaris.common.rs"));
}
pub mod worker {
    include!(concat!(env!("OUT_DIR"), "/lunaris.worker.rs"));
}
pub mod client {
    include!(concat!(env!("OUT_DIR"), "/lunaris.client.rs"));
}

use common::envelope::MessageType;

pub fn from_bytes(bytes: &[u8]) -> Result<Box<dyn Message + 'static>> {
    let envelope = common::Envelope::decode(bytes).context("Failed to decode Envelope")?;
    let message_type = MessageType::try_from(envelope.r#type).context("Unknown message type")?;

    let payload = if envelope.compressed {
        stream::decode_all(&envelope.payload[..])?
    } else {
        envelope.payload
    };

    match message_type {
        MessageType::Task => Ok(Box::new(worker::Task::decode(&payload[..])?)),
        MessageType::TaskResult => Ok(Box::new(common::TaskResult::decode(&payload[..])?)),
        MessageType::ControlCommand => Ok(Box::new(worker::ControlCommand::decode(&payload[..])?)),
        MessageType::NodeStatus => Ok(Box::new(worker::NodeStatus::decode(&payload[..])?)),
        MessageType::NodeRegistration => {
            Ok(Box::new(worker::NodeRegistration::decode(&payload[..])?))
        }
        MessageType::NodeRegistrationReply => Ok(Box::new(worker::NodeRegistrationReply::decode(
            &payload[..],
        )?)),
        MessageType::UnregisterNode => Ok(Box::new(worker::UnregisterNode::decode(&payload[..])?)),
        _ => Err(anyhow!("Unknown message type")),
    }
}

pub fn to_bytes(obj_buf: &Vec<u8>, message_type: MessageType) -> Result<Vec<u8>> {
    let compressed_payload = stream::encode_all(&obj_buf[..], 7)?;
    let envelope = common::Envelope {
        r#type: message_type as i32,
        payload: compressed_payload,
        compressed: true,
    };
    Ok(envelope.encode_to_vec())
}
