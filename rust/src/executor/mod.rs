//! Firefly Executor: Watch nodes glow as execution flows through the graph.
//!
//! The executor:
//! 1. Loads the execution graph from storage
//! 2. Plans execution (topological sort, parallelization)
//! 3. Executes nodes (native/WASM/SQL)
//! 4. Emits "glow" events for visualization
//! 5. Captures traces for learning

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use crate::Result;
use crate::dto::FireflyNode;
use crate::storage::FireflyStore;

// =============================================================================
// GLOW STATE (execution visualization)
// =============================================================================

/// Node execution state for visualization.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GlowState {
    Pending,
    Active,
    Success,
    Failure,
    Skipped,
}

impl GlowState {
    pub fn emoji(&self) -> &'static str {
        match self {
            GlowState::Pending => "⏳",
            GlowState::Active => "🔥",
            GlowState::Success => "✅",
            GlowState::Failure => "❌",
            GlowState::Skipped => "⏭️",
        }
    }
}

// =============================================================================
// EXECUTION CONTEXT
// =============================================================================

/// Context passed through execution.
///
/// Accumulates results from each node.
#[derive(Debug, Clone)]
pub struct ExecutionContext {
    pub execution_id: String,
    pub input_data: HashMap<String, serde_json::Value>,
    pub results: HashMap<String, serde_json::Value>,
    pub errors: HashMap<String, String>,
    pub trace: Vec<String>,
}

impl ExecutionContext {
    /// Create a new execution context.
    pub fn new(input_data: HashMap<String, serde_json::Value>) -> Self {
        Self {
            execution_id: uuid::Uuid::new_v4().to_string(),
            input_data,
            results: HashMap::new(),
            errors: HashMap::new(),
            trace: Vec::new(),
        }
    }

    /// Get value from input or previous results.
    pub fn get(&self, key: &str) -> Option<&serde_json::Value> {
        self.input_data.get(key).or_else(|| self.results.get(key))
    }

    /// Set result from node execution.
    pub fn set(&mut self, node_id: &str, result: serde_json::Value) {
        self.results.insert(node_id.to_string(), result);
        self.trace.push(node_id.to_string());
    }

    /// Record error from node execution.
    pub fn set_error(&mut self, node_id: &str, error: String) {
        self.errors.insert(node_id.to_string(), error);
        self.trace.push(format!("{}:ERROR", node_id));
    }

    /// Check if execution succeeded (no errors).
    pub fn success(&self) -> bool {
        self.errors.is_empty()
    }

    /// Get final result (last node's output).
    pub fn result(&self) -> Option<&serde_json::Value> {
        self.trace
            .last()
            .and_then(|s| s.strip_suffix(":ERROR").map(|_| None).unwrap_or(Some(s)))
            .and_then(|id| self.results.get(id))
    }
}

// =============================================================================
// EXECUTOR TRAIT
// =============================================================================

/// Function that can be executed by a node.
pub type ExecutorFn = Arc<dyn Fn(&HashMap<String, serde_json::Value>, &ExecutionContext) -> Result<serde_json::Value> + Send + Sync>;

/// Async executor function.
pub type AsyncExecutorFn = Arc<dyn Fn(HashMap<String, serde_json::Value>, ExecutionContext) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<serde_json::Value>> + Send>> + Send + Sync>;

// =============================================================================
// FIREFLY ENGINE
// =============================================================================

/// Execute compiled graphs.
/// Watch nodes light up as execution flows through.
pub struct FireflyEngine {
    store: Arc<FireflyStore>,
    executors: HashMap<String, ExecutorFn>,
    glow_handlers: Vec<Box<dyn Fn(&str, GlowState) + Send + Sync>>,
}

impl FireflyEngine {
    /// Create a new engine with a store.
    pub fn new(store: Arc<FireflyStore>) -> Self {
        let mut engine = Self {
            store,
            executors: HashMap::new(),
            glow_handlers: Vec::new(),
        };

        // Register built-in executors
        engine.register_builtin_executors();
        engine
    }

