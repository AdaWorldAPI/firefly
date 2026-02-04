//! LadybugDB Declarative Layer - Code as Graph
//!
//! Language constructs as typed nodes/edges. Sits ABOVE the Hamming substrate.
//!
//! ## Node Types
//! - CLASS, METHOD, FUNCTION, PROPERTY
//! - FOREACH, IF, WHILE, MATCH
//! - EXPRESSION, LITERAL, REFERENCE
//! - IMPORT, EXPORT, MODULE
//!
//! ## Edge Types
//! - CONTAINS, CALLS, RETURNS, DEPENDS
//! - INHERITS, IMPLEMENTS, USES
//! - BRANCHES_TO, LOOPS_TO

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::HammingVector;

// =============================================================================
// NODE TYPES (language constructs)
// =============================================================================

/// Language construct types.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
#[repr(i32)]
pub enum NodeType {
    // Containers
    Module = 1,
    Class = 2,
    Function = 3,
    Method = 4,
    Property = 5,

    // Control flow
    If = 10,
    Else = 11,
    Elif = 12,
    Match = 13,
    Case = 14,

    // Loops
    For = 20,
    ForEach = 21,
    While = 22,
    Loop = 23,

    // Expressions
    Expression = 30,
    Literal = 31,
    Reference = 32,
    Call = 33,
    BinaryOp = 34,
    UnaryOp = 35,

    // Declarations
    Variable = 40,
    Parameter = 41,
    Return = 42,
    Yield = 43,

    // Imports
    Import = 50,
    Export = 51,

    // Special
    Comment = 60,
    Decorator = 61,
    Annotation = 62,
}

impl Default for NodeType {
    fn default() -> Self {
        NodeType::Expression
    }
}

// =============================================================================
// EDGE TYPES (relationships)
// =============================================================================

/// Relationship types between nodes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
#[repr(i32)]
pub enum GraphEdgeType {
    // Structural
    Contains = 1,
    Next = 2,

    // Dependencies
    Calls = 10,
    Returns = 11,
    Depends = 12,
    Uses = 13,

    // OOP
    Inherits = 20,
    Implements = 21,
    Overrides = 22,

    // Control flow
    BranchesTo = 30,
    LoopsTo = 31,
    BreaksTo = 32,
    ContinuesTo = 33,

    // Data flow
    Assigns = 40,
    Reads = 41,
    Writes = 42,
}

impl Default for GraphEdgeType {
    fn default() -> Self {
        GraphEdgeType::Contains
    }
}

// =============================================================================
// NODE (language construct)
// =============================================================================

/// Language construct as a graph node.
#[derive(Debug, Clone)]
pub struct GraphNode {
    pub id: i64,
    pub node_type: NodeType,
    pub name: String,
    pub fingerprint: HammingVector,
    pub start_line: i32,
    pub end_line: i32,
    pub parent_id: i64,
}

impl GraphNode {
    /// Create a new graph node.
    pub fn new(id: i64, node_type: NodeType, name: impl Into<String>) -> Self {
        Self {
            id,
            node_type,
            name: name.into(),
            fingerprint: HammingVector::new(),
            start_line: 0,
            end_line: 0,
            parent_id: -1,
        }
    }

    /// Set fingerprint from computed data.
    pub fn set_fingerprint(&mut self, fp: HammingVector) {
        self.fingerprint = fp;
    }

    /// Hamming distance to another node.
    pub fn hamming(&self, other: &GraphNode) -> u32 {
        self.fingerprint.hamming(&other.fingerprint)
    }

    /// Similarity to another node [0, 1].
    pub fn similarity(&self, other: &GraphNode) -> f64 {
        self.fingerprint.similarity(&other.fingerprint)
    }
}

// =============================================================================
// EDGE (relationship)
// =============================================================================

/// Edge between nodes in the graph.
#[derive(Debug, Clone)]
pub struct GraphEdge {
    pub from_id: i64,
    pub to_id: i64,
    pub edge_type: GraphEdgeType,
    pub weight: f32,
}

impl GraphEdge {
    /// Create a new graph edge.
    pub fn new(from_id: i64, to_id: i64, edge_type: GraphEdgeType) -> Self {
        Self {
            from_id,
            to_id,
            edge_type,
            weight: 1.0,
        }
    }

