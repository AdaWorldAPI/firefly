//! Firefly Storage: Unified storage abstraction.
//!
//! In Python this uses LanceDB + DuckDB + Kuzu.
//! In Rust we provide a trait-based abstraction that can be implemented
//! for different backends.
//!
//! - **Vector Store**: Hamming similarity search (LanceDB equivalent)
//! - **Catalog Store**: SQL analytics (DuckDB equivalent)
//! - **Graph Store**: Cypher traversal (Kuzu equivalent)

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use crate::{FireflyError, Result, HammingVector};
use crate::dto::{FireflyNode, FireflyEdge};

// =============================================================================
// STORAGE TRAITS
// =============================================================================

/// Vector store for similarity search.
#[async_trait::async_trait]
pub trait VectorStore: Send + Sync {
    /// Store a node's resonance vector.
    async fn store_vector(&self, id: &str, vector: &HammingVector, metadata: HashMap<String, String>) -> Result<()>;

    /// Find k most similar vectors.
    async fn find_similar(&self, query: &HammingVector, k: usize) -> Result<Vec<(String, f64)>>;
}

/// Catalog store for SQL-like queries.
#[async_trait::async_trait]
pub trait CatalogStore: Send + Sync {
    /// Store a node record.
    async fn store_node(&self, node: &FireflyNode) -> Result<()>;

    /// Get a node by ID.
    async fn get_node(&self, id: &str) -> Result<Option<FireflyNode>>;

    /// Store an edge record.
    async fn store_edge(&self, edge: &FireflyEdge) -> Result<()>;

    /// Get outgoing edges from a node.
    async fn get_outgoing_edges(&self, node_id: &str) -> Result<Vec<FireflyEdge>>;

    /// Log an execution event.
    async fn log_execution(
        &self,
        execution_id: &str,
        node_id: &str,
        duration_ms: f64,
        success: bool,
        error: Option<&str>,
    ) -> Result<()>;

    /// Get slowest nodes by average execution time.
    async fn get_slowest_nodes(&self, limit: usize) -> Result<Vec<NodeStats>>;
}

/// Graph store for traversal queries.
#[async_trait::async_trait]
pub trait GraphStore: Send + Sync {
    /// Store a node in the graph.
    async fn add_node(&self, id: &str, node_type: &str, executor: &str) -> Result<()>;

    /// Store an edge in the graph.
    async fn add_edge(&self, source: &str, target: &str, edge_type: &str, condition: Option<&str>) -> Result<()>;

    /// Get execution path from start node.
    async fn get_execution_path(&self, start_id: &str) -> Result<Vec<String>>;

    /// Get upstream nodes within N hops.
    async fn get_upstream_nodes(&self, node_id: &str, hops: u32) -> Result<Vec<String>>;
}

// =============================================================================
// DATA TYPES
// =============================================================================

/// Node execution statistics.
#[derive(Debug, Clone)]
pub struct NodeStats {
    pub node_id: String,
    pub executions: u64,
    pub avg_duration_ms: f64,
    pub max_duration_ms: f64,
    pub failures: u64,
}

/// Execution log entry.
#[derive(Debug, Clone)]
pub struct ExecutionLogEntry {
    pub id: String,
    pub execution_id: String,
    pub node_id: String,
    pub duration_ms: f64,
    pub success: bool,
    pub error: Option<String>,
    pub timestamp: u64,
}

// =============================================================================
// IN-MEMORY IMPLEMENTATION
// =============================================================================

/// In-memory storage implementation for testing and simple use cases.
#[derive(Debug, Default)]
pub struct InMemoryStore {
    nodes: RwLock<HashMap<String, FireflyNode>>,
    edges: RwLock<Vec<FireflyEdge>>,
    vectors: RwLock<HashMap<String, (HammingVector, HashMap<String, String>)>>,
    execution_log: RwLock<Vec<ExecutionLogEntry>>,
}

impl InMemoryStore {
    pub fn new() -> Self {
        Self::default()
    }
}

#[async_trait::async_trait]
impl VectorStore for InMemoryStore {
    async fn store_vector(
        &self,
        id: &str,
        vector: &HammingVector,
        metadata: HashMap<String, String>,
    ) -> Result<()> {
        let mut vectors = self.vectors.write().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;
        vectors.insert(id.to_string(), (vector.clone(), metadata));
        Ok(())
    }

    async fn find_similar(&self, query: &HammingVector, k: usize) -> Result<Vec<(String, f64)>> {
        let vectors = self.vectors.read().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;

        let mut results: Vec<_> = vectors
            .iter()
            .map(|(id, (vec, _))| (id.clone(), query.similarity(vec)))
            .collect();

        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(k);

        Ok(results)
    }
}

