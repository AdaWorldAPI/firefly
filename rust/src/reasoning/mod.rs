//! Reasoning Module: Failure explanation and suggestions.
//!
//! Given a failed execution:
//! 1. Find the failed node in the execution trace
//! 2. Query upstream nodes: what fed into it?
//! 3. Query similar failures: seen this pattern before?
//! 4. Generate explanation from graph structure
//!
//! Uses Hamming similarity to find similar past failures,
//! graph traversal to identify root causes.

use std::sync::Arc;

use crate::Result;
use crate::storage::FireflyStore;

// =============================================================================
// FAILURE EXPLANATION
// =============================================================================

/// Structured explanation of a failure.
#[derive(Debug, Clone)]
pub struct FailureExplanation {
    pub failed_node_id: String,
    pub error: String,
    pub timestamp: String,
    pub upstream_nodes: Vec<String>,
    pub similar_failures: Vec<SimilarFailure>,
    pub root_cause: String,
    pub suggestion: String,
}

/// A similar past failure.
#[derive(Debug, Clone)]
pub struct SimilarFailure {
    pub node_id: String,
    pub error: String,
    pub timestamp: String,
    pub execution_id: String,
}

/// Execution trace step.
#[derive(Debug, Clone)]
pub struct TraceStep {
    pub node_id: String,
    pub duration_ms: f64,
    pub success: bool,
    pub error: Option<String>,
}

/// Analyzed execution trace.
#[derive(Debug, Clone)]
pub struct TraceAnalysis {
    pub steps: Vec<TraceStep>,
    pub total_ms: f64,
    pub failed_at_step: Option<usize>,
}

// =============================================================================
// FAILURE EXPLAINER
// =============================================================================

/// Explain graph execution failures.
///
/// Combines graph traversal with similarity search
/// and analytics to produce human-readable explanations.
pub struct FailureExplainer {
    store: Arc<FireflyStore>,
}

impl FailureExplainer {
    /// Create a new failure explainer.
    pub fn new(store: Arc<FireflyStore>) -> Self {
        Self { store }
    }

    /// Explain a specific failure.
    pub async fn explain_failure(
        &self,
        node_id: &str,
        error: &str,
        timestamp: &str,
        _execution_id: &str,
    ) -> Result<FailureExplanation> {
        // 1. Get upstream nodes (what fed into the failure)
        let upstream = self.store.get_upstream_nodes(node_id, 3).await?;

        // 2. Find similar past failures (placeholder - would query execution_log)
        let similar = Vec::new(); // TODO: Implement similar failure search

        // 3. Analyze the execution trace (placeholder)
        let trace = TraceAnalysis {
            steps: Vec::new(),
            total_ms: 0.0,
            failed_at_step: None,
        };

        // 4. Generate root cause hypothesis
        let root_cause = self.hypothesize_root_cause(node_id, error, &upstream, &similar, &trace);

        // 5. Generate suggestion
        let suggestion = self.generate_suggestion(node_id, error, &similar, &root_cause);

        Ok(FailureExplanation {
            failed_node_id: node_id.to_string(),
            error: error.to_string(),
            timestamp: timestamp.to_string(),
            upstream_nodes: upstream,
            similar_failures: similar,
            root_cause,
            suggestion,
        })
    }