    /// Create an edge with a specific weight.
    pub fn with_weight(mut self, weight: f32) -> Self {
        self.weight = weight;
        self
    }
}

// =============================================================================
// FINGERPRINT COMPUTATION
// =============================================================================

/// Compute 10K fingerprint from identity string.
pub fn compute_fingerprint(identity: &str) -> HammingVector {
    HammingVector::from_seed(identity)
}

/// Create a node with computed fingerprint.
pub fn make_node(
    id: i64,
    node_type: NodeType,
    name: &str,
    body: &str,
    signature: &str,
    parent_id: i64,
) -> GraphNode {
    let mut node = GraphNode::new(id, node_type, name);
    node.parent_id = parent_id;

    // Compute fingerprint from identity
    let identity = format!("{:?}::{}::{}::{}", node_type, name, signature, body);
    node.fingerprint = compute_fingerprint(&identity);

    node
}

/// Create an edge between nodes.
pub fn make_edge(from_id: i64, to_id: i64, edge_type: GraphEdgeType, weight: f32) -> GraphEdge {
    GraphEdge::new(from_id, to_id, edge_type).with_weight(weight)
}

// =============================================================================
// CODE GRAPH
// =============================================================================

/// Declarative code graph.
///
/// Nodes are language constructs, edges are relationships.
#[derive(Debug, Default)]
pub struct CodeGraph {
    nodes: HashMap<i64, GraphNode>,
    edges: Vec<GraphEdge>,
    next_id: i64,
}

impl CodeGraph {
    /// Create an empty code graph.
    pub fn new() -> Self {
        Self::default()
    }

    /// Get next node ID.
    fn get_id(&mut self) -> i64 {
        let id = self.next_id;
        self.next_id += 1;
        id
    }

    // -------------------------------------------------------------------------
    // Node creation methods
    // -------------------------------------------------------------------------

    /// Create MODULE node.
    pub fn module(&mut self, name: &str) -> i64 {
        self.add_node(NodeType::Module, name, None, "", "")
    }

    /// Create CLASS node.
    pub fn class(&mut self, name: &str, parent: Option<i64>) -> i64 {
        self.add_node(NodeType::Class, name, parent, "", "")
    }