#[async_trait::async_trait]
impl CatalogStore for InMemoryStore {
    async fn store_node(&self, node: &FireflyNode) -> Result<()> {
        let mut nodes = self.nodes.write().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;
        nodes.insert(node.id.clone(), node.clone());
        Ok(())
    }

    async fn get_node(&self, id: &str) -> Result<Option<FireflyNode>> {
        let nodes = self.nodes.read().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;
        Ok(nodes.get(id).cloned())
    }

    async fn store_edge(&self, edge: &FireflyEdge) -> Result<()> {
        let mut edges = self.edges.write().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;
        edges.push(edge.clone());
        Ok(())
    }

    async fn get_outgoing_edges(&self, node_id: &str) -> Result<Vec<FireflyEdge>> {
        let edges = self.edges.read().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;
        Ok(edges.iter().filter(|e| e.source_id == node_id).cloned().collect())
    }

    async fn log_execution(
        &self,
        execution_id: &str,
        node_id: &str,
        duration_ms: f64,
        success: bool,
        error: Option<&str>,
    ) -> Result<()> {
        let mut log = self.execution_log.write().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;

        let entry = ExecutionLogEntry {
            id: uuid::Uuid::new_v4().to_string(),
            execution_id: execution_id.to_string(),
            node_id: node_id.to_string(),
            duration_ms,
            success,
            error: error.map(|s| s.to_string()),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
        };

        log.push(entry);
        Ok(())
    }

    async fn get_slowest_nodes(&self, limit: usize) -> Result<Vec<NodeStats>> {
        let log = self.execution_log.read().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;

        // Aggregate by node_id
        let mut stats_map: HashMap<String, (u64, f64, f64, u64)> = HashMap::new();

        for entry in log.iter() {
            let stat = stats_map.entry(entry.node_id.clone()).or_insert((0, 0.0, 0.0, 0));
            stat.0 += 1; // count
            stat.1 += entry.duration_ms; // sum for avg
            if entry.duration_ms > stat.2 {
                stat.2 = entry.duration_ms; // max
            }
            if !entry.success {
                stat.3 += 1; // failures
            }
        }

        let mut results: Vec<NodeStats> = stats_map
            .into_iter()
            .map(|(node_id, (count, sum, max, failures))| NodeStats {
                node_id,
                executions: count,
                avg_duration_ms: if count > 0 { sum / count as f64 } else { 0.0 },
                max_duration_ms: max,
                failures,
            })
            .collect();

        results.sort_by(|a, b| b.avg_duration_ms.partial_cmp(&a.avg_duration_ms).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(limit);

        Ok(results)
    }
}

#[async_trait::async_trait]
impl GraphStore for InMemoryStore {
    async fn add_node(&self, id: &str, _node_type: &str, _executor: &str) -> Result<()> {
        // In-memory: just ensure node exists in catalog
        let exists = {
            let nodes = self.nodes.read().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;
            nodes.contains_key(id)
        };
        if !exists {
            let node = FireflyNode::from_id(id.to_string());
            self.store_node(&node).await?;
        }
        Ok(())
    }

    async fn add_edge(&self, source: &str, target: &str, _edge_type: &str, _condition: Option<&str>) -> Result<()> {
        // Create a simple edge
        let source_node = self.get_node(source).await?.ok_or_else(|| {
            FireflyError::StorageError(format!("Source node not found: {}", source))
        })?;
        let target_node = self.get_node(target).await?.ok_or_else(|| {
            FireflyError::StorageError(format!("Target node not found: {}", target))
        })?;

        let edge = FireflyEdge::from_nodes(&source_node, &target_node);
        self.store_edge(&edge).await
    }

    async fn get_execution_path(&self, start_id: &str) -> Result<Vec<String>> {
        // Simple BFS traversal
        let mut path = vec![start_id.to_string()];
        let mut current = start_id.to_string();

        for _ in 0..100 {
            // Max depth limit
            let edges = self.get_outgoing_edges(&current).await?;
            if edges.is_empty() {
                break;
            }
            current = edges[0].target_id.clone();
            path.push(current.clone());
        }

        Ok(path)
    }

