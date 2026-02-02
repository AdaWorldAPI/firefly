//! Error types for Firefly Core.

use thiserror::Error;

/// Result type alias for Firefly operations.
pub type Result<T> = std::result::Result<T, FireflyError>;

/// Errors that can occur in Firefly Core operations.
#[derive(Error, Debug)]
pub enum FireflyError {
    /// Invalid hexadecimal string.
    #[error("Invalid hex string: {0}")]
    InvalidHex(String),

    /// Invalid byte array length.
    #[error("Invalid length: {0}")]
    InvalidLength(String),

    /// Serialization/deserialization error.
    #[error("Serialization error: {0}")]
    SerializationError(String),

    /// Node not found.
    #[error("Node not found: {0}")]
    NodeNotFound(String),

    /// Edge not found.
    #[error("Edge not found: {0}")]
    EdgeNotFound(String),

    /// Invalid node type.
    #[error("Invalid node type: {0}")]
    InvalidNodeType(String),

    /// Invalid edge type.
    #[error("Invalid edge type: {0}")]
    InvalidEdgeType(String),

    /// Checksum mismatch.
    #[error("Checksum mismatch: expected {expected:#x}, got {actual:#x}")]
    ChecksumMismatch { expected: u32, actual: u32 },

    /// TTL expired.
    #[error("Packet TTL expired")]
    TtlExpired,

    /// Storage error.
    #[error("Storage error: {0}")]
    StorageError(String),

    /// Transport error.
    #[error("Transport error: {0}")]
    TransportError(String),

    /// Execution error.
    #[error("Execution error: {0}")]
    ExecutionError(String),
}

impl From<serde_json::Error> for FireflyError {
    fn from(err: serde_json::Error) -> Self {
        FireflyError::SerializationError(err.to_string())
    }
}
