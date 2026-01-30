"""
Firefly Storage: Unified storage across LanceDB + DuckDB + Kuzu.

LanceDB: Vectors (resonance similarity search)
DuckDB:  Facts (catalog, analytics, SQL)
Kuzu:    Graph (execution topology, Cypher)

All three share data via Apache Arrow (zero-copy).
"""

import os
import shutil
from typing import List, Optional, Dict, Any
from pathlib import Path

import numpy as np

# Import will fail if not installed - handle gracefully
try:
    import lancedb
    HAS_LANCE = True
except ImportError:
    HAS_LANCE = False
    
try:
    import duckdb
    HAS_DUCK = True
except ImportError:
    HAS_DUCK = False

try:
    import kuzu
    HAS_KUZU = True
except ImportError:
    HAS_KUZU = False

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from core import similarity, PACKED


class FireflyStore:
    """
    Unified storage across three databases.
    
    Each database serves a specific purpose:
    - LanceDB: "What is similar?" (vector search)
    - DuckDB: "What are the facts?" (SQL analytics)
    - Kuzu: "How does it connect?" (graph traversal)
    """
    
    def __init__(self, path: str = "./firefly_data"):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        
        # Initialize databases
        self._init_lance()
        self._init_duck()
        self._init_kuzu()
    
    def _init_lance(self):
        """Initialize LanceDB for vector storage."""
        if not HAS_LANCE:
            print("⚠️  LanceDB not installed. Vector search disabled.")
            self.lance = None
            return
            
        lance_path = self.path / "lance"
        self.lance = lancedb.connect(str(lance_path))
        
        # Tables created on first insert
        self._lance_nodes_table = None
        self._lance_edges_table = None
    
    def _init_duck(self):
        """Initialize DuckDB for catalog/analytics."""
        if not HAS_DUCK:
            print("⚠️  DuckDB not installed. SQL analytics disabled.")
            self.duck = None
            return
            
        duck_path = self.path / "duck.db"
        self.duck = duckdb.connect(str(duck_path))
        
        # Create catalog tables
        self.duck.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id VARCHAR PRIMARY KEY,
                type VARCHAR,
                executor VARCHAR,
                fn_name VARCHAR,
                cost INTEGER,
                pure BOOLEAN,
                parallelizable BOOLEAN,
                input_schema JSON,
                output_schema JSON,
                created_at TIMESTAMP
            )
        """)
        
        self.duck.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id VARCHAR PRIMARY KEY,
                source_id VARCHAR,
                target_id VARCHAR,
                type VARCHAR,
                condition VARCHAR,
                field VARCHAR,
                created_at TIMESTAMP
            )
        """)
        
        self.duck.execute("""
            CREATE TABLE IF NOT EXISTS execution_log (
                id VARCHAR PRIMARY KEY,
                execution_id VARCHAR,
                node_id VARCHAR,
                duration_ms DOUBLE,
                success BOOLEAN,
                error VARCHAR,
                timestamp TIMESTAMP
            )
        """)
    
    def _init_kuzu(self):
        """Initialize Kuzu for graph storage."""
        if not HAS_KUZU:
            print("⚠️  Kuzu not installed. Graph traversal disabled.")
            self.kuzu = None
            self.kuzu_db = None
            return
            
        kuzu_path = self.path / "kuzu"
        
        # Try to init Kuzu. If it fails, nuke the directory and retry once.
        for attempt in range(2):
            try:
                if attempt > 0:
                    print(f"🔄 Kuzu retry attempt {attempt + 1}...")
                
                self.kuzu_db = kuzu.Database(str(kuzu_path))
                self.kuzu = kuzu.Connection(self.kuzu_db)
                
                # Create node table
                try:
                    self.kuzu.execute("""
                        CREATE NODE TABLE IF NOT EXISTS Node(
                            id STRING PRIMARY KEY,
                            type STRING,
                            executor STRING
                        )
                    """)
                except Exception as e:
                    # Log but continue - table might already exist
                    if "already exists" not in str(e).lower():
                        print(f"⚠️  Kuzu node table creation warning: {e}")

                # Create edge table
                try:
                    self.kuzu.execute("""
                        CREATE REL TABLE IF NOT EXISTS FLOWS(
                            FROM Node TO Node,
                            type STRING,
                            condition STRING
                        )
                    """)
                except Exception as e:
                    # Log but continue - table might already exist
                    if "already exists" not in str(e).lower():
                        print(f"⚠️  Kuzu edge table creation warning: {e}")
                
                print(f"✅ Kuzu initialized at {kuzu_path}")
                return  # Success!
                
            except Exception as e:
                print(f"⚠️  Kuzu init failed: {e}")
                
                # On first failure, nuke and retry
                if attempt == 0 and kuzu_path.exists():
                    print(f"🗑️  Removing corrupted Kuzu directory: {kuzu_path}")
                    try:
                        shutil.rmtree(kuzu_path)
                    except Exception as rm_err:
                        print(f"   Failed to remove: {rm_err}")
                        break
                else:
                    break
        
        # If we get here, Kuzu failed
        print("⚠️  Kuzu disabled. Graph traversal unavailable.")
        self.kuzu = None
        self.kuzu_db = None
    
    # =========================================================================
    # NODE OPERATIONS
    # =========================================================================
    
    async def store_node(self, node: FireflyNode):
        """Store node in all three databases."""
        
        # LanceDB: vector for similarity search
        if self.lance:
            data = [{
                "id": node.id,
                "vector": np.frombuffer(node.resonance, dtype=np.uint8).tolist(),
                "type": node.type,
            }]
            
            if self._lance_nodes_table is None:
                self._lance_nodes_table = self.lance.create_table("nodes", data)
            else:
                self._lance_nodes_table.add(data)
        
        # DuckDB: catalog for SQL queries
        if self.duck:
            import json
            self.duck.execute("""
                INSERT OR REPLACE INTO nodes 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                node.id,
                node.type,
                node.executor,
                node.fn_name,
                node.cost,
                node.pure,
                node.parallelizable,
                json.dumps(node.input_schema),
                json.dumps(node.output_schema),
                node.created_at,
            ])
        
        # Kuzu: graph for traversal
        if self.kuzu:
            try:
                self.kuzu.execute("""
                    MERGE (n:Node {id: $id})
                    SET n.type = $type, n.executor = $executor
                """, {
                    "id": node.id,
                    "type": node.type,
                    "executor": node.executor
                })
            except Exception as e:
                print(f"Kuzu insert error: {e}")
    
    async def get_node(self, node_id: str) -> Optional[FireflyNode]:
        """Get node by ID."""
        if not self.duck:
            return None
            
        result = self.duck.execute(
            "SELECT * FROM nodes WHERE id = ?", [node_id]
        ).fetchone()
        
        if not result:
            return None
        
        import json
        return FireflyNode(
            id=result[0],
            resonance=b'\0' * PACKED,  # Would need to fetch from Lance
            type=result[1],
            executor=result[2],
            fn_name=result[3],
            cost=result[4],
            pure=result[5],
            parallelizable=result[6],
            input_schema=json.loads(result[7]) if result[7] else {},
            output_schema=json.loads(result[8]) if result[8] else {},
        )
    
    async def find_similar_nodes(self, resonance: bytes, k: int = 10) -> List[dict]:
        """Find nodes with similar resonance (Hamming search)."""
        if not self.lance or self._lance_nodes_table is None:
            return []
        
        vector = np.frombuffer(resonance, dtype=np.uint8).tolist()
        
        results = (
            self._lance_nodes_table
            .search(vector)
            .metric("hamming")  # Native Hamming distance!
            .limit(k)
            .to_list()
        )
        
        return results
    
    # =========================================================================
    # EDGE OPERATIONS
    # =========================================================================
    
    async def store_edge(self, edge: FireflyEdge):
        """Store edge in all three databases."""
        
        # LanceDB: edge resonance for relationship similarity
        if self.lance:
            data = [{
                "id": edge.id,
                "vector": np.frombuffer(edge.resonance, dtype=np.uint8).tolist(),
                "type": edge.type,
            }]
            
            if self._lance_edges_table is None:
                self._lance_edges_table = self.lance.create_table("edges", data)
            else:
                self._lance_edges_table.add(data)
        
        # DuckDB: catalog
        if self.duck:
            self.duck.execute("""
                INSERT OR REPLACE INTO edges 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                edge.id,
                edge.source_id,
                edge.target_id,
                edge.type,
                edge.condition,
                edge.field,
                edge.created_at,
            ])
        
        # Kuzu: graph
        if self.kuzu:
            try:
                self.kuzu.execute("""
                    MATCH (s:Node {id: $source}), (t:Node {id: $target})
                    MERGE (s)-[r:FLOWS]->(t)
                    SET r.type = $type, r.condition = $condition
                """, {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.type,
                    "condition": edge.condition or "",
                })
            except Exception as e:
                print(f"Kuzu edge insert error: {e}")
    
    async def get_outgoing_edges(self, node_id: str) -> List[FireflyEdge]:
        """Get all edges from a node."""
        if not self.duck:
            return []
            
        results = self.duck.execute(
            "SELECT * FROM edges WHERE source_id = ?", [node_id]
        ).fetchall()
        
        edges = []
        for r in results:
            edges.append(FireflyEdge(
                id=r[0],
                source_id=r[1],
                target_id=r[2],
                resonance=b'\0' * PACKED,
                type=r[3],
                condition=r[4],
                field=r[5],
            ))
        return edges
    
    # =========================================================================
    # GRAPH QUERIES (Kuzu)
    # =========================================================================
    
    async def get_execution_path(self, start_id: str) -> List[dict]:
        """Get execution path starting from a node (Cypher query)."""
        if not self.kuzu:
            return []
        
        try:
            result = self.kuzu.execute("""
                MATCH path = (start:Node {id: $id})-[:FLOWS*]->(end:Node)
                WHERE NOT EXISTS { MATCH (end)-[:FLOWS]->() }
                RETURN [n IN nodes(path) | n.id] as node_ids
                LIMIT 1
            """, {"id": start_id})
            
            df = result.get_as_df()
            if df.empty:
                return []
            return df.to_dict('records')
        except Exception as e:
            print(f"Kuzu query error: {e}")
            return []
    
    async def get_upstream_nodes(self, node_id: str, hops: int = 3) -> List[str]:
        """Get nodes that feed into this node.

        Args:
            node_id: The target node ID
            hops: Maximum number of hops upstream (1-10, default 3)

        Returns:
            List of upstream node IDs
        """
        if not self.kuzu:
            return []

        # Validate hops to prevent injection (must be positive integer 1-10)
        hops = max(1, min(10, int(hops)))

        try:
            # Note: hops must be validated above since Cypher doesn't support
            # parameterized path lengths. The validation ensures it's safe.
            result = self.kuzu.execute(f"""
                MATCH (upstream:Node)-[:FLOWS*1..{hops}]->(target:Node {{id: $id}})
                RETURN DISTINCT upstream.id as id
            """, {"id": node_id})

            df = result.get_as_df()
            return df['id'].tolist() if not df.empty else []
        except Exception as e:
            print(f"Kuzu upstream query error: {e}")
            return []
    
    # =========================================================================
    # ANALYTICS (DuckDB)
    # =========================================================================
    
    async def log_execution(
        self, 
        execution_id: str, 
        node_id: str, 
        duration_ms: float, 
        success: bool,
        error: Optional[str] = None
    ):
        """Log node execution for analytics."""
        if not self.duck:
            return
        
        import uuid
        from datetime import datetime
        
        self.duck.execute("""
            INSERT INTO execution_log VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            str(uuid.uuid4()),
            execution_id,
            node_id,
            duration_ms,
            success,
            error,
            datetime.utcnow(),
        ])
    
    async def get_slowest_nodes(self, limit: int = 10) -> List[dict]:
        """Get slowest nodes by average execution time."""
        if not self.duck:
            return []
        
        results = self.duck.execute("""
            SELECT 
                node_id,
                COUNT(*) as executions,
                AVG(duration_ms) as avg_duration,
                MAX(duration_ms) as max_duration,
                SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures
            FROM execution_log
            GROUP BY node_id
            ORDER BY avg_duration DESC
            LIMIT ?
        """, [limit]).fetchall()
        
        return [
            {
                "node_id": r[0],
                "executions": r[1],
                "avg_duration": r[2],
                "max_duration": r[3],
                "failures": r[4],
            }
            for r in results
        ]
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def close(self):
        """Close all database connections."""
        if self.duck:
            self.duck.close()
        # Lance and Kuzu don't need explicit close
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
