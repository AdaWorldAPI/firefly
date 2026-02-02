//! Firefly Packet: mRNA transport for distributed graph execution.
//!
//! Total: ~1.5KB
//! - Routing header: 80 bytes
//! - Resonance payload: 1250 bytes
//! - Execution context: variable (JSON)

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use chrono::{DateTime, Utc};

use crate::{HammingVector, PACKED, FireflyError, Result};

/// Packet flags
pub mod flags {
    pub const ASYNC: u16 = 0x01;     // Don't wait for response
    pub const SYNC: u16 = 0x02;      // Wait for response
    pub const BROADCAST: u16 = 0x04; // Send to all matching nodes
    pub const TRACE: u16 = 0x08;     // Record execution trace
    pub const PRIORITY: u16 = 0x10;  // High priority
}

/// Header size in bytes
pub const HEADER_SIZE: usize = 80;

/// mRNA packet for distributed graph execution.
///
/// Like a ribosome carrying instructions through the cell,
/// packets carry execution context through the graph.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FireflyPacket {
    /// Source node address (32 bytes, SHA256 of node ID)
    #[serde(with = "hex_bytes")]
    pub source_node: [u8; 32],

    /// Target node address (32 bytes, SHA256 of node ID)
    #[serde(with = "hex_bytes")]
    pub target_node: [u8; 32],

    /// Time-to-live: max hops before death
    pub ttl: u8,

    /// Priority (0-10, higher = more urgent)
    pub priority: u8,

    /// Flags bitfield
    pub flags: u16,

    /// Sequence number for ordering/dedup
    pub sequence: u32,

    /// 10K-bit resonance payload
    #[serde(with = "hex_resonance")]
    pub resonance: HammingVector,

    /// DTO identifier
    pub dto_id: String,

    /// Operation: CREATE | UPDATE | DESTROY | QUERY
    pub operation: String,

    /// Input data context
    pub input_data: HashMap<String, serde_json::Value>,

    /// Trace of node IDs visited
    pub trace: Vec<String>,

    /// Creation timestamp
    pub created_at: DateTime<Utc>,
}

impl Default for FireflyPacket {
    fn default() -> Self {
        Self {
            source_node: [0u8; 32],
            target_node: [0u8; 32],
            ttl: 8,
            priority: 5,
            flags: flags::TRACE,
            sequence: 0,
            resonance: HammingVector::new(),
            dto_id: String::new(),
            operation: String::new(),
            input_data: HashMap::new(),
            trace: Vec::new(),
            created_at: Utc::now(),
        }
    }
}

impl FireflyPacket {
    /// Create a new packet with defaults.
    pub fn new() -> Self {
        Self::default()
    }

    /// Create packet targeting a specific node by ID.
    pub fn for_node(node_id: &str) -> Self {
        let target = Sha256::digest(node_id.as_bytes());
        let mut packet = Self::default();
        packet.target_node.copy_from_slice(&target);
        packet
    }

    /// Create packet for DTO operation.
    pub fn for_dto(dto_id: &str, operation: &str, input_data: HashMap<String, serde_json::Value>) -> Self {
        let entry_id = format!("{}_{}_entry", dto_id, operation);
        let target = Sha256::digest(entry_id.as_bytes());

        let mut packet = Self::default();
        packet.target_node.copy_from_slice(&target);
        packet.dto_id = dto_id.to_string();
        packet.operation = operation.to_string();
        packet.input_data = input_data;
        packet.flags = flags::TRACE | flags::SYNC;
        packet
    }