    async fn get_upstream_nodes(&self, node_id: &str, hops: u32) -> Result<Vec<String>> {
        let edges = self.edges.read().map_err(|_| FireflyError::StorageError("Lock poisoned".into()))?;

        let mut upstream = Vec::new();
        let mut current_layer: Vec<String> = vec![node_id.to_string()];

        for _ in 0..hops {
            let mut next_layer = Vec::new();
            for target in &current_layer {
                for edge in edges.iter() {
                    if edge.target_id == *target && !upstream.contains(&edge.source_id) {
                        upstream.push(edge.source_id.clone());
                        next_layer.push(edge.source_id.clone());
                    }
                }
            }
            if next_layer.is_empty() {
                break;
            }
            current_layer = next_layer;
        }

        Ok(upstream)
    }
}

// =============================================================================
// UNIFIED STORE
// =============================================================================

/// Unified store wrapping all three storage types.
pub struct FireflyStore {
    pub vector: Arc<dyn VectorStore>,
    pub catalog: Arc<dyn CatalogStore>,
    pub graph: Arc<dyn GraphStore>,
}

impl FireflyStore {
    /// Create a new store with in-memory backends.
    pub fn in_memory() -> Self {
        let store = Arc::new(InMemoryStore::new());
        Self {
            vector: store.clone(),
            catalog: store.clone(),
            graph: store,
        }
    }

    /// Store a node in all backends.
    pub async fn store_node(&self, node: &FireflyNode) -> Result<()> {
        // Vector store
        self.vector
            .store_vector(&node.id, &node.resonance, HashMap::new())
            .await?;

        // Catalog store
        self.catalog.store_node(node).await?;

        // Graph store
        self.graph
            .add_node(&node.id, &format!("{:?}", node.node_type), &format!("{:?}", node.executor))
            .await?;

        Ok(())
    }

    /// Store an edge in all backends.
    pub async fn store_edge(&self, edge: &FireflyEdge) -> Result<()> {
        // Vector store
        self.vector
            .store_vector(&edge.id, &edge.resonance, HashMap::new())
            .await?;

        // Catalog store
        self.catalog.store_edge(edge).await?;

        // Graph store
        self.graph
            .add_edge(
                &edge.source_id,
                &edge.target_id,
                &format!("{:?}", edge.edge_type),
                edge.condition.as_deref(),
            )
            .await?;

        Ok(())
    }

    /// Find similar nodes by resonance.
    pub async fn find_similar_nodes(&self, resonance: &HammingVector, k: usize) -> Result<Vec<(String, f64)>> {
        self.vector.find_similar(resonance, k).await
    }

    /// Get node by ID.
    pub async fn get_node(&self, id: &str) -> Result<Option<FireflyNode>> {
        self.catalog.get_node(id).await
    }

    /// Get execution path.
    pub async fn get_execution_path(&self, start_id: &str) -> Result<Vec<String>> {
        self.graph.get_execution_path(start_id).await
    }

    /// Get upstream nodes.
    pub async fn get_upstream_nodes(&self, node_id: &str, hops: u32) -> Result<Vec<String>> {
        self.graph.get_upstream_nodes(node_id, hops).await
    }

    /// Log execution.
    pub async fn log_execution(
        &self,
        execution_id: &str,
        node_id: &str,
        duration_ms: f64,
        success: bool,
        error: Option<&str>,
    ) -> Result<()> {
        self.catalog.log_execution(execution_id, node_id, duration_ms, success, error).await
    }

    /// Get slowest nodes.
    pub async fn get_slowest_nodes(&self, limit: usize) -> Result<Vec<NodeStats>> {
        self.catalog.get_slowest_nodes(limit).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_in_memory_store() {
        let store = FireflyStore::in_memory();

        let node = FireflyNode::from_id("test_node".into());
        store.store_node(&node).await.unwrap();

        let retrieved = store.get_node("test_node").await.unwrap();
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().id, "test_node");
    }

    #[tokio::test]
    async fn test_similarity_search() {
        let store = FireflyStore::in_memory();

        let node1 = FireflyNode::from_id("validate_email".into());
        let node2 = FireflyNode::from_id("validate_phone".into());
        let node3 = FireflyNode::from_id("send_notification".into());

        store.store_node(&node1).await.unwrap();
        store.store_node(&node2).await.unwrap();
        store.store_node(&node3).await.unwrap();

        let similar = store.find_similar_nodes(&node1.resonance, 3).await.unwrap();
        assert!(!similar.is_empty());
    }

    #[tokio::test]
    async fn test_execution_logging() {
        let store = FireflyStore::in_memory();

        store.log_execution("exec1", "node1", 100.0, true, None).await.unwrap();
        store.log_execution("exec1", "node1", 200.0, true, None).await.unwrap();
        store.log_execution("exec1", "node2", 50.0, false, Some("error")).await.unwrap();

        let slowest = store.get_slowest_nodes(10).await.unwrap();
        assert_eq!(slowest.len(), 2);
        assert_eq!(slowest[0].node_id, "node1"); // 150ms avg > 50ms
    }
}
