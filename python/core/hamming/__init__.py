"""
Firefly Hamming Operations - Cross-Language Content-Addressable Memory

Same XOR + POPCOUNT in every language.
Same fingerprint → same resonance regardless of runtime.

Languages:
- Python (with Numba JIT): core/hamming/python/
- Rust (full crate): core/hamming/rust/
- Reference implementations: core/hamming/impl/ (Go, TypeScript, C, Java, C#, Zig)

Usage:
    from core.hamming import HammingVector, fingerprint, resonate, bundle

    # Create vectors
    v1 = fingerprint("validate_email", "(str) -> bool", "check format")
    v2 = fingerprint("validate_phone", "(str) -> bool", "check format")

    # Operations
    sim = v1 @ v2  # or v1.similarity(v2)
    bound = v1 ^ v2  # XOR binding (self-inverse)

    # Search
    results = resonate(query, corpus, threshold=0.5)
"""

# =============================================================================
# PYTHON IMPLEMENTATION (Numba JIT)
# =============================================================================

from .python import (
    # Constants
    DIM,
    DIM_U64,
    PACKED,
    LAST_MASK,
    HAS_NUMBA,

    # Core class
    HammingVector,

    # High-level functions
    fingerprint,
    resonate,
    bundle,
    info,

    # JIT kernels (for advanced use)
    hamming_distance_jit,
    xor_vectors_jit,
    similarity_jit,
    batch_hamming_jit,
    batch_similarity_jit,
    bundle_vectors_jit,
)

__all__ = [
    # Constants
    "DIM",
    "DIM_U64",
    "PACKED",
    "LAST_MASK",
    "HAS_NUMBA",

    # Core class
    "HammingVector",

    # High-level functions
    "fingerprint",
    "resonate",
    "bundle",
    "info",

    # JIT kernels
    "hamming_distance_jit",
    "xor_vectors_jit",
    "similarity_jit",
    "batch_hamming_jit",
    "batch_similarity_jit",
    "bundle_vectors_jit",

    # Reference code getters
    "get_reference_code",
    "list_languages",
]

# =============================================================================
# REFERENCE CODE FOR OTHER LANGUAGES
# =============================================================================

# Map of language -> (filename, path relative to impl/)
REFERENCE_LANGUAGES = {
    "typescript": "hamming.ts",
    "go": "hamming.go",
    "c": "hamming.h",
    "cpp": "hamming.hpp",
    "csharp": "Hamming.cs",
    "java": "HammingVector.java",
    "zig": "hamming.zig",
    "ruby": "hamming.rb",
    "wasm": "hamming.wat",
}


def get_reference_code(language: str) -> str:
    """
    Get reference Hamming implementation for a specific language.

    Languages: typescript, go, c, cpp, csharp, java, zig, ruby, wasm

    For Python, use the main module directly.
    For Rust, see core/hamming/rust/
    """
    import os
    lang = language.lower()

    if lang == "python":
        return "Use: from core.hamming import HammingVector"

    if lang == "rust":
        return "Use: core/hamming/rust/ crate"

    if lang not in REFERENCE_LANGUAGES:
        available = ", ".join(sorted(REFERENCE_LANGUAGES.keys()))
        raise ValueError(f"Unknown language: {lang}. Available: {available}")

    # Read from impl/ folder
    impl_path = os.path.join(os.path.dirname(__file__), "impl", REFERENCE_LANGUAGES[lang])
    if os.path.exists(impl_path):
        with open(impl_path, "r") as f:
            return f.read()
    else:
        return f"# Reference file not found: {impl_path}"


def list_languages() -> list:
    """List all supported languages (including Python and Rust)."""
    return ["python", "rust"] + sorted(REFERENCE_LANGUAGES.keys())


# =============================================================================
# MODULE INFO
# =============================================================================

if __name__ == "__main__":
    print("Firefly Hamming Operations")
    print("=" * 50)
    print(f"Dimension: {DIM} bits")
    print(f"Packed size: {PACKED} bytes")
    print(f"Numba JIT: {'enabled' if HAS_NUMBA else 'disabled'}")
    print()
    print("Supported languages:")
    for lang in list_languages():
        print(f"  - {lang}")