    /// Pack routing header to exactly 80 bytes.
    ///
    /// Format (little-endian):
    /// - source_node: 32 bytes
    /// - target_node: 32 bytes
    /// - ttl: 1 byte
    /// - priority: 1 byte
    /// - flags: 2 bytes
    /// - sequence: 4 bytes
    /// - checksum: 4 bytes (CRC32 of preceding 72 bytes)
    /// - reserved: 4 bytes
    pub fn pack_header(&self) -> [u8; HEADER_SIZE] {
        let mut header = [0u8; HEADER_SIZE];

        // Source node (32 bytes)
        header[0..32].copy_from_slice(&self.source_node);

        // Target node (32 bytes)
        header[32..64].copy_from_slice(&self.target_node);

        // Control fields
        header[64] = self.ttl;
        header[65] = self.priority;
        header[66..68].copy_from_slice(&self.flags.to_le_bytes());
        header[68..72].copy_from_slice(&self.sequence.to_le_bytes());

        // CRC32 checksum of first 72 bytes
        let checksum = crc32fast::hash(&header[0..72]);
        header[72..76].copy_from_slice(&checksum.to_le_bytes());

        // Reserved (4 bytes padding)
        // Already zero

        header
    }

    /// Unpack routing header from 80 bytes.
    pub fn unpack_header(data: &[u8]) -> Result<UnpackedHeader> {
        if data.len() < HEADER_SIZE {
            return Err(FireflyError::InvalidLength(format!(
                "Header requires {} bytes, got {}",
                HEADER_SIZE,
                data.len()
            )));
        }

        let mut source_node = [0u8; 32];
        let mut target_node = [0u8; 32];
        source_node.copy_from_slice(&data[0..32]);
        target_node.copy_from_slice(&data[32..64]);

        let ttl = data[64];
        let priority = data[65];
        let flags = u16::from_le_bytes([data[66], data[67]]);
        let sequence = u32::from_le_bytes([data[68], data[69], data[70], data[71]]);
        let stored_checksum = u32::from_le_bytes([data[72], data[73], data[74], data[75]]);

        // Verify checksum
        let computed_checksum = crc32fast::hash(&data[0..72]);
        if stored_checksum != computed_checksum {
            return Err(FireflyError::ChecksumMismatch {
                expected: stored_checksum,
                actual: computed_checksum,
            });
        }

        Ok(UnpackedHeader {
            source_node,
            target_node,
            ttl,
            priority,
            flags,
            sequence,
            checksum: stored_checksum,
        })
    }

    /// Redis stream key for routing.
    pub fn route_key(&self) -> String {
        let target_hex = hex::encode(&self.target_node[0..8]);
        format!("firefly:route:{}", target_hex)
    }

    /// Redis stream key for specific node.
    pub fn node_key(&self) -> String {
        let target_hex = hex::encode(&self.target_node[0..16]);
        format!("firefly:node:{}", target_hex)
    }

    /// Create new packet for next hop.
    ///
    /// Decrements TTL, updates source, adds to trace.
    pub fn hop(&self, current_node_id: &str, next_node_id: &str) -> Result<Self> {
        if self.ttl == 0 {
            return Err(FireflyError::TtlExpired);
        }

        let source = Sha256::digest(current_node_id.as_bytes());
        let target = Sha256::digest(next_node_id.as_bytes());

        let mut trace = self.trace.clone();
        trace.push(current_node_id.to_string());

        let mut packet = self.clone();
        packet.source_node.copy_from_slice(&source);
        packet.target_node.copy_from_slice(&target);
        packet.ttl = self.ttl - 1;
        packet.sequence = self.sequence + 1;
        packet.trace = trace;

        Ok(packet)
    }

