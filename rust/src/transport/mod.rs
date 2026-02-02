//! Transport Layer: Queue management for distributed graph execution.
//!
//! Provides abstractions for:
//! - Execution request queuing
//! - Per-node work distribution
//! - Result collection
//! - Dead letter handling
//!
//! Stream topology:
//! - `firefly:execute:{dto_id}` → Incoming execution requests
//! - `firefly:node:{node_hash}` → Per-node work queue
//! - `firefly:results:{exec_id}` → Execution results
//! - `firefly:dead-letter` → Failed executions

use std::collections::HashMap;
use std::time::Duration;

use crate::{Result, FireflyError};
use crate::dto::FireflyPacket;
use crate::storage::FireflyStore;

/// Maximum stream length before backpressure kicks in.
pub const MAX_STREAM_LENGTH: usize = 10000;

// =============================================================================
// STREAM ENTRY
// =============================================================================

/// An entry read from a message stream.
#[derive(Debug, Clone)]
pub struct StreamEntry {
    pub entry_id: String,
    pub data: HashMap<String, String>,
}

// =============================================================================
// TRANSPORT TRAIT
// =============================================================================

/// Transport layer abstraction.
#[async_trait::async_trait]
pub trait Transport: Send + Sync {
    /// Add entry to stream.
    async fn xadd(&self, stream: &str, data: HashMap<String, String>, max_len: usize) -> Result<String>;

    /// Read from streams (blocking).
    async fn xread(
        &self,
        streams: &[String],
        count: usize,
        block_ms: u64,
        last_ids: Option<HashMap<String, String>>,
    ) -> Result<HashMap<String, Vec<StreamEntry>>>;

    /// Get stream length.
    async fn xlen(&self, stream: &str) -> Result<usize>;
}

// =============================================================================
// IN-MEMORY TRANSPORT
// =============================================================================

/// In-memory transport for testing.
#[derive(Debug, Default)]
pub struct InMemoryTransport {
    streams: std::sync::RwLock<HashMap<String, Vec<(String, HashMap<String, String>)>>>,
    next_id: std::sync::atomic::AtomicU64,
}

impl InMemoryTransport {
    pub fn new() -> Self {
        Self::default()
    }

    fn generate_id(&self) -> String {
        let id = self
            .next_id
            .fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        format!("{}-0", id)
    }
}

#[async_trait::async_trait]
impl Transport for InMemoryTransport {
    async fn xadd(&self, stream: &str, data: HashMap<String, String>, max_len: usize) -> Result<String> {
        let mut streams = self
            .streams
            .write()
            .map_err(|_| FireflyError::TransportError("Lock poisoned".into()))?;

        let stream_data = streams.entry(stream.to_string()).or_insert_with(Vec::new);

        // Trim if over max_len
        if stream_data.len() >= max_len {
            let trim_count = stream_data.len() - max_len + 1;
            stream_data.drain(0..trim_count);
        }

        let id = self.generate_id();
        stream_data.push((id.clone(), data));

        Ok(id)
    }

    async fn xread(
        &self,
        streams: &[String],
        count: usize,
        _block_ms: u64,
        last_ids: Option<HashMap<String, String>>,
    ) -> Result<HashMap<String, Vec<StreamEntry>>> {
        let stream_lock = self
            .streams
            .read()
            .map_err(|_| FireflyError::TransportError("Lock poisoned".into()))?;

        let last_ids = last_ids.unwrap_or_default();
        let mut result = HashMap::new();

        for stream_name in streams {
            if let Some(stream_data) = stream_lock.get(stream_name) {
                let last_id = last_ids.get(stream_name).map(|s| s.as_str()).unwrap_or("0");

                let entries: Vec<StreamEntry> = stream_data
                    .iter()
                    .filter(|(id, _)| id.as_str() > last_id)
                    .take(count)
                    .map(|(id, data)| StreamEntry {
                        entry_id: id.clone(),
                        data: data.clone(),
                    })
                    .collect();

                if !entries.is_empty() {
                    result.insert(stream_name.clone(), entries);
                }
            }
        }

        Ok(result)
    }

    async fn xlen(&self, stream: &str) -> Result<usize> {
        let streams = self
            .streams
            .read()
            .map_err(|_| FireflyError::TransportError("Lock poisoned".into()))?;

        Ok(streams.get(stream).map(|s| s.len()).unwrap_or(0))
    }
}

// =============================================================================
// PACKET TRANSPORT
// =============================================================================

/// High-level packet transport operations.
pub struct PacketTransport<T: Transport> {
    inner: T,
}

impl<T: Transport> PacketTransport<T> {
    pub fn new(transport: T) -> Self {
        Self { inner: transport }
    }

    /// Send a packet to its target stream.
    pub async fn send_packet(&self, packet: &FireflyPacket) -> Result<String> {
        let stream = packet.route_key();
        let data = packet.to_string_map();
        self.inner.xadd(&stream, data, MAX_STREAM_LENGTH).await
    }

    /// Send a packet to a specific node's work queue.
    pub async fn send_to_node(&self, packet: &FireflyPacket) -> Result<String> {
        let stream = packet.node_key();
        let data = packet.to_string_map();
        self.inner.xadd(&stream, data, MAX_STREAM_LENGTH).await
    }

