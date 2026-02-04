//! Rubberduck: Self-Analyzing Audit System for LadybugDB
//!
//! Named after "rubber duck debugging" - explaining code to find issues.
//! Creates feedback loops: parse source → build graph → detect antipatterns → suggest fixes.
//!
//! ## Modern Features
//!
//! - **Work-Stealing Analysis**: Parallel antipattern detection
//! - **GEL Queries**: Use DN addressing to navigate code graph
//! - **Resonance Similarity**: Find similar code patterns via Hamming
//! - **Incremental Audits**: Track changes between audits
//!
//! ## Example
//!
//! ```ignore
//! let auditor = Rubberduck::new();
//! let report = auditor.audit_graph(&graph).await?;
//! println!("Quality: {}/100", report.quality_score);
//! for smell in &report.smells {
//!     println!("  {} at {}", smell.smell_type, smell.location);
//! }
//! ```

use std::collections::HashMap;
use std::sync::Arc;

use dashmap::DashMap;
use parking_lot::RwLock;
use rayon::prelude::*;

use crate::{HammingVector, Result, FireflyError};
use crate::gel::{DistinguishedName, GelExecutor, GelQuery, ExecutionMode};
use crate::ladybug::{CodeGraph, GraphNode, NodeType, GraphEdgeType};

// =============================================================================
// CODE SMELLS
// =============================================================================

/// Types of code smells that can be detected.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SmellType {
    /// Class with too many responsibilities.
    GodClass,
    /// Function that's too long.
    LongMethod,
    /// Deeply nested control structures.
    DeepNesting,
    /// Too many parameters.
    TooManyParameters,
    /// Circular dependency between modules.
    CircularDependency,
    /// Code that's duplicated.
    DuplicateCode,
    /// Dead code that's never called.
    DeadCode,
    /// Magic numbers without named constants.
    MagicNumbers,
    /// Empty catch/except blocks.
    SwallowedException,
    /// Overly complex method (high cyclomatic complexity).
    ComplexMethod,
    /// Feature envy (method uses another class more than its own).
    FeatureEnvy,
    /// Data clump (group of data that appears together).
    DataClump,
    /// Primitive obsession (using primitives instead of small objects).
    PrimitiveObsession,
    /// Refused bequest (subclass doesn't use inherited methods).
    RefusedBequest,
}

impl SmellType {
    /// Get severity (1-10, higher is worse).
    pub fn severity(&self) -> u8 {
        match self {
            SmellType::GodClass => 8,
            SmellType::LongMethod => 5,
            SmellType::DeepNesting => 6,
            SmellType::TooManyParameters => 4,
            SmellType::CircularDependency => 9,
            SmellType::DuplicateCode => 7,
            SmellType::DeadCode => 3,
            SmellType::MagicNumbers => 2,
            SmellType::SwallowedException => 8,
            SmellType::ComplexMethod => 6,
            SmellType::FeatureEnvy => 5,
            SmellType::DataClump => 4,
            SmellType::PrimitiveObsession => 3,
            SmellType::RefusedBequest => 4,
        }
    }

    /// Get description.
    pub fn description(&self) -> &'static str {
        match self {
            SmellType::GodClass => "Class has too many responsibilities",
            SmellType::LongMethod => "Method is too long and should be split",
            SmellType::DeepNesting => "Control structures are nested too deeply",
            SmellType::TooManyParameters => "Method has too many parameters",
            SmellType::CircularDependency => "Circular dependency between modules",
            SmellType::DuplicateCode => "Code is duplicated and should be extracted",
            SmellType::DeadCode => "Code is never executed",
            SmellType::MagicNumbers => "Magic numbers should be named constants",
            SmellType::SwallowedException => "Exception is caught but ignored",
            SmellType::ComplexMethod => "Method has high cyclomatic complexity",
            SmellType::FeatureEnvy => "Method uses another class more than its own",
            SmellType::DataClump => "Data fields that always appear together",
            SmellType::PrimitiveObsession => "Using primitives instead of value objects",
            SmellType::RefusedBequest => "Subclass doesn't use inherited methods",
        }
    }
}