    /// Serialize to JSON.
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string(self).map_err(|e| FireflyError::SerializationError(e.to_string()))
    }

    /// Deserialize from JSON.
    pub fn from_json(json: &str) -> Result<Self> {
        serde_json::from_str(json).map_err(|e| FireflyError::SerializationError(e.to_string()))
    }

    /// Base size in bytes (header + resonance).
    pub fn base_size(&self) -> usize {
        HEADER_SIZE + PACKED
    }

    /// Convert to string map for transport.
    pub fn to_string_map(&self) -> HashMap<String, String> {
        let mut map = HashMap::new();
        map.insert("source_node".to_string(), hex::encode(&self.source_node));
        map.insert("target_node".to_string(), hex::encode(&self.target_node));
        map.insert("ttl".to_string(), self.ttl.to_string());
        map.insert("priority".to_string(), self.priority.to_string());
        map.insert("flags".to_string(), self.flags.to_string());
        map.insert("sequence".to_string(), self.sequence.to_string());
        map.insert("resonance".to_string(), self.resonance.to_hex());
        map.insert("dto_id".to_string(), self.dto_id.clone());
        map.insert("operation".to_string(), self.operation.clone());
        map.insert("input_data".to_string(), serde_json::to_string(&self.input_data).unwrap_or_default());
        map.insert("trace".to_string(), serde_json::to_string(&self.trace).unwrap_or_default());
        map.insert("created_at".to_string(), self.created_at.to_rfc3339());
        map
    }
}

/// Unpacked header fields.
#[derive(Debug, Clone)]
pub struct UnpackedHeader {
    pub source_node: [u8; 32],
    pub target_node: [u8; 32],
    pub ttl: u8,
    pub priority: u8,
    pub flags: u16,
    pub sequence: u32,
    pub checksum: u32,
}

/// Serde helper for 32-byte arrays as hex.
mod hex_bytes {
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(bytes: &[u8; 32], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&hex::encode(bytes))
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<[u8; 32], D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        let bytes = hex::decode(&s).map_err(serde::de::Error::custom)?;
        if bytes.len() != 32 {
            return Err(serde::de::Error::custom("Expected 32 bytes"));
        }
        let mut arr = [0u8; 32];
        arr.copy_from_slice(&bytes);
        Ok(arr)
    }
}

/// Serde helper for HammingVector as hex.
mod hex_resonance {
    use super::HammingVector;
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(v: &HammingVector, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&v.to_hex())
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<HammingVector, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        HammingVector::from_hex(&s).map_err(serde::de::Error::custom)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default() {
        let packet = FireflyPacket::new();
        assert_eq!(packet.ttl, 8);
        assert_eq!(packet.priority, 5);
    }

    #[test]
    fn test_for_node() {
        let packet = FireflyPacket::for_node("test_node");
        assert_ne!(packet.target_node, [0u8; 32]);
    }

    #[test]
    fn test_pack_unpack_header() {
        let packet = FireflyPacket::for_node("test");
        let header = packet.pack_header();
        assert_eq!(header.len(), HEADER_SIZE);

        let unpacked = FireflyPacket::unpack_header(&header).unwrap();
        assert_eq!(unpacked.ttl, packet.ttl);
        assert_eq!(unpacked.priority, packet.priority);
        assert_eq!(unpacked.target_node, packet.target_node);
    }

    #[test]
    fn test_checksum_validation() {
        let packet = FireflyPacket::for_node("test");
        let mut header = packet.pack_header();

        // Corrupt the header
        header[0] ^= 0xFF;

        // Should fail checksum
        assert!(FireflyPacket::unpack_header(&header).is_err());
    }

    #[test]
    fn test_hop() {
        let packet = FireflyPacket::for_node("start");
        let hopped = packet.hop("start", "next").unwrap();

        assert_eq!(hopped.ttl, packet.ttl - 1);
        assert_eq!(hopped.sequence, packet.sequence + 1);
        assert_eq!(hopped.trace, vec!["start".to_string()]);
    }

    #[test]
    fn test_ttl_expired() {
        let mut packet = FireflyPacket::new();
        packet.ttl = 0;

        assert!(packet.hop("a", "b").is_err());
    }

    #[test]
    fn test_json_roundtrip() {
        let packet = FireflyPacket::for_dto("users", "create", HashMap::new());
        let json = packet.to_json().unwrap();
        let restored = FireflyPacket::from_json(&json).unwrap();

        assert_eq!(packet.dto_id, restored.dto_id);
        assert_eq!(packet.operation, restored.operation);
        assert_eq!(packet.target_node, restored.target_node);
    }
}
