#!/usr/bin/env python3
"""LadybugDB Demo - Code as Deterministic Data.

Shows:
1. Register functions → fingerprint → hashtable
2. Deterministic execution graph (DuckDB)
3. Similarity search (LanceDB + AVX-512)
4. Translation to other languages
"""

import sys
sys.path.insert(0, "..")

import time
from ladybugdb import LadybugDB, TYPE_VALIDATE, TYPE_TRANSFORM, TYPE_PERSIST


# =============================================================================
# SAMPLE FUNCTIONS TO REGISTER
# =============================================================================

def validate_email(email: str) -> bool:
    """Check if email is valid."""
    return "@" in email and "." in email.split("@")[1]


def validate_age(age: int) -> bool:
    """Check if age is reasonable."""
    return 0 < age < 150


def normalize_name(name: str) -> str:
    """Normalize a name."""
    return name.strip().title()


def create_user(name: str, email: str, age: int) -> dict:
    """Create user dict."""
    return {
        "name": normalize_name(name),
        "email": email.lower(),
        "age": age,
        "created_at": time.time(),
    }


def persist_user(user: dict) -> int:
    """Simulate persisting user, return ID."""
    return hash(user["email"]) % 1000000


def similar_validate(x: str) -> bool:
    """Similar to validate_email."""
    return "@" in x


def different_function(a: int, b: int) -> int:
    """Completely different function."""
    return a * b + a - b


# =============================================================================
# DEMO
# =============================================================================

def main():
    print("=" * 70)
    print("LADYBUGDB - Code as Deterministic Data")
    print("=" * 70)
    print()
    
    # Create database
    db = LadybugDB(
        duck_path=":memory:",
        lance_path="/tmp/ladybug_demo",
    )
    
    # Register functions with dependencies
    print("1. REGISTER FUNCTIONS")
    print("-" * 50)
    
    db.register(validate_email, type_code=TYPE_VALIDATE)
    db.register(validate_age, type_code=TYPE_VALIDATE)
    db.register(normalize_name, type_code=TYPE_TRANSFORM)
    db.register(create_user, deps=["validate_email", "validate_age", "normalize_name"])
    db.register(persist_user, deps=["create_user"], type_code=TYPE_PERSIST)
    db.register(similar_validate, type_code=TYPE_VALIDATE)
    db.register(different_function)
    
    print(f"Registered {len(db)} atoms")
    print()
    
    for name in ["validate_email", "create_user", "persist_user"]:
        atom = db[name]
        print(f"  {name}:")
        print(f"    Index:       {atom.index}")
        print(f"    Fingerprint: {atom.fingerprint[:2].tobytes().hex()}...")
        print(f"    Depends on:  {atom.depends_on}")
    print()
    
    # Execute
    print("2. EXECUTE")
    print("-" * 50)
    
    result = db.execute("validate_email", "test@example.com")
    print(f"validate_email('test@example.com') = {result}")
    
    result = db.execute("validate_email", "invalid")
    print(f"validate_email('invalid') = {result}")
    
    result = db.execute("normalize_name", "  JOHN DOE  ")
    print(f"normalize_name('  JOHN DOE  ') = '{result}'")
    
    result = db.execute("create_user", "john doe", "john@example.com", 30)
    print(f"create_user(...) = {result}")
    print()
    
    # Execution plan
    print("3. EXECUTION PLAN (Topological Order)")
    print("-" * 50)
    
    plan = db.graph.topological_levels()
    for i, level in enumerate(plan):
        names = [db._atoms[idx].name for idx in level if idx in db._atoms]
        print(f"  Level {i}: {names}")
    print()
    
    # Similarity / Resonance
    print("4. SIMILARITY / RESONANCE (AVX-512)")
    print("-" * 50)
    
    # Compare similar functions
    sim = db.similarity("validate_email", "similar_validate")
    print(f"validate_email ↔ similar_validate:  {sim:.3f}")
    
    sim = db.similarity("validate_email", "validate_age")
    print(f"validate_email ↔ validate_age:      {sim:.3f}")
    
    sim = db.similarity("validate_email", "different_function")
    print(f"validate_email ↔ different_function: {sim:.3f}")
    print()
    
    # Find resonating atoms
    print("Atoms resonating with validate_email (threshold=0.5):")
    resonating = db.resonate("validate_email", threshold=0.5)
    for name, sim in resonating:
        print(f"  {name}: {sim:.3f}")
    print()
    
    # Find similar to unregistered function
    def check_valid_email(addr: str) -> bool:
        """Check email validity."""
        return "@" in addr
    
    print("Finding atoms similar to unregistered 'check_valid_email':")
    similar = db.find_similar(check_valid_email, k=3)
    for name, sim in similar:
        print(f"  {name}: {sim:.3f}")
    print()
    
    # Translation
    print("5. TRANSLATE TO OTHER LANGUAGES")
    print("-" * 50)
    
    print("TypeScript:")
    ts = db.translate("validate_email", target="typescript")
    print(ts)
    print()
    
    print("Rust:")
    rs = db.translate("validate_email", target="rust")
    print(rs)
    print()
    
    # Export graph
    print("6. EXPORT GRAPH (Graphviz DOT)")
    print("-" * 50)
    
    dot = db.export_graph()
    print(dot[:500] + "..." if len(dot) > 500 else dot)
    print()
    
    # Stats
    print("7. STATS")
    print("-" * 50)
    
    stats = db.stats()
    for k, v in stats.items():
        if k == "avg_ns":
            print(f"  {k}: {v:.0f} ns")
        else:
            print(f"  {k}: {v}")
    print()
    
    # Benchmark
    print("8. BENCHMARK")
    print("-" * 50)
    
    # Register 1000 synthetic functions
    start = time.perf_counter()
    for i in range(1000):
        exec(f"def func_{i}(x): return x + {i}")
        db.register(eval(f"func_{i}"))
    reg_time = time.perf_counter() - start
    print(f"Registered 1000 functions in {reg_time*1000:.1f} ms")
    print(f"  = {reg_time/1000*1000*1000:.1f} ns per registration")
    
    # Resonance search over all
    start = time.perf_counter()
    for _ in range(100):
        _ = db.resonate("validate_email", threshold=0.5, k=10)
    search_time = time.perf_counter() - start
    print(f"100 resonance searches in {search_time*1000:.1f} ms")
    print(f"  = {search_time/100*1000:.2f} ms per search over {len(db)} atoms")
    
    print()
    print("=" * 70)
    print(f"FINAL: {db}")
    print("=" * 70)


if __name__ == "__main__":
    main()