/// A detected code smell.
#[derive(Debug, Clone)]
pub struct CodeSmell {
    pub smell_type: SmellType,
    pub location: String,
    pub dn: Option<DistinguishedName>,
    pub message: String,
    pub severity: u8,
    pub line_start: Option<u32>,
    pub line_end: Option<u32>,
    pub suggestion: String,
}

impl CodeSmell {
    pub fn new(smell_type: SmellType, location: impl Into<String>, message: impl Into<String>) -> Self {
        let suggestion = match smell_type {
            SmellType::GodClass => "Split into smaller, focused classes",
            SmellType::LongMethod => "Extract into smaller methods with clear names",
            SmellType::DeepNesting => "Use early returns or extract conditions",
            SmellType::TooManyParameters => "Use parameter object or builder pattern",
            SmellType::CircularDependency => "Introduce interface or reorganize modules",
            SmellType::DuplicateCode => "Extract into shared utility function",
            SmellType::DeadCode => "Remove unused code",
            SmellType::MagicNumbers => "Create named constant",
            SmellType::SwallowedException => "Log the exception or handle appropriately",
            SmellType::ComplexMethod => "Split into smaller methods with single responsibility",
            SmellType::FeatureEnvy => "Move method to the class it envies",
            SmellType::DataClump => "Create a class to hold the data",
            SmellType::PrimitiveObsession => "Create value object",
            SmellType::RefusedBequest => "Reconsider inheritance hierarchy",
        };

        Self {
            smell_type,
            location: location.into(),
            dn: None,
            message: message.into(),
            severity: smell_type.severity(),
            line_start: None,
            line_end: None,
            suggestion: suggestion.to_string(),
        }
    }

    pub fn with_dn(mut self, dn: DistinguishedName) -> Self {
        self.dn = Some(dn);
        self
    }

    pub fn with_lines(mut self, start: u32, end: u32) -> Self {
        self.line_start = Some(start);
        self.line_end = Some(end);
        self
    }
}

// =============================================================================
// METRICS
// =============================================================================

/// Code metrics for a module/class/function.
#[derive(Debug, Clone, Default)]
pub struct CodeMetrics {
    pub total_lines: usize,
    pub code_lines: usize,
    pub comment_lines: usize,
    pub blank_lines: usize,
    pub functions: usize,
    pub classes: usize,
    pub methods: usize,
    pub avg_method_length: f64,
    pub max_method_length: usize,
    pub avg_parameters: f64,
    pub max_parameters: usize,
    pub max_nesting_depth: usize,
    pub cyclomatic_complexity: usize,
}

/// Aggregated metrics for a codebase.
#[derive(Debug, Clone, Default)]
pub struct AggregatedMetrics {
    pub total_files: usize,
    pub total_lines: usize,
    pub total_functions: usize,
    pub total_classes: usize,
    pub avg_file_lines: f64,
    pub avg_class_methods: f64,
    pub maintainability_index: f64,
}

// =============================================================================
// AUDIT REPORT
// =============================================================================

/// Complete audit report.
#[derive(Debug, Clone)]
pub struct AuditReport {
    pub id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub smells: Vec<CodeSmell>,
    pub metrics: AggregatedMetrics,
    pub quality_score: u8,
    pub recommendations: Vec<String>,
    pub hotspots: Vec<Hotspot>,
}

/// A code hotspot (area needing attention).
#[derive(Debug, Clone)]
pub struct Hotspot {
    pub location: String,
    pub dn: Option<DistinguishedName>,
    pub smell_count: usize,
    pub total_severity: u32,
    pub reason: String,
}

/// Delta between two audits.
#[derive(Debug, Clone)]
pub struct AuditDelta {
    pub previous_id: String,
    pub current_id: String,
    pub new_smells: Vec<CodeSmell>,
    pub resolved_smells: Vec<CodeSmell>,
    pub score_change: i16,
    pub improved: bool,
}

