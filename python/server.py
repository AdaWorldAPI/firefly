"""
Firefly API Server

Detects environment automatically:
  Railway:  0.0.0.0:$PORT (default 8080)
  Local:    127.0.0.1:8000
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

from core import similarity, project, random_vector, PACKED, DIM
from dto import FireflyNode, FireflyEdge, FireflyPacket
from storage import FireflyStore
from executor import FireflyEngine, BUILTIN_EXECUTORS, GlowState
from compiler import RubyCompiler

# --- Environment detection ---

RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_ID"))
HOST = "0.0.0.0" if RAILWAY else os.environ.get("FIREFLY_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080" if RAILWAY else "8000"))
DATA_DIR = os.environ.get("FIREFLY_DATA_DIR", "/data" if RAILWAY else "./firefly_data")

# --- Shared state ---

store: FireflyStore = None
engine: FireflyEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, engine
    store = FireflyStore(DATA_DIR)
    engine = FireflyEngine(store)
    for name, fn in BUILTIN_EXECUTORS.items():
        engine.register_executor(name, fn)
    yield
    store.close()


app = FastAPI(
    title="Firefly",
    version="0.1.0",
    description="Graph Substrate Compiler — 10K Hamming vectors over mRNA transport",
    lifespan=lifespan,
)


# --- Health / info ---

@app.get("/")
async def root():
    return {
        "service": "firefly",
        "version": "0.1.0",
        "environment": "railway" if RAILWAY else "local",
        "host": HOST,
        "port": PORT,
        "dim": DIM,
        "packed": PACKED,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Compile ---

@app.post("/compile")
async def compile_source(request: Request):
    """Compile source code to Firefly graph.

    Body: {"source": "<ruby source>", "language": "ruby"}
    """
    body = await request.json()
    source = body.get("source", "")
    language = body.get("language", "ruby")

    if not source:
        raise HTTPException(400, "source is required")

    if language == "ruby":
        compiler = RubyCompiler()
    else:
        raise HTTPException(400, f"unsupported language: {language}")

    # Write source to a temp file for parsing (parser expects file path)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rb', delete=False) as f:
        f.write(source)
        temp_path = f.name

    try:
        parsed = compiler.parser.parse_file(temp_path)
        if not parsed:
            raise HTTPException(422, "parse returned no model")

        all_nodes = []
        all_edges = []

        # parse_file returns a single model, not a list
        nodes, edges = await compiler._compile_model(parsed)
        all_nodes.extend(nodes)
        all_edges.extend(edges)
    finally:
        import os
        os.unlink(temp_path)

    # Persist
    for node in all_nodes:
        await store.store_node(node)
    for edge in all_edges:
        await store.store_edge(edge)

    return {
        "nodes": len(all_nodes),
        "edges": len(all_edges),
        "size_kb": len(all_nodes) * 1.25,
        "node_ids": [n.id for n in all_nodes],
    }


# --- Execute ---

@app.post("/execute")
async def execute_dto(request: Request):
    """Execute a DTO operation.

    Body: {"dto": "work_packages", "operation": "create", "input": {...}}
    """
    body = await request.json()
    dto = body.get("dto", "")
    operation = body.get("operation", "create")
    input_data = body.get("input", {})

    if not dto:
        raise HTTPException(400, "dto is required")

    ctx = await engine.execute(dto, operation, input_data)

    return {
        "success": ctx.success,
        "result": ctx.result,
        "errors": ctx.errors,
        "trace": ctx.trace,
    }


# --- Resonate ---

@app.get("/resonate/{query}")
async def resonate(query: str, k: int = 10):
    """Find nodes similar to query by Hamming resonance."""
    # Generate query vector from text (using hash-based projection for now)
    import hashlib
    h = hashlib.sha256(query.encode()).digest()
    # Expand hash to 1024 floats for projection
    expanded = np.frombuffer((h * 32)[:1024], dtype=np.float32)
    query_vec = project(expanded)
    results = await store.find_similar_nodes(query_vec, k=k)

    return {
        "query": query,
        "results": [
            {
                "id": r.get("id"),
                "type": r.get("type"),
                "distance": r.get("_distance"),
            }
            for r in results
        ],
    }


# --- mRNA binary endpoint ---

MRNA_CONTENT_TYPE = "application/x-mrna-10k"


@app.post("/mrna")
async def mrna_receive(request: Request):
    """Receive raw mRNA packet (1250 bytes resonance).

    Content-Type: application/x-mrna-10k
    """
    content_type = request.headers.get("content-type", "")

    if MRNA_CONTENT_TYPE in content_type:
        raw = await request.body()
        if len(raw) < PACKED:
            raise HTTPException(400, f"need at least {PACKED} bytes, got {len(raw)}")

        resonance = raw[:PACKED]
        results = await store.find_similar_nodes(resonance, k=5)
        best = results[0] if results else None

        if best:
            resp_vec = bytes(PACKED)  # placeholder echo
            return Response(content=resp_vec, media_type=MRNA_CONTENT_TYPE)

        return Response(status_code=204)

    # JSON fallback
    body = await request.json()
    resonance_hex = body.get("resonance", "")
    if resonance_hex:
        resonance = bytes.fromhex(resonance_hex)
        results = await store.find_similar_nodes(resonance, k=5)
        return {"matches": len(results), "results": results}

    raise HTTPException(400, "provide resonance as binary or hex")


# --- Stats ---

@app.get("/stats")
async def stats():
    """Execution statistics."""
    slowest = await store.get_slowest_nodes(10)
    return {"slowest_nodes": slowest}


# --- Explain ---

@app.get("/explain/{node_id}")
async def explain(node_id: str):
    """Explain a node failure."""
    if not store.duck:
        raise HTTPException(503, "DuckDB not available")

    result = store.duck.execute(
        """
        SELECT node_id, error, timestamp
        FROM execution_log
        WHERE node_id = ? AND NOT success
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        [node_id],
    ).fetchone()

    if not result:
        return {"node_id": node_id, "status": "no failures recorded"}

    upstream = await store.get_upstream_nodes(node_id)

    return {
        "node_id": result[0],
        "error": result[1],
        "timestamp": str(result[2]),
        "upstream": upstream,
    }


# --- Entry point ---

def main():
    import uvicorn

    print(f"Firefly server starting")
    print(f"  Environment: {'Railway' if RAILWAY else 'local'}")
    print(f"  Bind:        {HOST}:{PORT}")
    print(f"  Data:        {DATA_DIR}")

    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        reload=not RAILWAY,
    )


if __name__ == "__main__":
    main()
