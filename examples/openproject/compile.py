#!/usr/bin/env python3
"""
Example: Compile OpenProject Ruby models to Firefly graph substrate.

Demonstrates the full compilation pipeline:
  PARSE → ANALYZE → LOWER → OPTIMIZE → EMBED → EMIT

Usage:
    python -m examples.openproject.compile
"""

import asyncio
import sys
from pathlib import Path

# Ensure firefly root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from compiler.ruby import RubyParser, RubyCompiler
from compiler.analyze.semantic import SemanticAnalyzer
from compiler.lower.nodes import GraphLowering
from compiler.optimize.pipeline import GraphOptimizer
from compiler.embed.vectors import VectorEmbedder


async def main():
    print("=" * 60)
    print("FIREFLY: OpenProject Compilation Example")
    print("=" * 60)
    print()

    # Path to example Ruby model
    example_dir = Path(__file__).parent
    rb_file = example_dir / "work_package.rb"

    if not rb_file.exists():
        print(f"Error: {rb_file} not found")
        return

    # Phase 1: PARSE
    print("Phase 1: PARSE")
    print("-" * 40)
    parser = RubyParser()
    model = parser.parse_file(str(rb_file))
    if not model:
        print("  Failed to parse model")
        return

    print(f"  Model: {model.name}")
    print(f"  Validations: {len(model.validations)}")
    print(f"  Associations: {len(model.associations)}")
    print(f"  Callbacks: {len(model.callbacks)}")
    print(f"  Scopes: {len(model.scopes)}")
    print()

    for v in model.validations:
        print(f"    validate :{v.field} ({v.type})")
    for a in model.associations:
        print(f"    {a.type} :{a.name}")
    for c in model.callbacks:
        print(f"    {c.timing}_{c.event} :{c.method}")
    for s in model.scopes:
        print(f"    scope :{s['name']}")
    print()

    # Phase 2: ANALYZE
    print("Phase 2: ANALYZE")
    print("-" * 40)
    analyzer = SemanticAnalyzer()
    graphs = analyzer.analyze_model(model)

    for op, graph in graphs.items():
        stages = graph.topological_sort()
        print(f"  {op}:")
        print(f"    Nodes: {len(graph.nodes)}")
        print(f"    Edges: {len(graph.edges)}")
        print(f"    Stages: {len(stages)}")
        for i, stage in enumerate(stages):
            parallel = "parallel" if len(stage) > 1 else "sequential"
            print(f"      Stage {i}: {stage} ({parallel})")
    print()

    # Phase 3: LOWER
    print("Phase 3: LOWER")
    print("-" * 40)
    lowering = GraphLowering()

    all_nodes = []
    all_edges = []
    for op, graph in graphs.items():
        nodes, edges = await lowering.lower(graph)
        all_nodes.extend(nodes)
        all_edges.extend(edges)
        print(f"  {op}: {len(nodes)} nodes, {len(edges)} edges")

    print(f"  Total: {len(all_nodes)} nodes, {len(all_edges)} edges")
    print(f"  Size: {len(all_nodes) * 1.25:.1f}KB")
    print()

    # Phase 4: OPTIMIZE
    print("Phase 4: OPTIMIZE")
    print("-" * 40)
    optimizer = GraphOptimizer()
    opt_nodes, opt_edges, stats = optimizer.optimize(all_nodes, all_edges)

    print(f"  Before: {stats.nodes_before} nodes, {stats.edges_before} edges")
    print(f"  After:  {stats.nodes_after} nodes, {stats.edges_after} edges")
    print(f"  Eliminated: {stats.eliminated}")
    print(f"  Fused: {stats.fused}")
    print(f"  Parallelized: {stats.parallelized}")
    print(f"  Cached: {stats.cached}")
    print()

    # Phase 5: EMBED
    print("Phase 5: EMBED")
    print("-" * 40)
    embedder = VectorEmbedder()  # No Jina — uses structural fingerprints
    embedded_nodes = await embedder.embed_graph(opt_nodes, opt_edges)
    print(f"  Embedded {len(embedded_nodes)} nodes with structural fingerprints")

    # Show some node details
    for node in embedded_nodes[:5]:
        cam = VectorEmbedder.cam_fingerprint(node.resonance)
        print(f"    {node.id}")
        print(f"      Type: {node.type} | Executor: {node.executor}")
        print(f"      CAM: 0x{cam:012x}")
        print(f"      Pure: {node.pure} | Parallel: {node.parallelizable}")
    if len(embedded_nodes) > 5:
        print(f"    ... and {len(embedded_nodes) - 5} more")
    print()

    # Phase 6: EMIT (skip actual DB storage in example)
    print("Phase 6: EMIT (summary)")
    print("-" * 40)
    print(f"  Would store to LanceDB: {len(embedded_nodes)} vectors")
    print(f"  Would store to DuckDB: {len(embedded_nodes)} nodes + {len(opt_edges)} edges")
    print(f"  Would store to Kuzu: {len(embedded_nodes)} graph nodes + {len(opt_edges)} relationships")
    print()

    # Summary
    print("=" * 60)
    print("COMPILATION COMPLETE")
    print("=" * 60)
    print(f"  Source: {rb_file.name}")
    print(f"  Model: {model.name}")
    print(f"  Operations: {', '.join(graphs.keys())}")
    print(f"  Total nodes: {len(embedded_nodes)}")
    print(f"  Total edges: {len(opt_edges)}")
    print(f"  Total size: {len(embedded_nodes) * 1.25:.1f}KB")
    print(f"  State space: 2^{len(embedded_nodes) * 10000} possible states")
    print()
    print("  Any procedural system -> Graph -> Execution -> AGI")


if __name__ == "__main__":
    asyncio.run(main())