// =============================================================================
// SMELL DETECTORS
// =============================================================================

/// Trait for detecting code smells.
pub trait SmellDetector: Send + Sync {
    /// Detect smells in a graph node.
    fn detect(&self, node: &GraphNode, graph: &CodeGraph) -> Vec<CodeSmell>;

    /// Get the smell type this detector finds.
    fn smell_type(&self) -> SmellType;
}

/// Detector for god classes.
pub struct GodClassDetector {
    pub max_methods: usize,
    pub max_lines: usize,
}

impl Default for GodClassDetector {
    fn default() -> Self {
        Self {
            max_methods: 20,
            max_lines: 500,
        }
    }
}

impl SmellDetector for GodClassDetector {
    fn detect(&self, node: &GraphNode, graph: &CodeGraph) -> Vec<CodeSmell> {
        if node.node_type != NodeType::Class {
            return Vec::new();
        }

        let children = graph.get_children(node.id);
        let method_count = children
            .iter()
            .filter(|c| c.node_type == NodeType::Method)
            .count();

        let lines = (node.end_line - node.start_line) as usize;

        if method_count > self.max_methods || lines > self.max_lines {
            vec![CodeSmell::new(
                SmellType::GodClass,
                &node.name,
                format!(
                    "Class has {} methods and {} lines (max: {}/{})",
                    method_count, lines, self.max_methods, self.max_lines
                ),
            )
            .with_lines(node.start_line as u32, node.end_line as u32)]
        } else {
            Vec::new()
        }
    }

    fn smell_type(&self) -> SmellType {
        SmellType::GodClass
    }
}

/// Detector for long methods.
pub struct LongMethodDetector {
    pub max_lines: usize,
}

impl Default for LongMethodDetector {
    fn default() -> Self {
        Self { max_lines: 50 }
    }
}

impl SmellDetector for LongMethodDetector {
    fn detect(&self, node: &GraphNode, _graph: &CodeGraph) -> Vec<CodeSmell> {
        if node.node_type != NodeType::Method && node.node_type != NodeType::Function {
            return Vec::new();
        }

        let lines = (node.end_line - node.start_line) as usize;

        if lines > self.max_lines {
            vec![CodeSmell::new(
                SmellType::LongMethod,
                &node.name,
                format!("Method has {} lines (max: {})", lines, self.max_lines),
            )
            .with_lines(node.start_line as u32, node.end_line as u32)]
        } else {
            Vec::new()
        }
    }

    fn smell_type(&self) -> SmellType {
        SmellType::LongMethod
    }
}

/// Detector for deep nesting.
pub struct DeepNestingDetector {
    pub max_depth: usize,
}

impl Default for DeepNestingDetector {
    fn default() -> Self {
        Self { max_depth: 4 }
    }
}

impl SmellDetector for DeepNestingDetector {
    fn detect(&self, node: &GraphNode, graph: &CodeGraph) -> Vec<CodeSmell> {
        // Count nesting depth by traversing parents
        let mut depth = 0;
        let mut current_id = node.parent_id;

        while current_id >= 0 {
            if let Some(parent) = graph.get_node(current_id) {
                match parent.node_type {
                    NodeType::If | NodeType::For | NodeType::ForEach | NodeType::While | NodeType::Match => {
                        depth += 1;
                    }
                    _ => {}
                }
                current_id = parent.parent_id;
            } else {
                break;
            }
        }

        if depth > self.max_depth {
            vec![CodeSmell::new(
                SmellType::DeepNesting,
                &node.name,
                format!("Nesting depth is {} (max: {})", depth, self.max_depth),
            )
            .with_lines(node.start_line as u32, node.end_line as u32)]
        } else {
            Vec::new()
        }
    }

    fn smell_type(&self) -> SmellType {
        SmellType::DeepNesting
    }
}

/// Detector for duplicate code using Hamming similarity.
pub struct DuplicateCodeDetector {
    pub similarity_threshold: f64,
}