    /// Register a native executor function.
    pub fn register_executor<F>(&mut self, name: &str, f: F)
    where
        F: Fn(&HashMap<String, serde_json::Value>, &ExecutionContext) -> Result<serde_json::Value> + Send + Sync + 'static,
    {
        self.executors.insert(name.to_string(), Arc::new(f));
    }

    /// Register handler for node glow events.
    pub fn on_glow<F>(&mut self, handler: F)
    where
        F: Fn(&str, GlowState) + Send + Sync + 'static,
    {
        self.glow_handlers.push(Box::new(handler));
    }

    /// Emit glow event to all handlers.
    fn emit_glow(&self, node_id: &str, state: GlowState) {
        for handler in &self.glow_handlers {
            handler(node_id, state);
        }

        // Default console output
        println!("{} {}: {:?}", state.emoji(), node_id, state);
    }

    /// Execute a DTO operation.
    pub async fn execute(
        &self,
        dto: &str,
        operation: &str,
        input_data: HashMap<String, serde_json::Value>,
    ) -> Result<ExecutionContext> {
        let mut ctx = ExecutionContext::new(input_data);

        // Find entry point
        let entry_id = format!("{}_{}_entry", dto, operation);

        // Get execution path from graph
        let path = self.store.get_execution_path(&entry_id).await?;

        if path.is_empty() {
            // Fallback: just execute the entry node
            self.execute_single(&entry_id, &mut ctx).await?;
            return Ok(ctx);
        }

        // Execute each node in path
        for node_id in path {
            if !ctx.success() {
                break;
            }
            self.execute_node(&node_id, &mut ctx).await?;
        }

        Ok(ctx)
    }

    /// Execute a single node by ID.
    async fn execute_single(&self, node_id: &str, ctx: &mut ExecutionContext) -> Result<()> {
        if let Some(node) = self.store.get_node(node_id).await? {
            self.execute_node_impl(&node, ctx).await
        } else {
            ctx.set_error(node_id, format!("Node not found: {}", node_id));
            Ok(())
        }
    }

    /// Execute a node by ID.
    async fn execute_node(&self, node_id: &str, ctx: &mut ExecutionContext) -> Result<()> {
        match self.store.get_node(node_id).await? {
            Some(node) => self.execute_node_impl(&node, ctx).await,
            None => {
                self.emit_glow(node_id, GlowState::Skipped);
                Ok(())
            }
        }
    }

    /// Execute a node with tracing and glow.
    async fn execute_node_impl(&self, node: &FireflyNode, ctx: &mut ExecutionContext) -> Result<()> {
        self.emit_glow(&node.id, GlowState::Active);

        let start = Instant::now();

        let result = self.run_executor(node, ctx);
        let duration_ms = start.elapsed().as_secs_f64() * 1000.0;

        match result {
            Ok(value) => {
                ctx.set(&node.id, value);
                self.emit_glow(&node.id, GlowState::Success);

                // Log execution
                self.store
                    .log_execution(&ctx.execution_id, &node.id, duration_ms, true, None)
                    .await?;
            }
            Err(e) => {
                let error_msg = e.to_string();
                ctx.set_error(&node.id, error_msg.clone());
                self.emit_glow(&node.id, GlowState::Failure);

                // Log execution
                self.store
                    .log_execution(&ctx.execution_id, &node.id, duration_ms, false, Some(&error_msg))
                    .await?;
            }
        }

        Ok(())
    }

    /// Run a native executor function.
    fn run_executor(&self, node: &FireflyNode, ctx: &ExecutionContext) -> Result<serde_json::Value> {
        // Build input from context
        let mut input_data = HashMap::new();
        for field in node.input_schema.keys() {
            if let Some(value) = ctx.get(field) {
                input_data.insert(field.clone(), value.clone());
            }
        }

        // Get executor
        if let Some(executor) = self.executors.get(&node.fn_name) {
            executor(&input_data, ctx)
        } else {
            // No executor - pass through
            Ok(serde_json::json!({
                "status": "no_executor",
                "node": node.id
            }))
        }
    }

