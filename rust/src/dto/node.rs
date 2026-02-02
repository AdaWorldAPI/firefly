//! Firefly Node: Executable graph node in 1.25KB.
//!
//! Each node encodes:
//! - **WHAT**: input/output schema (bound with ROLE_SCHEMA)
//! - **HOW**: execution logic (bound with ROLE_LOGIC)
//! - **WHERE**: position in graph (bound with ROLE_CONTEXT)
//!
//! All three are recoverable via XOR unbinding.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::SystemTime;

use crate::{FireflyError, Result, HammingVector, bundle, roles};

/// Node executor type.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Executor {
    /// Native Rust/Python function.
    Native,
    /// WebAssembly module.
    Wasm,
    /// SQL query.
    Sql,
}

impl Default for Executor {
    fn default() -> Self {
        Executor::Native
    }
}

/// Node type within the execution graph.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum NodeType {
    /// Validation node (checks constraints).
    Validate,
    /// Transform node (modifies data).
    Transform,
    /// Persist node (writes to storage).
    Persist,
    /// Trigger node (initiates flow).
    Trigger,
    /// Query node (reads from storage).
    Query,
}

impl Default for NodeType {
    fn default() -> Self {
        NodeType::Transform
    }
}

/// Executable graph node in 1.25KB.
///
/// The resonance vector is the identity - everything else is metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FireflyNode {
    /// Unique identifier.
    pub id: String,

    /// 10K-bit resonance vector (the node's identity).
    #[serde(with = "hex_vector")]
    pub resonance: HammingVector,

    /// Executor type.
    #[serde(default)]
    pub executor: Executor,

    /// Function name reference.
    #[serde(default)]
    pub fn_name: String,

    /// Node type.
    #[serde(default, rename = "type")]
    pub node_type: NodeType,

    /// Relative execution cost (for optimizer).
    #[serde(default = "default_cost")]
    pub cost: u32,

    /// Whether the node has side effects.
    #[serde(default = "default_true")]
    pub pure: bool,

    /// Whether the node can be parallelized.
    #[serde(default = "default_true")]
    pub parallelizable: bool,

    /// Input schema: field name -> type.
    #[serde(default)]
    pub input_schema: HashMap<String, String>,

    /// Output schema: field name -> type.
    #[serde(default)]
    pub output_schema: HashMap<String, String>,

    /// Creation timestamp (Unix epoch seconds).
    #[serde(default = "now")]
    pub created_at: u64,
}

fn default_cost() -> u32 {
    1
}
fn default_true() -> bool {
    true
}
fn now() -> u64 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

impl FireflyNode {
    /// Create a node from semantic components.
    ///
    /// The resonance vector is the bundle of role-bound components:
    /// ```text
    /// resonance = bundle([
    ///     bind(schema, ROLE_SCHEMA),
    ///     bind(logic, ROLE_LOGIC),
    ///     bind(context, ROLE_CONTEXT)
    /// ])
    /// ```
    pub fn from_components(
        id: String,
        schema_vec: &HammingVector,
        logic_vec: &HammingVector,
        context_vec: &HammingVector,
    ) -> Self {
        let bound_schema = schema_vec ^ &*roles::ROLE_SCHEMA;
        let bound_logic = logic_vec ^ &*roles::ROLE_LOGIC;
        let bound_context = context_vec ^ &*roles::ROLE_CONTEXT;

        let resonance = bundle(&[bound_schema, bound_logic, bound_context]);

        Self {
            id,
            resonance,
            executor: Executor::default(),
            fn_name: String::new(),
            node_type: NodeType::default(),
            cost: 1,
            pure: true,
            parallelizable: true,
            input_schema: HashMap::new(),
            output_schema: HashMap::new(),
            created_at: now(),
        }
    }

    /// Create a node with deterministic resonance from ID.
    pub fn from_id(id: String) -> Self {
        let resonance = HammingVector::from_seed(&id);
        Self {
            id,
            resonance,
            executor: Executor::default(),
            fn_name: String::new(),
            node_type: NodeType::default(),
            cost: 1,
            pure: true,
            parallelizable: true,
            input_schema: HashMap::new(),
            output_schema: HashMap::new(),
            created_at: now(),
        }
    }

    /// Approximate recovery of schema component.
    ///
    /// Due to bundling noise, this is an approximation.
    pub fn extract_schema(&self) -> HammingVector {
        &self.resonance ^ &*roles::ROLE_SCHEMA
    }