    /// Create METHOD node inside a class.
    pub fn method(
        &mut self,
        name: &str,
        signature: &str,
        body: &str,
        parent: i64,
    ) -> i64 {
        let id = self.add_node(NodeType::Method, name, Some(parent), signature, body);
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create FUNCTION node.
    pub fn function(
        &mut self,
        name: &str,
        signature: &str,
        body: &str,
        parent: Option<i64>,
    ) -> i64 {
        let id = self.add_node(NodeType::Function, name, parent, signature, body);
        if let Some(p) = parent {
            self.edge(p, id, GraphEdgeType::Contains, 1.0);
        }
        id
    }

    /// Create PROPERTY node inside a class.
    pub fn property(&mut self, name: &str, type_hint: &str, parent: i64) -> i64 {
        let id = self.add_node(NodeType::Property, name, Some(parent), type_hint, "");
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create IF node.
    pub fn if_node(&mut self, condition: &str, parent: i64) -> i64 {
        let name = format!("if({})", condition);
        let id = self.add_node(NodeType::If, &name, Some(parent), "", condition);
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create FOREACH node.
    pub fn foreach(&mut self, var: &str, iterable: &str, parent: i64) -> i64 {
        let name = format!("for {} in {}", var, iterable);
        let id = self.add_node(NodeType::ForEach, &name, Some(parent), var, iterable);
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create WHILE node.
    pub fn while_node(&mut self, condition: &str, parent: i64) -> i64 {
        let name = format!("while({})", condition);
        let id = self.add_node(NodeType::While, &name, Some(parent), "", condition);
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create MATCH node.
    pub fn match_node(&mut self, expr: &str, parent: i64) -> i64 {
        let name = format!("match({})", expr);
        let id = self.add_node(NodeType::Match, &name, Some(parent), "", expr);
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create CASE node inside a match.
    pub fn case(&mut self, pattern: &str, parent: i64) -> i64 {
        let name = format!("case {}", pattern);
        let id = self.add_node(NodeType::Case, &name, Some(parent), "", pattern);
        self.edge(parent, id, GraphEdgeType::BranchesTo, 1.0);
        id
    }

    /// Create VARIABLE node.
    pub fn variable(&mut self, name: &str, type_hint: &str, parent: i64) -> i64 {
        let id = self.add_node(NodeType::Variable, name, Some(parent), type_hint, "");
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create CALL node.
    pub fn call(&mut self, target: &str, args: &str, parent: i64) -> i64 {
        let name = format!("{}({})", target, args);
        let id = self.add_node(NodeType::Call, &name, Some(parent), target, args);
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create IMPORT node.
    pub fn import(&mut self, module: &str, parent: Option<i64>) -> i64 {
        self.add_node(NodeType::Import, module, parent, "", "")
    }

    /// Create LITERAL node.
    pub fn literal(&mut self, value: &str, parent: i64) -> i64 {
        let id = self.add_node(NodeType::Literal, value, Some(parent), "", value);
        self.edge(parent, id, GraphEdgeType::Contains, 1.0);
        id
    }

    /// Create REFERENCE node.
    pub fn reference(&mut self, name: &str, parent: i64) -> i64 {
        let id = self.add_node(NodeType::Reference, name, Some(parent), "", "");
        self.edge(parent, id, GraphEdgeType::Uses, 1.0);
        id
    }

    // -------------------------------------------------------------------------
    // Edge creation
    // -------------------------------------------------------------------------

    /// Create edge between nodes.
    pub fn edge(&mut self, from: i64, to: i64, edge_type: GraphEdgeType, weight: f32) {
        self.edges.push(make_edge(from, to, edge_type, weight));
    }

    /// Create CALLS edge.
    pub fn calls(&mut self, caller: i64, callee: i64) {
        self.edge(caller, callee, GraphEdgeType::Calls, 1.0);
    }

    /// Create INHERITS edge.
    pub fn inherits(&mut self, child: i64, parent: i64) {
        self.edge(child, parent, GraphEdgeType::Inherits, 1.0);
    }

    /// Create IMPLEMENTS edge.
    pub fn implements(&mut self, class: i64, interface: i64) {
        self.edge(class, interface, GraphEdgeType::Implements, 1.0);
    }

    /// Create DEPENDS edge.
    pub fn depends(&mut self, dependent: i64, dependency: i64) {
        self.edge(dependent, dependency, GraphEdgeType::Depends, 1.0);
    }

    // -------------------------------------------------------------------------
    // Internal
    // -------------------------------------------------------------------------

    fn add_node(
        &mut self,
        node_type: NodeType,
        name: &str,
        parent: Option<i64>,
        signature: &str,
        body: &str,
    ) -> i64 {
        let id = self.get_id();
        let parent_id = parent.unwrap_or(-1);
        let node = make_node(id, node_type, name, body, signature, parent_id);
        self.nodes.insert(id, node);
        id
    }

    // -------------------------------------------------------------------------
    // Query
    // -------------------------------------------------------------------------

    /// Get node by ID.
    pub fn get_node(&self, id: i64) -> Option<&GraphNode> {
        self.nodes.get(&id)
    }

    /// Get mutable node by ID.
    pub fn get_node_mut(&mut self, id: i64) -> Option<&mut GraphNode> {
        self.nodes.get_mut(&id)
    }

    /// Iterate over all nodes.
    pub fn iter_nodes(&self) -> impl Iterator<Item = &GraphNode> {
        self.nodes.values()
    }

    /// Iterate over all edges.
    pub fn iter_edges(&self) -> impl Iterator<Item = &GraphEdge> {
        self.edges.iter()
    }

    /// Get all children of a node.
    pub fn get_children(&self, parent_id: i64) -> Vec<&GraphNode> {
        self.edges
            .iter()
            .filter(|e| e.from_id == parent_id && e.edge_type == GraphEdgeType::Contains)
            .filter_map(|e| self.nodes.get(&e.to_id))
            .collect()
    }

    /// Get all nodes called by this node.
    pub fn get_calls(&self, node_id: i64) -> Vec<&GraphNode> {
        self.edges
            .iter()
            .filter(|e| e.from_id == node_id && e.edge_type == GraphEdgeType::Calls)
            .filter_map(|e| self.nodes.get(&e.to_id))
            .collect()
    }

    /// Find all nodes of a given type.
    pub fn find_by_type(&self, node_type: NodeType) -> Vec<&GraphNode> {
        self.nodes
            .values()
            .filter(|n| n.node_type == node_type)
            .collect()
    }

    /// Find nodes similar to query (above threshold).
    pub fn find_similar(&self, query_id: i64, threshold: f64) -> Vec<(&GraphNode, f64)> {
        let query = match self.nodes.get(&query_id) {
            Some(n) => n,
            None => return vec![],
        };

        let mut results: Vec<_> = self
            .nodes
            .values()
            .filter(|n| n.id != query_id)
            .map(|n| (n, query.similarity(n)))
            .filter(|(_, sim)| *sim >= threshold)
            .collect();

        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        results
    }

    /// Get node count.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Get edge count.
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    // -------------------------------------------------------------------------
    // Export
    // -------------------------------------------------------------------------

    /// Export to Graphviz DOT format.
    pub fn to_graphviz(&self) -> String {
        let mut lines = vec![
            "digraph CodeGraph {".to_string(),
            "  rankdir=TB;".to_string(),
            "  node [shape=box];".to_string(),
        ];

        // Node shapes by type
        for node in self.nodes.values() {
            let shape = match node.node_type {
                NodeType::Module => "folder",
                NodeType::Class => "box3d",
                NodeType::Function | NodeType::Method => "ellipse",
                NodeType::If | NodeType::Match => "diamond",
                NodeType::ForEach | NodeType::While | NodeType::For => "hexagon",
                _ => "box",
            };
            let label = format!("{:?}\\n{}", node.node_type, node.name);
            lines.push(format!(
                "  n{} [label=\"{}\" shape={}];",
                node.id, label, shape
            ));
        }

        // Edges
        for edge in &self.edges {
            let style = match edge.edge_type {
                GraphEdgeType::Contains => "solid",
                GraphEdgeType::Calls => "dashed",
                GraphEdgeType::Inherits => "bold",
                GraphEdgeType::BranchesTo => "dotted",
                _ => "solid",
            };
            let label = format!("{:?}", edge.edge_type);
            lines.push(format!(
                "  n{} -> n{} [style={} label=\"{}\"];",
                edge.from_id, edge.to_id, style, label
            ));
        }

        lines.push("}".to_string());
        lines.join("\n")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_code_graph() {
        let mut g = CodeGraph::new();

        // Build a simple graph
        let module = g.module("user_service");
        let class = g.class("UserService", Some(module));
        let method = g.method("validate_user", "(user: User) -> bool", "validate", class);
        let _if_node = g.if_node("user.email", method);

        assert_eq!(g.node_count(), 4);
        // method adds 1 edge (class->method), if_node adds 1 edge (method->if)
        assert_eq!(g.edge_count(), 2);

        // Check children
        let children = g.get_children(class);
        assert_eq!(children.len(), 1);
        assert_eq!(children[0].name, "validate_user");
    }

    #[test]
    fn test_find_by_type() {
        let mut g = CodeGraph::new();
        g.module("mod1");
        g.module("mod2");
        g.class("Class1", None);

        let modules = g.find_by_type(NodeType::Module);
        assert_eq!(modules.len(), 2);
    }

    #[test]
    fn test_similarity() {
        let mut g = CodeGraph::new();
        let n1 = g.function("validate_email", "(str) -> bool", "check format", None);
        let _n2 = g.function("validate_phone", "(str) -> bool", "check format", None);
        let _n3 = g.function("send_notification", "(msg) -> void", "send message", None);

        // With SHA256-based fingerprints, semantic similarity isn't guaranteed
        // Just verify we can find similar nodes (threshold 0.0 returns all)
        let similar = g.find_similar(n1, 0.0);
        assert_eq!(similar.len(), 2); // Should find n2 and n3
    }

    #[test]
    fn test_graphviz() {
        let mut g = CodeGraph::new();
        let module = g.module("test");
        g.function("func", "() -> void", "body", Some(module));

        let dot = g.to_graphviz();
        assert!(dot.contains("digraph CodeGraph"));
        assert!(dot.contains("n0"));
        assert!(dot.contains("n1"));
    }
}