    /// Register built-in executors.
    fn register_builtin_executors(&mut self) {
        // validate_presence
        self.register_executor("validate_presence", |input, _ctx| {
            let field = input
                .get("_field")
                .and_then(|v| v.as_str())
                .unwrap_or("value");

            let value = input.get(field);
            let errors: Vec<String> = if value.is_none()
                || value == Some(&serde_json::Value::Null)
                || value.and_then(|v| v.as_str()) == Some("")
            {
                vec![format!("{} can't be blank", field)]
            } else {
                vec![]
            };

            Ok(serde_json::json!({
                "valid": errors.is_empty(),
                "errors": errors
            }))
        });

        // validate_length
        self.register_executor("validate_length", |input, _ctx| {
            let field = input
                .get("_field")
                .and_then(|v| v.as_str())
                .unwrap_or("value");

            let value = input
                .get(field)
                .and_then(|v| v.as_str())
                .unwrap_or("");

            let min_len = input.get("_min").and_then(|v| v.as_u64());
            let max_len = input.get("_max").and_then(|v| v.as_u64());

            let mut errors = Vec::new();

            if let Some(min) = min_len {
                if (value.len() as u64) < min {
                    errors.push(format!("{} is too short (min {})", field, min));
                }
            }

            if let Some(max) = max_len {
                if (value.len() as u64) > max {
                    errors.push(format!("{} is too long (max {})", field, max));
                }
            }

            Ok(serde_json::json!({
                "valid": errors.is_empty(),
                "errors": errors
            }))
        });

        // transform_identity
        self.register_executor("transform_identity", |input, _ctx| {
            Ok(serde_json::to_value(input).unwrap_or(serde_json::Value::Null))
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_execution_context() {
        let mut ctx = ExecutionContext::new(HashMap::new());

        ctx.set("node1", serde_json::json!({"result": 42}));
        assert!(ctx.success());
        assert_eq!(ctx.trace.len(), 1);

        ctx.set_error("node2", "test error".into());
        assert!(!ctx.success());
        assert_eq!(ctx.trace.len(), 2);
    }

    #[tokio::test]
    async fn test_builtin_validate_presence() {
        let store = Arc::new(FireflyStore::in_memory());
        let engine = FireflyEngine::new(store);

        let executor = engine.executors.get("validate_presence").unwrap();

        // Test with missing value
        let input = HashMap::new();
        let ctx = ExecutionContext::new(HashMap::new());
        let result = executor(&input, &ctx).unwrap();
        assert_eq!(result["valid"], false);

        // Test with present value
        let mut input = HashMap::new();
        input.insert("value".to_string(), serde_json::json!("hello"));
        let result = executor(&input, &ctx).unwrap();
        assert_eq!(result["valid"], true);
    }

    #[tokio::test]
    async fn test_builtin_validate_length() {
        let store = Arc::new(FireflyStore::in_memory());
        let engine = FireflyEngine::new(store);

        let executor = engine.executors.get("validate_length").unwrap();
        let ctx = ExecutionContext::new(HashMap::new());

        // Test too short
        let mut input = HashMap::new();
        input.insert("value".to_string(), serde_json::json!("ab"));
        input.insert("_min".to_string(), serde_json::json!(5));
        let result = executor(&input, &ctx).unwrap();
        assert_eq!(result["valid"], false);

        // Test valid length
        let mut input = HashMap::new();
        input.insert("value".to_string(), serde_json::json!("hello world"));
        input.insert("_min".to_string(), serde_json::json!(5));
        input.insert("_max".to_string(), serde_json::json!(20));
        let result = executor(&input, &ctx).unwrap();
        assert_eq!(result["valid"], true);
    }
}