    /// Send execution result.
    pub async fn send_result(&self, exec_id: &str, result: HashMap<String, String>) -> Result<String> {
        let stream = format!("firefly:results:{}", exec_id);
        self.inner.xadd(&stream, result, MAX_STREAM_LENGTH).await
    }

    /// Send failed packet to dead letter queue.
    pub async fn send_dead_letter(&self, packet: &FireflyPacket, error: &str) -> Result<String> {
        let mut data = packet.to_string_map();
        data.insert("error".to_string(), error.to_string());
        self.inner.xadd("firefly:dead-letter", data, MAX_STREAM_LENGTH).await
    }

    /// Add to stream with backpressure handling.
    pub async fn xadd_with_backpressure(
        &self,
        stream: &str,
        data: HashMap<String, String>,
    ) -> Result<String> {
        let length = self.inner.xlen(stream).await?;

        if length > MAX_STREAM_LENGTH {
            // Wait for consumers to catch up
            tokio::time::sleep(Duration::from_millis(100)).await;

            let length = self.inner.xlen(stream).await?;
            if length > MAX_STREAM_LENGTH {
                return Err(FireflyError::TransportError(format!(
                    "Stream {} at capacity ({})",
                    stream, length
                )));
            }
        }

        self.inner.xadd(stream, data, MAX_STREAM_LENGTH).await
    }
}

// =============================================================================
// PACKET ROUTER
// =============================================================================

/// Route packets through the distributed execution graph.
pub struct PacketRouter<T: Transport> {
    transport: PacketTransport<T>,
    store: std::sync::Arc<FireflyStore>,
}

impl<T: Transport> PacketRouter<T> {
    pub fn new(transport: T, store: std::sync::Arc<FireflyStore>) -> Self {
        Self {
            transport: PacketTransport::new(transport),
            store,
        }
    }

    /// Route a packet to its destination.
    pub async fn route(&self, packet: &FireflyPacket) -> Result<()> {
        if packet.flags & crate::dto::flags::BROADCAST != 0 {
            self.route_broadcast(packet).await
        } else {
            self.route_direct(packet).await
        }
    }

    /// Route packet directly to target node.
    async fn route_direct(&self, packet: &FireflyPacket) -> Result<()> {
        self.transport.send_to_node(packet).await?;
        Ok(())
    }

    /// Route packet to similar nodes via Hamming search.
    async fn route_broadcast(&self, packet: &FireflyPacket) -> Result<()> {
        let similar = self.store.find_similar_nodes(&packet.resonance, 10).await?;

        for (node_id, _sim) in similar {
            let target_packet = packet.hop("router", &node_id)?;
            self.transport.send_to_node(&target_packet).await?;
        }

        Ok(())
    }

    /// Submit an execution request.
    pub async fn submit_execution(
        &self,
        dto_id: &str,
        operation: &str,
        input_data: HashMap<String, serde_json::Value>,
    ) -> Result<String> {
        let packet = FireflyPacket::for_dto(dto_id, operation, input_data);
        let stream = format!("firefly:execute:{}", dto_id);
        let data = packet.to_string_map();
        self.transport.inner.xadd(&stream, data, MAX_STREAM_LENGTH).await?;
        Ok(packet.created_at.to_rfc3339())
    }

    /// Get execution plan from graph database.
    pub async fn plan_execution(&self, dto_id: &str, operation: &str) -> Result<Vec<String>> {
        let entry_id = format!("{}_{}_entry", dto_id, operation);
        let path = self.store.get_execution_path(&entry_id).await?;

        if path.is_empty() {
            Ok(vec![entry_id])
        } else {
            Ok(path)
        }
    }

    /// Wait for and collect execution result.
    pub async fn collect_result(
        &self,
        exec_id: &str,
        timeout_ms: u64,
    ) -> Result<Option<HashMap<String, String>>> {
        let stream = format!("firefly:results:{}", exec_id);
        let result = self
            .transport
            .inner
            .xread(&[stream.clone()], 1, timeout_ms, None)
            .await?;

        Ok(result
            .get(&stream)
            .and_then(|entries| entries.first())
            .map(|entry| entry.data.clone()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_in_memory_transport() {
        let transport = InMemoryTransport::new();

        let mut data = HashMap::new();
        data.insert("key".to_string(), "value".to_string());

        let id = transport.xadd("test_stream", data.clone(), 100).await.unwrap();
        assert!(!id.is_empty());

        let len = transport.xlen("test_stream").await.unwrap();
        assert_eq!(len, 1);

        let entries = transport
            .xread(&["test_stream".to_string()], 10, 0, None)
            .await
            .unwrap();

        assert!(entries.contains_key("test_stream"));
        assert_eq!(entries["test_stream"].len(), 1);
        assert_eq!(entries["test_stream"][0].data["key"], "value");
    }

    #[tokio::test]
    async fn test_backpressure() {
        let transport = InMemoryTransport::new();
        let packet_transport = PacketTransport::new(transport);

        // Fill stream to capacity
        for i in 0..MAX_STREAM_LENGTH + 10 {
            let mut data = HashMap::new();
            data.insert("i".to_string(), i.to_string());
            packet_transport
                .inner
                .xadd("test", data, MAX_STREAM_LENGTH)
                .await
                .unwrap();
        }

        let len = packet_transport.inner.xlen("test").await.unwrap();
        assert!(len <= MAX_STREAM_LENGTH);
    }
}
