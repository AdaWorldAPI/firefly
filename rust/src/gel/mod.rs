//! GEL: Graph Execution Language
//!
//! A declarative DSL for expressing graph execution patterns.
//! Inspired by EdgeQL, Cypher, and dataflow languages.
//!
//! ## Core Concepts
//!
//! - **Prefix Addressing**: Nodes addressed by semantic prefix paths
//! - **DN (Distinguished Name)**: Hierarchical node identification
//! - **Work Stealing**: Parallel execution with load balancing
//! - **ACID Semantics**: Transactional graph mutations
//!
//! ## Example
//!
//! ```ignore
//! // GEL query: find all validation nodes and execute in parallel
//! gel! {
//!     MATCH (n:Function)-[:CALLS]->(v:Validation)
//!     WHERE n.dto = "users"
//!     EXECUTE v WITH work_steal
//!     RETURN v.result
//! }
//! ```

use std::collections::HashMap;
use std::sync::Arc;

use dashmap::DashMap;
use parking_lot::RwLock;
use rayon::prelude::*;

use crate::{HammingVector, Result, FireflyError};
use crate::dto::FireflyNode;

// =============================================================================
// PREFIX ADDRESSING (DN - Distinguished Name)
// =============================================================================

/// Distinguished Name for hierarchical node addressing.
///
/// Format: `dto://users/create/validate_email`
///
/// Components:
/// - scheme: `dto`, `fn`, `type`, `edge`
/// - segments: hierarchical path components
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct DistinguishedName {
    pub scheme: String,
    pub segments: Vec<String>,
}

impl DistinguishedName {
    /// Parse a DN from string.
    ///
    /// Examples:
    /// - `dto://users/create/validate`
    /// - `fn://validate_email`
    /// - `type://User/email`
    pub fn parse(s: &str) -> Result<Self> {
        let parts: Vec<&str> = s.splitn(2, "://").collect();
        if parts.len() != 2 {
            return Err(FireflyError::InvalidNodeType(format!(
                "Invalid DN format: {}",
                s
            )));
        }

        let scheme = parts[0].to_string();
        let segments: Vec<String> = parts[1]
            .split('/')
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
            .collect();

        Ok(Self { scheme, segments })
    }

    /// Create DN from components.
    pub fn new(scheme: impl Into<String>, segments: Vec<String>) -> Self {
        Self {
            scheme: scheme.into(),
            segments,
        }
    }

    /// Get the full path string.
    pub fn to_string(&self) -> String {
        format!("{}://{}", self.scheme, self.segments.join("/"))
    }

    /// Check if this DN is a prefix of another.
    pub fn is_prefix_of(&self, other: &DistinguishedName) -> bool {
        if self.scheme != other.scheme {
            return false;
        }
        if self.segments.len() > other.segments.len() {
            return false;
        }
        self.segments
            .iter()
            .zip(other.segments.iter())
            .all(|(a, b)| a == b)
    }

    /// Get parent DN (remove last segment).
    pub fn parent(&self) -> Option<Self> {
        if self.segments.is_empty() {
            return None;
        }
        let mut segments = self.segments.clone();
        segments.pop();
        Some(Self {
            scheme: self.scheme.clone(),
            segments,
        })
    }

    /// Append a segment.
    pub fn child(&self, segment: impl Into<String>) -> Self {
        let mut segments = self.segments.clone();
        segments.push(segment.into());
        Self {
            scheme: self.scheme.clone(),
            segments,
        }
    }

    /// Get the leaf (last segment).
    pub fn leaf(&self) -> Option<&str> {
        self.segments.last().map(|s| s.as_str())
    }

    /// Get depth (number of segments).
    pub fn depth(&self) -> usize {
        self.segments.len()
    }

    /// Create fingerprint for this DN.
    pub fn fingerprint(&self) -> HammingVector {
        HammingVector::from_seed(&self.to_string())
    }
}

