#!/usr/bin/env python3
"""
Firefly CLI: Bioluminescent Code Execution

Usage:
    firefly compile <path>           Compile source to graph
    firefly execute <dto> [options]  Execute a DTO operation  
    firefly trace                    Watch execution in real-time
    firefly resonate <query>         Find similar patterns
    firefly explain                  Explain last failure
    firefly stats                    Show execution statistics
"""

import asyncio
import json
import sys
from pathlib import Path

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core import similarity, project, random_vector
from dto import FireflyNode, FireflyEdge
from storage import FireflyStore
from executor import FireflyEngine, BUILTIN_EXECUTORS, GlowState
from compiler import RubyCompiler


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """🔥 Firefly: Bioluminescent Code Execution"""
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--output', '-o', default='./firefly_data', help='Output directory')
@click.option('--language', '-l', default='ruby', help='Source language (ruby, python)')
def compile(path: str, output: str, language: str):
    """Compile source code to Firefly graph."""
    
    click.echo(f"🔥 Firefly Compiler")
    click.echo(f"   Source: {path}")
    click.echo(f"   Language: {language}")
    click.echo(f"   Output: {output}")
    click.echo()
    
    async def do_compile():
        # Initialize storage
        store = FireflyStore(output)
        
        # Select compiler
        if language == 'ruby':
            compiler = RubyCompiler()
        else:
            click.echo(f"❌ Unsupported language: {language}")
            return
        
        # Compile
        click.echo("📖 Parsing source files...")
        nodes, edges = await compiler.compile_directory(path)
        
        click.echo(f"\n📊 Compiled:")
        click.echo(f"   Nodes: {len(nodes)}")
        click.echo(f"   Edges: {len(edges)}")
        click.echo(f"   Total size: {len(nodes) * 1.25:.1f}KB")
        
        # Store
        click.echo("\n💾 Storing to databases...")
        for node in nodes:
            await store.store_node(node)
        for edge in edges:
            await store.store_edge(edge)
        
        click.echo(f"\n✅ Compiled graph saved to {output}")
        store.close()
    
    asyncio.run(do_compile())


@cli.command()
@click.argument('dto')
@click.option('--operation', '-o', default='create', help='Operation (create, update, destroy)')
@click.option('--input', '-i', 'input_json', default='{}', help='Input JSON')
@click.option('--data-dir', '-d', default='./firefly_data', help='Data directory')
def execute(dto: str, operation: str, input_json: str, data_dir: str):
    """Execute a DTO operation."""
    
    click.echo(f"🔥 Firefly Executor")
    click.echo(f"   DTO: {dto}")
    click.echo(f"   Operation: {operation}")
    click.echo()
    
    async def do_execute():
        # Parse input
        try:
            input_data = json.loads(input_json)
        except json.JSONDecodeError as e:
            click.echo(f"❌ Invalid JSON: {e}")
            return
        
        # Initialize
        store = FireflyStore(data_dir)
        engine = FireflyEngine(store)
        
        # Register built-in executors
        for name, fn in BUILTIN_EXECUTORS.items():
            engine.register_executor(name, fn)
        
        # Add glow handler for CLI output
        def on_glow(node_id: str, state: GlowState):
            emoji = {
                GlowState.PENDING: "⏳",
                GlowState.ACTIVE: "🔥",
                GlowState.SUCCESS: "✅",
                GlowState.FAILURE: "❌",
                GlowState.SKIPPED: "⏭️",
            }
            click.echo(f"   {emoji.get(state, '?')} {node_id}")
        
        engine.on_glow(on_glow)
        
        # Execute
        click.echo("Executing...")
        ctx = await engine.execute(dto, operation, input_data)
        
        click.echo()
        if ctx.success:
            click.echo(f"✅ Success")
            click.echo(f"   Result: {json.dumps(ctx.result, indent=2)}")
        else:
            click.echo(f"❌ Failed")
            for node_id, error in ctx.errors.items():
                click.echo(f"   {node_id}: {error}")
        
        click.echo(f"\n📍 Trace: {' → '.join(ctx.trace)}")
        store.close()
    
    asyncio.run(do_execute())