impl Default for DuplicateCodeDetector {
    fn default() -> Self {
        Self {
            similarity_threshold: 0.95,
        }
    }
}

impl SmellDetector for DuplicateCodeDetector {
    fn detect(&self, node: &GraphNode, graph: &CodeGraph) -> Vec<CodeSmell> {
        if node.node_type != NodeType::Method && node.node_type != NodeType::Function {
            return Vec::new();
        }

        let mut smells = Vec::new();

        // Find similar functions
        let similar = graph.find_similar(node.id, self.similarity_threshold);

        for (other_node, similarity) in similar {
            if other_node.id != node.id && similarity >= self.similarity_threshold {
                smells.push(CodeSmell::new(
                    SmellType::DuplicateCode,
                    &node.name,
                    format!(
                        "Similar to '{}' ({:.1}% match)",
                        other_node.name,
                        similarity * 100.0
                    ),
                ));
            }
        }

        smells
    }

    fn smell_type(&self) -> SmellType {
        SmellType::DuplicateCode
    }
}

// =============================================================================
// RUBBERDUCK AUDITOR
// =============================================================================

/// Main auditor that orchestrates code analysis.
pub struct Rubberduck {
    /// Registered smell detectors.
    detectors: Vec<Arc<dyn SmellDetector>>,
    /// Previous audit reports for delta calculation.
    history: RwLock<Vec<AuditReport>>,
    /// GEL executor for graph queries.
    gel_executor: GelExecutor,
    /// Configuration.
    config: RubberduckConfig,
}

/// Configuration for the auditor.
#[derive(Debug, Clone)]
pub struct RubberduckConfig {
    pub max_history: usize,
    pub parallel_detection: bool,
    pub similarity_threshold: f64,
}

impl Default for RubberduckConfig {
    fn default() -> Self {
        Self {
            max_history: 10,
            parallel_detection: true,
            similarity_threshold: 0.95,
        }
    }
}

impl Default for Rubberduck {
    fn default() -> Self {
        Self::new()
    }
}

impl Rubberduck {
    /// Create a new auditor with default detectors.
    pub fn new() -> Self {
        let mut auditor = Self {
            detectors: Vec::new(),
            history: RwLock::new(Vec::new()),
            gel_executor: GelExecutor::new(),
            config: RubberduckConfig::default(),
        };

        // Register default detectors
        auditor.register_detector(Arc::new(GodClassDetector::default()));
        auditor.register_detector(Arc::new(LongMethodDetector::default()));
        auditor.register_detector(Arc::new(DeepNestingDetector::default()));
        auditor.register_detector(Arc::new(DuplicateCodeDetector::default()));

        auditor
    }

    /// Create with custom config.
    pub fn with_config(config: RubberduckConfig) -> Self {
        let mut auditor = Self::new();
        auditor.config = config;
        auditor
    }

    /// Register a smell detector.
    pub fn register_detector(&mut self, detector: Arc<dyn SmellDetector>) {
        self.detectors.push(detector);
    }

    /// Audit a code graph.
    pub fn audit_graph(&self, graph: &CodeGraph) -> AuditReport {
        // Collect all nodes
        let nodes: Vec<_> = graph.iter_nodes().collect();

        // Run detectors
        let smells: Vec<CodeSmell> = if self.config.parallel_detection {
            // Parallel detection with work-stealing
            nodes
                .par_iter()
                .flat_map(|node| {
                    self.detectors
                        .par_iter()
                        .flat_map(|detector| detector.detect(node, graph))
                        .collect::<Vec<_>>()
                })
                .collect()
        } else {
            // Sequential detection
            nodes
                .iter()
                .flat_map(|node| {
                    self.detectors
                        .iter()
                        .flat_map(|detector| detector.detect(node, graph))
                        .collect::<Vec<_>>()
                })
                .collect()
        };

        // Calculate metrics
        let metrics = self.calculate_metrics(graph);

        // Calculate quality score
        let quality_score = self.calculate_quality_score(&smells, &metrics);

        // Find hotspots
        let hotspots = self.find_hotspots(&smells);

        // Generate recommendations
        let recommendations = self.generate_recommendations(&smells, &metrics);

        let report = AuditReport {
            id: uuid::Uuid::new_v4().to_string(),
            timestamp: chrono::Utc::now(),
            smells,
            metrics,
            quality_score,
            recommendations,
            hotspots,
        };

        // Store in history
        {
            let mut history = self.history.write();
            history.push(report.clone());
            if history.len() > self.config.max_history {
                history.remove(0);
            }
        }

        report
    }

