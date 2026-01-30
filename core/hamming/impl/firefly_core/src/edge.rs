//! Firefly Edge: Graph edge as resonance binding.
//!
//! ```text
//! edge.resonance = source.resonance ^ target.resonance
//! ```
//!
//! This means:
//! - Given source + edge -> recover target (approximately)
//! - Given target + edge -> recover source (approximately)
//! - Edge IS the relationship, not just a pointer

use serde::{Deserialize, Serialize};
use std::time::SystemTime;

use crate::error::{FireflyError, Result};
use crate::node::FireflyNode;
use crate::vector::HammingVector;

/// Edge type in the execution graph.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum EdgeType {
    /// Data flows from source to target.
    Feeds,
    /// Source triggers target execution.
    Triggers,
    /// Source guards target (conditional execution).
    Guards,
    /// Source is a checkpoint before target.
    Checkpoints,
}

impl Default for EdgeType {
    fn default() -> Self {
        EdgeType::Feeds
    }
}

/// Edge between nodes = XOR binding of their resonances.
///
/// The edge resonance encodes the RELATIONSHIP between nodes,
/// not just connectivity. Similar edges = similar relationships.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FireflyEdge {
    /// Unique identifier (typically "source_id->target_id").
    pub id: String,

    /// Source node ID.
    pub source_id: String,

    /// Target node ID.
    pub target_id: String,

    /// Resonance = source ^ target (the relationship encoding).
    #[serde(with = "hex_vector")]
    pub resonance: HammingVector,

    /// Edge type.
    #[serde(default, rename = "type")]
    pub edge_type: EdgeType,

    /// Condition expression (for GUARDS edges).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub condition: Option<String>,

    /// Field name (for FEEDS edges - which field flows).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub field: Option<String>,

    /// Creation timestamp (Unix epoch seconds).
    #[serde(default = "now")]
    pub created_at: u64,
}

fn now() -> u64 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

impl FireflyEdge {
    /// Create an edge from two nodes.
    ///
    /// The resonance is computed as `source.resonance ^ target.resonance`.
    pub fn from_nodes(source: &FireflyNode, target: &FireflyNode) -> Self {
        let resonance = &source.resonance ^ &target.resonance;
        Self {
            id: format!("{}->{}", source.id, target.id),
            source_id: source.id.clone(),
            target_id: target.id.clone(),
            resonance,
            edge_type: EdgeType::default(),
            condition: None,
            field: None,
            created_at: now(),
        }
    }

    /// Create an edge from raw resonances.
    pub fn from_resonances(
        source_id: impl Into<String>,
        target_id: impl Into<String>,
        source_resonance: &HammingVector,
        target_resonance: &HammingVector,
    ) -> Self {
        let source_id = source_id.into();
        let target_id = target_id.into();
        let resonance = source_resonance ^ target_resonance;

        Self {
            id: format!("{}->{}", source_id, target_id),
            source_id,
            target_id,
            resonance,
            edge_type: EdgeType::default(),
            condition: None,
            field: None,
            created_at: now(),
        }
    }

    /// Create an edge with a specific type.
    pub fn with_type(mut self, edge_type: EdgeType) -> Self {
        self.edge_type = edge_type;
        self
    }

    /// Add a condition (for GUARDS edges).
    pub fn with_condition(mut self, condition: impl Into<String>) -> Self {
        self.condition = Some(condition.into());
        self
    }

    /// Add a field name (for FEEDS edges).
    pub fn with_field(mut self, field: impl Into<String>) -> Self {
        self.field = Some(field.into());
        self
    }

    /// Given source node, approximate the target resonance.
    ///
    /// ```text
    /// target ≈ source.resonance ^ edge.resonance
    /// ```
    pub fn recover_target(&self, source: &FireflyNode) -> HammingVector {
        &source.resonance ^ &self.resonance
    }

    /// Given target node, approximate the source resonance.
    ///
    /// ```text
    /// source ≈ target.resonance ^ edge.resonance
    /// ```
    pub fn recover_source(&self, target: &FireflyNode) -> HammingVector {
        &target.resonance ^ &self.resonance
    }

    /// Similarity to another edge (how similar are the relationships?).
    pub fn similarity_to(&self, other: &FireflyEdge) -> f64 {
        self.resonance.similarity(&other.resonance)
    }

    /// Serialize to JSON.
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string(self).map_err(FireflyError::from)
    }

    /// Deserialize from JSON.
    pub fn from_json(json: &str) -> Result<Self> {
        serde_json::from_str(json).map_err(FireflyError::from)
    }
}

/// Serde helper for HammingVector as hex string.
mod hex_vector {
    use crate::HammingVector;
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
    fn test_from_nodes() {
        let source = FireflyNode::from_id("source".into());
        let target = FireflyNode::from_id("target".into());

        let edge = FireflyEdge::from_nodes(&source, &target);

        assert_eq!(edge.source_id, "source");
        assert_eq!(edge.target_id, "target");
        assert_eq!(edge.id, "source->target");
    }

    #[test]
    fn test_recover_target() {
        let source = FireflyNode::from_id("source".into());
        let target = FireflyNode::from_id("target".into());

        let edge = FireflyEdge::from_nodes(&source, &target);
        let recovered = edge.recover_target(&source);

        // Should exactly recover target resonance
        assert_eq!(recovered.hamming(&target.resonance), 0);
    }

    #[test]
    fn test_recover_source() {
        let source = FireflyNode::from_id("source".into());
        let target = FireflyNode::from_id("target".into());

        let edge = FireflyEdge::from_nodes(&source, &target);
        let recovered = edge.recover_source(&target);

        // Should exactly recover source resonance
        assert_eq!(recovered.hamming(&source.resonance), 0);
    }

    #[test]
    fn test_similar_edges() {
        // Create similar relationships
        let a1 = FireflyNode::from_id("validate_email".into());
        let a2 = FireflyNode::from_id("check_email".into());
        let b1 = FireflyNode::from_id("validate_phone".into());
        let b2 = FireflyNode::from_id("check_phone".into());

        let edge1 = FireflyEdge::from_nodes(&a1, &a2);
        let edge2 = FireflyEdge::from_nodes(&b1, &b2);

        // Similar relationships should have similar edge resonances
        let sim = edge1.similarity_to(&edge2);
        assert!(sim > 0.3);
    }

    #[test]
    fn test_with_type() {
        let source = FireflyNode::from_id("source".into());
        let target = FireflyNode::from_id("target".into());

        let edge = FireflyEdge::from_nodes(&source, &target)
            .with_type(EdgeType::Guards)
            .with_condition("x > 0");

        assert_eq!(edge.edge_type, EdgeType::Guards);
        assert_eq!(edge.condition, Some("x > 0".into()));
    }

    #[test]
    fn test_json_roundtrip() {
        let source = FireflyNode::from_id("source".into());
        let target = FireflyNode::from_id("target".into());

        let edge = FireflyEdge::from_nodes(&source, &target)
            .with_type(EdgeType::Triggers);

        let json = edge.to_json().unwrap();
        let restored = FireflyEdge::from_json(&json).unwrap();

        assert_eq!(edge.id, restored.id);
        assert_eq!(edge.source_id, restored.source_id);
        assert_eq!(edge.target_id, restored.target_id);
        assert_eq!(edge.edge_type, restored.edge_type);
        assert_eq!(edge.resonance, restored.resonance);
    }
}