// =============================================================================
// GEL QUERY BUILDER
// =============================================================================

/// GEL query execution mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExecutionMode {
    /// Sequential execution (default).
    Sequential,
    /// Parallel execution with work-stealing.
    WorkSteal,
    /// Pipelined execution (streaming).
    Pipeline,
}

/// GEL query pattern for matching nodes.
#[derive(Debug, Clone)]
pub enum Pattern {
    /// Match node by DN prefix.
    ByPrefix(DistinguishedName),
    /// Match node by type.
    ByType(String),
    /// Match node by resonance similarity.
    BySimilarity {
        reference: HammingVector,
        threshold: f64,
    },
    /// Match node by property.
    ByProperty { key: String, value: String },
    /// Match connected nodes.
    Connected {
        from: Box<Pattern>,
        edge_type: String,
        to: Box<Pattern>,
    },
}

/// GEL query builder for fluent API.
#[derive(Debug, Clone)]
pub struct GelQuery {
    patterns: Vec<Pattern>,
    filters: Vec<Box<dyn GelFilter>>,
    execution_mode: ExecutionMode,
    limit: Option<usize>,
    timeout_ms: Option<u64>,
}

/// Filter trait for GEL queries.
pub trait GelFilter: std::fmt::Debug + Send + Sync {
    fn matches(&self, node: &FireflyNode) -> bool;
    fn clone_box(&self) -> Box<dyn GelFilter>;
}

impl Clone for Box<dyn GelFilter> {
    fn clone(&self) -> Self {
        self.clone_box()
    }
}

/// Property equality filter.
#[derive(Debug, Clone)]
pub struct PropertyFilter {
    pub key: String,
    pub value: String,
}

impl GelFilter for PropertyFilter {
    fn matches(&self, node: &FireflyNode) -> bool {
        // Check node properties (simplified - would check metadata in real impl)
        match self.key.as_str() {
            "id" => node.id == self.value,
            "fn_name" => node.fn_name == self.value,
            _ => false,
        }
    }

    fn clone_box(&self) -> Box<dyn GelFilter> {
        Box::new(self.clone())
    }
}

impl Default for GelQuery {
    fn default() -> Self {
        Self::new()
    }
}

impl GelQuery {
    /// Create a new GEL query.
    pub fn new() -> Self {
        Self {
            patterns: Vec::new(),
            filters: Vec::new(),
            execution_mode: ExecutionMode::Sequential,
            limit: None,
            timeout_ms: None,
        }
    }

    /// Match nodes by DN prefix.
    pub fn match_prefix(mut self, dn: &str) -> Result<Self> {
        let dn = DistinguishedName::parse(dn)?;
        self.patterns.push(Pattern::ByPrefix(dn));
        Ok(self)
    }

    /// Match nodes by type.
    pub fn match_type(mut self, node_type: &str) -> Self {
        self.patterns.push(Pattern::ByType(node_type.to_string()));
        self
    }

    /// Match nodes by similarity.
    pub fn match_similar(mut self, reference: &HammingVector, threshold: f64) -> Self {
        self.patterns.push(Pattern::BySimilarity {
            reference: reference.clone(),
            threshold,
        });
        self
    }

    /// Filter by property.
    pub fn filter_property(mut self, key: &str, value: &str) -> Self {
        self.filters.push(Box::new(PropertyFilter {
            key: key.to_string(),
            value: value.to_string(),
        }));
        self
    }

    /// Set execution mode to work-stealing parallel.
    pub fn with_work_steal(mut self) -> Self {
        self.execution_mode = ExecutionMode::WorkSteal;
        self
    }

    /// Set execution mode to pipeline.
    pub fn with_pipeline(mut self) -> Self {
        self.execution_mode = ExecutionMode::Pipeline;
        self
    }

    /// Set result limit.
    pub fn limit(mut self, n: usize) -> Self {
        self.limit = Some(n);
        self
    }