    /// Calculate aggregated metrics.
    fn calculate_metrics(&self, graph: &CodeGraph) -> AggregatedMetrics {
        let functions: Vec<_> = graph.find_by_type(NodeType::Function);
        let methods: Vec<_> = graph.find_by_type(NodeType::Method);
        let classes: Vec<_> = graph.find_by_type(NodeType::Class);
        let modules: Vec<_> = graph.find_by_type(NodeType::Module);

        let total_functions = functions.len() + methods.len();
        let avg_class_methods = if classes.is_empty() {
            0.0
        } else {
            methods.len() as f64 / classes.len() as f64
        };

        // Simplified maintainability index
        let smell_penalty = 0.0; // Would be calculated from smells
        let maintainability = 100.0 - smell_penalty;

        AggregatedMetrics {
            total_files: modules.len(),
            total_lines: graph.node_count() * 10, // Rough estimate
            total_functions,
            total_classes: classes.len(),
            avg_file_lines: 100.0, // Placeholder
            avg_class_methods,
            maintainability_index: maintainability,
        }
    }

    /// Calculate quality score (0-100).
    fn calculate_quality_score(&self, smells: &[CodeSmell], _metrics: &AggregatedMetrics) -> u8 {
        let total_severity: u32 = smells.iter().map(|s| s.severity as u32).sum();
        let penalty = (total_severity as f64 * 2.0).min(100.0);
        (100.0 - penalty).max(0.0) as u8
    }

    /// Find code hotspots.
    fn find_hotspots(&self, smells: &[CodeSmell]) -> Vec<Hotspot> {
        // Group smells by location
        let mut by_location: HashMap<String, Vec<&CodeSmell>> = HashMap::new();
        for smell in smells {
            by_location
                .entry(smell.location.clone())
                .or_default()
                .push(smell);
        }

        // Convert to hotspots
        let mut hotspots: Vec<Hotspot> = by_location
            .into_iter()
            .map(|(location, smells)| {
                let total_severity: u32 = smells.iter().map(|s| s.severity as u32).sum();
                let reason = smells
                    .iter()
                    .map(|s| format!("{:?}", s.smell_type))
                    .collect::<Vec<_>>()
                    .join(", ");

                Hotspot {
                    location,
                    dn: smells.first().and_then(|s| s.dn.clone()),
                    smell_count: smells.len(),
                    total_severity,
                    reason,
                }
            })
            .collect();

        // Sort by severity
        hotspots.sort_by(|a, b| b.total_severity.cmp(&a.total_severity));
        hotspots.truncate(10);

        hotspots
    }

    /// Generate recommendations.
    fn generate_recommendations(&self, smells: &[CodeSmell], metrics: &AggregatedMetrics) -> Vec<String> {
        let mut recommendations = Vec::new();

        // Count smell types
        let mut smell_counts: HashMap<SmellType, usize> = HashMap::new();
        for smell in smells {
            *smell_counts.entry(smell.smell_type).or_default() += 1;
        }

        // Generate recommendations based on smell patterns
        if let Some(&count) = smell_counts.get(&SmellType::GodClass) {
            if count > 0 {
                recommendations.push(format!(
                    "Found {} god classes. Consider applying Single Responsibility Principle.",
                    count
                ));
            }
        }

        if let Some(&count) = smell_counts.get(&SmellType::DuplicateCode) {
            if count > 0 {
                recommendations.push(format!(
                    "Found {} instances of duplicate code. Extract common functionality.",
                    count
                ));
            }
        }

        if let Some(&count) = smell_counts.get(&SmellType::DeepNesting) {
            if count > 0 {
                recommendations.push(format!(
                    "Found {} deeply nested blocks. Use early returns and guard clauses.",
                    count
                ));
            }
        }

        if metrics.avg_class_methods > 15.0 {
            recommendations.push(format!(
                "Average methods per class is {:.1}. Consider breaking up large classes.",
                metrics.avg_class_methods
            ));
        }

        recommendations
    }