    /// Generate a root cause hypothesis from available data.
    fn hypothesize_root_cause(
        &self,
        node_id: &str,
        error: &str,
        upstream: &[String],
        similar: &[SimilarFailure],
        trace: &TraceAnalysis,
    ) -> String {
        let error_lower = error.to_lowercase();
        let mut parts = Vec::new();

        // Check error type
        if error_lower.contains("blank")
            || error_lower.contains("null")
            || error_lower.contains("empty")
        {
            parts.push(format!("Missing required input for {}", node_id));
            if !upstream.is_empty() {
                let upstream_str = upstream
                    .iter()
                    .take(3)
                    .cloned()
                    .collect::<Vec<_>>()
                    .join(" → ");
                parts.push(format!("Data should flow from: {}", upstream_str));
            }
        } else if error_lower.contains("too short") || error_lower.contains("too long") {
            parts.push(format!("Length constraint violation at {}", node_id));
        } else if error_lower.contains("unique") || error_lower.contains("duplicate") {
            parts.push(format!("Uniqueness constraint violation at {}", node_id));
        } else {
            parts.push(format!("Execution error at {}: {}", node_id, error));
        }

        // Check for patterns in similar failures
        let same_node_failures = similar.iter().filter(|s| s.node_id == node_id).count();
        if same_node_failures >= 2 {
            parts.push(format!(
                "This node has failed {} times before — recurring issue",
                same_node_failures
            ));
        }

        // Check trace
        if trace.failed_at_step == Some(0) {
            parts.push("Failed at very first step — likely bad input data".to_string());
        }

        if parts.is_empty() {
            format!("Unknown failure at {}: {}", node_id, error)
        } else {
            parts.join(". ")
        }
    }

    /// Generate actionable suggestion.
    fn generate_suggestion(
        &self,
        node_id: &str,
        _error: &str,
        _similar: &[SimilarFailure],
        root_cause: &str,
    ) -> String {
        let root_cause_lower = root_cause.to_lowercase();

        if root_cause_lower.contains("missing") || root_cause_lower.contains("required") {
            format!(
                "Ensure all required fields are provided before {} executes",
                node_id
            )
        } else if root_cause_lower.contains("recurring") {
            format!(
                "Node {} has a systemic issue — consider adding input validation upstream",
                node_id
            )
        } else if root_cause_lower.contains("length") {
            format!("Check field length constraints at {}", node_id)
        } else {
            format!(
                "Review the execution path leading to {} and verify input data",
                node_id
            )
        }
    }
}

// =============================================================================
// SUGGESTION ENGINE (placeholder for future expansion)
// =============================================================================

/// Suggestion types.
#[derive(Debug, Clone)]
pub enum SuggestionType {
    /// Add validation node upstream.
    AddValidation { before_node: String, validation: String },
    /// Add retry logic.
    AddRetry { node: String, max_retries: u32 },
    /// Add fallback path.
    AddFallback { node: String, fallback_node: String },
    /// Modify input schema.
    ModifySchema { node: String, changes: String },
}

/// A suggested fix for a failure.
#[derive(Debug, Clone)]
pub struct Suggestion {
    pub suggestion_type: SuggestionType,
    pub description: String,
    pub confidence: f64,
}

// =============================================================================
// OPTIMIZER (placeholder for future expansion)
// =============================================================================

/// Optimization types.
#[derive(Debug, Clone)]
pub enum OptimizationType {
    /// Parallelize independent nodes.
    Parallelize { nodes: Vec<String> },
    /// Cache expensive computation.
    Cache { node: String, ttl_seconds: u64 },
    /// Batch similar operations.
    Batch { nodes: Vec<String> },
    /// Remove unused nodes.
    Prune { nodes: Vec<String> },
}

/// An optimization suggestion.
#[derive(Debug, Clone)]
pub struct Optimization {
    pub optimization_type: OptimizationType,
    pub description: String,
    pub estimated_improvement: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_explain_failure() {
        let store = Arc::new(FireflyStore::in_memory());
        let explainer = FailureExplainer::new(store);

        let explanation = explainer
            .explain_failure("validate_email", "email can't be blank", "2024-01-01T00:00:00Z", "exec1")
            .await
            .unwrap();

        assert_eq!(explanation.failed_node_id, "validate_email");
        assert!(explanation.root_cause.contains("Missing required input"));
        assert!(explanation.suggestion.contains("required fields"));
    }

    #[tokio::test]
    async fn test_explain_length_error() {
        let store = Arc::new(FireflyStore::in_memory());
        let explainer = FailureExplainer::new(store);

        let explanation = explainer
            .explain_failure("validate_name", "name is too short", "2024-01-01T00:00:00Z", "exec1")
            .await
            .unwrap();

        assert!(explanation.root_cause.contains("Length constraint"));
        assert!(explanation.suggestion.contains("length constraints"));
    }
}