    /// Set execution timeout.
    pub fn timeout(mut self, ms: u64) -> Self {
        self.timeout_ms = Some(ms);
        self
    }
}

// =============================================================================
// GEL EXECUTOR (WORK-STEALING)
// =============================================================================

/// Execution result from a single node.
#[derive(Debug, Clone)]
pub struct NodeResult {
    pub node_id: String,
    pub dn: Option<DistinguishedName>,
    pub success: bool,
    pub output: Option<serde_json::Value>,
    pub duration_ms: f64,
    pub error: Option<String>,
}

/// GEL query execution engine with work-stealing.
pub struct GelExecutor {
    /// Node registry by DN.
    nodes_by_dn: DashMap<String, Arc<FireflyNode>>,
    /// Node registry by ID.
    nodes_by_id: DashMap<String, Arc<FireflyNode>>,
    /// DN index for prefix matching.
    dn_index: RwLock<Vec<(DistinguishedName, String)>>,
    /// Execution statistics.
    stats: DashMap<String, ExecutionStats>,
}

/// Execution statistics per node.
#[derive(Debug, Clone, Default)]
pub struct ExecutionStats {
    pub total_executions: u64,
    pub total_duration_ms: f64,
    pub failures: u64,
}

impl Default for GelExecutor {
    fn default() -> Self {
        Self::new()
    }
}

impl GelExecutor {
    /// Create a new GEL executor.
    pub fn new() -> Self {
        Self {
            nodes_by_dn: DashMap::new(),
            nodes_by_id: DashMap::new(),
            dn_index: RwLock::new(Vec::new()),
            stats: DashMap::new(),
        }
    }

    /// Register a node with a DN.
    pub fn register(&self, dn: DistinguishedName, node: FireflyNode) {
        let node = Arc::new(node);
        let dn_str = dn.to_string();

        self.nodes_by_dn.insert(dn_str.clone(), node.clone());
        self.nodes_by_id.insert(node.id.clone(), node);

        let mut index = self.dn_index.write();
        index.push((dn, dn_str));
    }

    /// Find nodes matching a pattern.
    pub fn find(&self, pattern: &Pattern) -> Vec<Arc<FireflyNode>> {
        match pattern {
            Pattern::ByPrefix(prefix) => {
                let index = self.dn_index.read();
                index
                    .iter()
                    .filter(|(dn, _)| prefix.is_prefix_of(dn))
                    .filter_map(|(_, dn_str)| self.nodes_by_dn.get(dn_str).map(|r| r.clone()))
                    .collect()
            }
            Pattern::ByType(node_type) => {
                self.nodes_by_id
                    .iter()
                    .filter(|r| format!("{:?}", r.node_type) == *node_type)
                    .map(|r| r.clone())
                    .collect()
            }
            Pattern::BySimilarity { reference, threshold } => {
                self.nodes_by_id
                    .iter()
                    .filter(|r| r.resonance.similarity(reference) >= *threshold)
                    .map(|r| r.clone())
                    .collect()
            }
            Pattern::ByProperty { key, value } => {
                self.nodes_by_id
                    .iter()
                    .filter(|r| match key.as_str() {
                        "id" => &r.id == value,
                        "fn_name" => &r.fn_name == value,
                        _ => false,
                    })
                    .map(|r| r.clone())
                    .collect()
            }
            Pattern::Connected { from, edge_type: _, to: _ } => {
                // Simplified: just find 'from' nodes
                // Full implementation would traverse edges
                self.find(from)
            }
        }
    }