    /// Approximate recovery of logic component.
    pub fn extract_logic(&self) -> HammingVector {
        &self.resonance ^ &*roles::ROLE_LOGIC
    }

    /// Approximate recovery of context component.
    pub fn extract_context(&self) -> HammingVector {
        &self.resonance ^ &*roles::ROLE_CONTEXT
    }

    /// Similarity to another node.
    pub fn similarity_to(&self, other: &FireflyNode) -> f64 {
        self.resonance.similarity(&other.resonance)
    }

    /// Create edge resonance by binding with another node.
    pub fn bind_with(&self, other: &FireflyNode) -> HammingVector {
        &self.resonance ^ &other.resonance
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

/// Builder for FireflyNode.
pub struct FireflyNodeBuilder {
    node: FireflyNode,
}

impl FireflyNodeBuilder {
    pub fn new(id: impl Into<String>) -> Self {
        Self {
            node: FireflyNode::from_id(id.into()),
        }
    }

    pub fn executor(mut self, executor: Executor) -> Self {
        self.node.executor = executor;
        self
    }

    pub fn fn_name(mut self, name: impl Into<String>) -> Self {
        self.node.fn_name = name.into();
        self
    }

    pub fn node_type(mut self, node_type: NodeType) -> Self {
        self.node.node_type = node_type;
        self
    }

    pub fn cost(mut self, cost: u32) -> Self {
        self.node.cost = cost;
        self
    }

    pub fn pure(mut self, pure: bool) -> Self {
        self.node.pure = pure;
        self
    }

    pub fn parallelizable(mut self, parallelizable: bool) -> Self {
        self.node.parallelizable = parallelizable;
        self
    }

    pub fn input(mut self, field: impl Into<String>, type_name: impl Into<String>) -> Self {
        self.node.input_schema.insert(field.into(), type_name.into());
        self
    }

    pub fn output(mut self, field: impl Into<String>, type_name: impl Into<String>) -> Self {
        self.node
            .output_schema
            .insert(field.into(), type_name.into());
        self
    }

    pub fn build(self) -> FireflyNode {
        self.node
    }
}

/// Serde helper for HammingVector as hex string.
mod hex_vector {
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
    fn test_from_id() {
        let node = FireflyNode::from_id("test_node".into());
        assert_eq!(node.id, "test_node");
        assert!(node.pure);
    }

    #[test]
    fn test_from_components() {
        let schema = HammingVector::from_seed("schema");
        let logic = HammingVector::from_seed("logic");
        let context = HammingVector::from_seed("context");

        let node = FireflyNode::from_components("test".into(), &schema, &logic, &context);

        // The node should have some similarity to the extracted components
        // (not exact due to bundling noise)
        let extracted_schema = node.extract_schema();
        assert!(schema.similarity(&extracted_schema) > 0.3);
    }

    #[test]
    fn test_builder() {
        let node = FireflyNodeBuilder::new("my_node")
            .executor(Executor::Wasm)
            .fn_name("validate")
            .node_type(NodeType::Validate)
            .cost(5)
            .pure(false)
            .input("email", "string")
            .output("valid", "bool")
            .build();

        assert_eq!(node.id, "my_node");
        assert_eq!(node.executor, Executor::Wasm);
        assert_eq!(node.fn_name, "validate");
        assert_eq!(node.node_type, NodeType::Validate);
        assert_eq!(node.cost, 5);
        assert!(!node.pure);
        assert_eq!(node.input_schema.get("email"), Some(&"string".into()));
        assert_eq!(node.output_schema.get("valid"), Some(&"bool".into()));
    }

    #[test]
    fn test_json_roundtrip() {
        let node = FireflyNodeBuilder::new("test")
            .fn_name("my_func")
            .build();

        let json = node.to_json().unwrap();
        let restored = FireflyNode::from_json(&json).unwrap();

        assert_eq!(node.id, restored.id);
        assert_eq!(node.fn_name, restored.fn_name);
        assert_eq!(node.resonance, restored.resonance);
    }

    #[test]
    fn test_similarity() {
        let node1 = FireflyNode::from_id("validate_email".into());
        let node2 = FireflyNode::from_id("validate_phone".into());
        let node3 = FireflyNode::from_id("completely_different".into());

        // Similar names should have some similarity
        let sim12 = node1.similarity_to(&node2);
        let sim13 = node1.similarity_to(&node3);

        assert!(sim12 > sim13);
    }
}