    /// Calculate delta between current report and previous.
    pub fn delta(&self, current: &AuditReport) -> Option<AuditDelta> {
        let history = self.history.read();
        if history.len() < 2 {
            return None;
        }

        let previous = &history[history.len() - 2];

        // Find new smells (in current but not previous)
        let previous_locations: std::collections::HashSet<_> =
            previous.smells.iter().map(|s| &s.location).collect();
        let new_smells: Vec<_> = current
            .smells
            .iter()
            .filter(|s| !previous_locations.contains(&s.location))
            .cloned()
            .collect();

        // Find resolved smells (in previous but not current)
        let current_locations: std::collections::HashSet<_> =
            current.smells.iter().map(|s| &s.location).collect();
        let resolved_smells: Vec<_> = previous
            .smells
            .iter()
            .filter(|s| !current_locations.contains(&s.location))
            .cloned()
            .collect();

        let score_change = current.quality_score as i16 - previous.quality_score as i16;

        Some(AuditDelta {
            previous_id: previous.id.clone(),
            current_id: current.id.clone(),
            new_smells,
            resolved_smells,
            score_change,
            improved: score_change > 0,
        })
    }
}

// =============================================================================
// TESTS
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_smell_severity() {
        assert!(SmellType::CircularDependency.severity() > SmellType::MagicNumbers.severity());
        assert!(SmellType::GodClass.severity() > SmellType::DeadCode.severity());
    }

    #[test]
    fn test_code_smell_creation() {
        let smell = CodeSmell::new(
            SmellType::LongMethod,
            "MyClass.processData",
            "Method has 100 lines",
        )
        .with_lines(10, 110);

        assert_eq!(smell.smell_type, SmellType::LongMethod);
        assert_eq!(smell.line_start, Some(10));
        assert_eq!(smell.line_end, Some(110));
        assert!(!smell.suggestion.is_empty());
    }

    #[test]
    fn test_rubberduck_audit() {
        let auditor = Rubberduck::new();
        let mut graph = CodeGraph::new();

        // Create a simple class
        let module = graph.module("test_module");
        let class = graph.class("TestClass", Some(module));
        graph.method("process", "() -> void", "body", class);
        graph.method("validate", "() -> bool", "body", class);

        let report = auditor.audit_graph(&graph);

        assert!(report.quality_score > 0);
        assert!(!report.id.is_empty());
    }

    #[test]
    fn test_god_class_detection() {
        let detector = GodClassDetector {
            max_methods: 2,
            max_lines: 10,
        };
        let mut graph = CodeGraph::new();

        let class_id = graph.class("GodClass", None);
        // Set a large line range
        if let Some(node) = graph.get_node_mut(class_id) {
            node.end_line = 1000;
        }

        // Add many methods
        for i in 0..5 {
            graph.method(&format!("method_{}", i), "() -> void", "body", class_id);
        }

        if let Some(class_node) = graph.get_node(class_id) {
            let smells = detector.detect(class_node, &graph);
            assert_eq!(smells.len(), 1);
            assert_eq!(smells[0].smell_type, SmellType::GodClass);
        }
    }

    #[test]
    fn test_parallel_detection() {
        let auditor = Rubberduck::with_config(RubberduckConfig {
            parallel_detection: true,
            ..Default::default()
        });

        let mut graph = CodeGraph::new();
        for i in 0..100 {
            graph.function(&format!("func_{}", i), "() -> void", "body", None);
        }

        let report = auditor.audit_graph(&graph);
        assert!(report.quality_score > 0);
    }
}