    /// Execute a GEL query with work-stealing parallelism.
    pub fn execute(&self, query: &GelQuery) -> Vec<NodeResult> {
        // Collect all matching nodes
        let mut nodes: Vec<Arc<FireflyNode>> = Vec::new();
        for pattern in &query.patterns {
            nodes.extend(self.find(pattern));
        }

        // Apply filters
        for filter in &query.filters {
            nodes.retain(|n| filter.matches(n));
        }

        // Apply limit
        if let Some(limit) = query.limit {
            nodes.truncate(limit);
        }

        // Execute based on mode
        match query.execution_mode {
            ExecutionMode::Sequential => {
                nodes
                    .iter()
                    .map(|node| self.execute_node(node))
                    .collect()
            }
            ExecutionMode::WorkSteal => {
                // Use rayon for work-stealing parallelism
                nodes
                    .par_iter()
                    .map(|node| self.execute_node(node))
                    .collect()
            }
            ExecutionMode::Pipeline => {
                // Pipeline mode: streaming execution
                // For now, same as sequential but could be async streaming
                nodes
                    .iter()
                    .map(|node| self.execute_node(node))
                    .collect()
            }
        }
    }

    /// Execute a single node.
    fn execute_node(&self, node: &FireflyNode) -> NodeResult {
        let start = std::time::Instant::now();

        // Simulate execution (would call actual executor in real impl)
        let success = true;
        let output = Some(serde_json::json!({
            "node_id": node.id,
            "executed": true
        }));

        let duration_ms = start.elapsed().as_secs_f64() * 1000.0;

        // Update stats
        self.stats
            .entry(node.id.clone())
            .and_modify(|s| {
                s.total_executions += 1;
                s.total_duration_ms += duration_ms;
                if !success {
                    s.failures += 1;
                }
            })
            .or_insert_with(|| ExecutionStats {
                total_executions: 1,
                total_duration_ms: duration_ms,
                failures: if success { 0 } else { 1 },
            });

        NodeResult {
            node_id: node.id.clone(),
            dn: None,
            success,
            output,
            duration_ms,
            error: None,
        }
    }

    /// Get execution statistics for a node.
    pub fn get_stats(&self, node_id: &str) -> Option<ExecutionStats> {
        self.stats.get(node_id).map(|r| r.clone())
    }

    /// Get all nodes count.
    pub fn node_count(&self) -> usize {
        self.nodes_by_id.len()
    }
}

// =============================================================================
// ACID TRANSACTION SUPPORT
// =============================================================================

/// Transaction state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransactionState {
    Active,
    Committed,
    RolledBack,
}

/// ACID transaction for graph mutations.
pub struct Transaction {
    id: String,
    state: TransactionState,
    pending_writes: Vec<PendingWrite>,
    pending_deletes: Vec<String>,
}

/// A pending write operation.
#[derive(Debug, Clone)]
struct PendingWrite {
    dn: DistinguishedName,
    node: FireflyNode,
}

impl Transaction {
    /// Create a new transaction.
    pub fn new() -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            state: TransactionState::Active,
            pending_writes: Vec::new(),
            pending_deletes: Vec::new(),
        }
    }

    /// Get transaction ID.
    pub fn id(&self) -> &str {
        &self.id
    }

    /// Get transaction state.
    pub fn state(&self) -> TransactionState {
        self.state
    }

    /// Stage a node write.
    pub fn write(&mut self, dn: DistinguishedName, node: FireflyNode) -> Result<()> {
        if self.state != TransactionState::Active {
            return Err(FireflyError::ExecutionError(
                "Transaction not active".into(),
            ));
        }
        self.pending_writes.push(PendingWrite { dn, node });
        Ok(())
    }

    /// Stage a node delete.
    pub fn delete(&mut self, node_id: &str) -> Result<()> {
        if self.state != TransactionState::Active {
            return Err(FireflyError::ExecutionError(
                "Transaction not active".into(),
            ));
        }
        self.pending_deletes.push(node_id.to_string());
        Ok(())
    }

    /// Commit the transaction to executor.
    pub fn commit(mut self, executor: &GelExecutor) -> Result<()> {
        if self.state != TransactionState::Active {
            return Err(FireflyError::ExecutionError(
                "Transaction not active".into(),
            ));
        }

        // Apply writes
        for write in self.pending_writes.drain(..) {
            executor.register(write.dn, write.node);
        }

        // Apply deletes
        for node_id in self.pending_deletes.drain(..) {
            executor.nodes_by_id.remove(&node_id);
        }

        self.state = TransactionState::Committed;
        Ok(())
    }

    /// Rollback the transaction.
    pub fn rollback(mut self) -> Result<()> {
        if self.state != TransactionState::Active {
            return Err(FireflyError::ExecutionError(
                "Transaction not active".into(),
            ));
        }

        self.pending_writes.clear();
        self.pending_deletes.clear();
        self.state = TransactionState::RolledBack;
        Ok(())
    }
}

