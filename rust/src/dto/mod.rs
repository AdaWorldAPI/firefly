//! Data Transfer Objects for Firefly.
//!
//! - `FireflyNode`: Executable graph node (1.25KB)
//! - `FireflyEdge`: Graph edge as resonance binding
//! - `FireflyPacket`: mRNA transport packet (~1.5KB)

mod node;
mod edge;
mod packet;

pub use node::{FireflyNode, FireflyNodeBuilder, Executor, NodeType};
pub use edge::{FireflyEdge, EdgeType};
pub use packet::{FireflyPacket, UnpackedHeader, flags, HEADER_SIZE};