@cli.command()
@click.argument('query')
@click.option('--top-k', '-k', default=5, help='Number of results')
@click.option('--data-dir', '-d', default='./firefly_data', help='Data directory')
def resonate(query: str, top_k: int, data_dir: str):
    """Find nodes similar to query."""
    
    click.echo(f"🔥 Firefly Resonance Search")
    click.echo(f"   Query: {query}")
    click.echo()
    
    async def do_search():
        store = FireflyStore(data_dir)
        
        # Generate query vector (using hash for now, would use Jina in production)
        import hashlib
        h = hashlib.sha256(query.encode()).digest()
        query_vec = (h * 40)[:1250]
        
        # Search
        results = await store.find_similar_nodes(query_vec, k=top_k)
        
        if not results:
            click.echo("No results found.")
            return
        
        click.echo(f"Found {len(results)} similar nodes:\n")
        for i, r in enumerate(results, 1):
            distance = r.get('_distance', 'N/A')
            click.echo(f"  {i}. {r['id']}")
            click.echo(f"     Type: {r.get('type', 'unknown')}")
            click.echo(f"     Distance: {distance}")
            click.echo()
        
        store.close()
    
    asyncio.run(do_search())


@cli.command()
@click.option('--data-dir', '-d', default='./firefly_data', help='Data directory')
def stats(data_dir: str):
    """Show execution statistics."""
    
    click.echo(f"🔥 Firefly Statistics\n")
    
    async def do_stats():
        store = FireflyStore(data_dir)
        
        # Get slowest nodes
        slowest = await store.get_slowest_nodes(10)
        
        if not slowest:
            click.echo("No execution data yet.")
            return
        
        click.echo("Slowest nodes (by avg duration):\n")
        for node in slowest:
            click.echo(f"  {node['node_id']}")
            click.echo(f"    Executions: {node['executions']}")
            click.echo(f"    Avg: {node['avg_duration']:.2f}ms")
            click.echo(f"    Max: {node['max_duration']:.2f}ms")
            click.echo(f"    Failures: {node['failures']}")
            click.echo()
        
        store.close()
    
    asyncio.run(do_stats())


@cli.command()
@click.option('--data-dir', '-d', default='./firefly_data', help='Data directory')
def explain(data_dir: str):
    """Explain last failure."""
    
    click.echo(f"🔥 Firefly Failure Analysis\n")
    
    async def do_explain():
        store = FireflyStore(data_dir)
        
        if not store.duck:
            click.echo("DuckDB not available.")
            return
        
        # Get last failure
        result = store.duck.execute("""
            SELECT node_id, error, timestamp
            FROM execution_log
            WHERE NOT success
            ORDER BY timestamp DESC
            LIMIT 1
        """).fetchone()
        
        if not result:
            click.echo("No failures recorded.")
            return
        
        node_id, error, timestamp = result
        
        click.echo(f"Last failure: {node_id}")
        click.echo(f"Time: {timestamp}")
        click.echo(f"Error: {error}")
        
        # Get upstream nodes
        click.echo(f"\nUpstream nodes:")
        upstream = await store.get_upstream_nodes(node_id)
        for up in upstream:
            click.echo(f"  ← {up}")
        
        store.close()
    
    asyncio.run(do_explain())


@cli.command()
def info():
    """Show Firefly information."""
    
    click.echo("""
🔥 FIREFLY
   Bioluminescent Code Execution
   
   Version: 0.1.0
   
   The modesty:   1.25KB per node
   The immodesty: 2^10000 possible states
   
   Storage:
   • LanceDB (vectors)
   • DuckDB (facts)
   • Kuzu (graph)
   
   https://github.com/AdaWorldAPI/firefly
""")


if __name__ == '__main__':
    cli()