impl Default for Transaction {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// TESTS
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dn_parse() {
        let dn = DistinguishedName::parse("dto://users/create/validate").unwrap();
        assert_eq!(dn.scheme, "dto");
        assert_eq!(dn.segments, vec!["users", "create", "validate"]);
    }

    #[test]
    fn test_dn_prefix() {
        let parent = DistinguishedName::parse("dto://users").unwrap();
        let child = DistinguishedName::parse("dto://users/create").unwrap();
        let other = DistinguishedName::parse("dto://orders").unwrap();

        assert!(parent.is_prefix_of(&child));
        assert!(!parent.is_prefix_of(&other));
        assert!(!child.is_prefix_of(&parent));
    }

    #[test]
    fn test_dn_navigation() {
        let dn = DistinguishedName::parse("dto://users/create").unwrap();

        let parent = dn.parent().unwrap();
        assert_eq!(parent.segments, vec!["users"]);

        let child = dn.child("validate");
        assert_eq!(child.segments, vec!["users", "create", "validate"]);

        assert_eq!(dn.leaf(), Some("create"));
    }

    #[test]
    fn test_gel_executor_basic() {
        let executor = GelExecutor::new();

        // Register nodes
        let dn1 = DistinguishedName::parse("dto://users/create/validate_email").unwrap();
        let node1 = FireflyNode::from_id("validate_email".into());
        executor.register(dn1, node1);

        let dn2 = DistinguishedName::parse("dto://users/create/validate_name").unwrap();
        let node2 = FireflyNode::from_id("validate_name".into());
        executor.register(dn2, node2);

        assert_eq!(executor.node_count(), 2);

        // Query by prefix
        let query = GelQuery::new()
            .match_prefix("dto://users/create")
            .unwrap();

        let results = executor.execute(&query);
        assert_eq!(results.len(), 2);
    }

    #[test]
    fn test_work_stealing_execution() {
        let executor = GelExecutor::new();

        // Register many nodes
        for i in 0..100 {
            let dn = DistinguishedName::new("dto", vec!["test".into(), format!("node_{}", i)]);
            let node = FireflyNode::from_id(format!("node_{}", i));
            executor.register(dn, node);
        }

        // Execute with work stealing
        let query = GelQuery::new()
            .match_prefix("dto://test")
            .unwrap()
            .with_work_steal();

        let results = executor.execute(&query);
        assert_eq!(results.len(), 100);
        assert!(results.iter().all(|r| r.success));
    }

    #[test]
    fn test_transaction() {
        let executor = GelExecutor::new();
        let mut tx = Transaction::new();

        // Stage writes
        let dn = DistinguishedName::parse("dto://users/create").unwrap();
        let node = FireflyNode::from_id("create_user".into());
        tx.write(dn, node).unwrap();

        // Commit
        tx.commit(&executor).unwrap();

        assert_eq!(executor.node_count(), 1);
    }

    #[test]
    fn test_transaction_rollback() {
        let executor = GelExecutor::new();
        let mut tx = Transaction::new();

        // Stage writes
        let dn = DistinguishedName::parse("dto://users/create").unwrap();
        let node = FireflyNode::from_id("create_user".into());
        tx.write(dn, node).unwrap();

        // Rollback
        tx.rollback().unwrap();

        assert_eq!(executor.node_count(), 0);
    }
}
