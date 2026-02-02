"""
RUBBERDUCK - Self-Analyzing Audit System

Rubberduck analyzes LadybugDB itself, creating a feedback loop:
1. Parse LadybugDB source code
2. Build graph of its own structure
3. Detect antipatterns in its own code
4. Suggest improvements
5. Track improvements over time

This is the audit loop that enables RL pattern detection.
"""

import os
import ast
import sys
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

# Import LadybugDB components
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from antipatterns import AntipatternDetector, SmellReport, SmellType, Smell
    from meta import MetaGraph, NodeType as MetaNodeType
    from nars import NARSGraph, NodeType as NarsNodeType, TruthValue
except ImportError:
    # Fallback for standalone testing
    pass


# =============================================================================
# AUDIT REPORT
# =============================================================================

@dataclass
class AuditReport:
    """Complete audit report for a codebase."""
    timestamp: str
    files_analyzed: int
    total_nodes: int
    total_edges: int
    smells: Dict[str, List[dict]]
    metrics: Dict[str, float]
    recommendations: List[str]
    score: float  # 0-100 quality score
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "files_analyzed": self.files_analyzed,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "smells": self.smells,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "score": self.score
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AuditDelta:
    """Change between two audits."""
    previous_score: float
    current_score: float
    delta_score: float
    new_smells: List[str]
    fixed_smells: List[str]
    recommendations: List[str]


# =============================================================================
# RUBBERDUCK AUDITOR
# =============================================================================

class Rubberduck:
    """
    Self-analyzing audit system.
    
    Named after rubber duck debugging - explaining code to find issues.
    """
    
    def __init__(self, target_dir: str = None):
        self.target_dir = target_dir or os.path.dirname(os.path.abspath(__file__))
        self.detector = None
        self.history: List[AuditReport] = []
        
    def _init_detector(self):
        """Initialize antipattern detector."""
        try:
            from antipatterns import AntipatternDetector
            self.detector = AntipatternDetector()
        except ImportError:
            # Minimal detector for standalone
            self.detector = MinimalDetector()
    
    def parse_file(self, filepath: str) -> List[dict]:
        """Parse a Python file into nodes."""
        nodes = []
        
        try:
            with open(filepath, 'r') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    nodes.append({
                        'type': 'CLASS',
                        'name': node.name,
                        'line': node.lineno,
                        'file': filepath
                    })
                elif isinstance(node, ast.FunctionDef):
                    # Count lines
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                    line_count = end_line - node.lineno
                    
                    # Count params
                    param_count = len(node.args.args)
                    
                    # Estimate nesting depth
                    nesting = self._estimate_nesting(node)
                    
                    nodes.append({
                        'type': 'METHOD' if self._is_method(node, tree) else 'FUNCTION',
                        'name': node.name,
                        'line': node.lineno,
                        'line_count': line_count,
                        'param_count': param_count,
                        'nesting_depth': nesting,
                        'file': filepath
                    })
        except Exception as e:
            print(f"  Warning: Could not parse {filepath}: {e}")
        
        return nodes
    
    def _is_method(self, func_node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Check if function is a method (inside class)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item is func_node:
                        return True
        return False
    
    def _estimate_nesting(self, node: ast.FunctionDef) -> int:
        """Estimate max nesting depth in function."""
        max_depth = 0
        
        def walk_depth(n, depth):
            nonlocal max_depth
            if isinstance(n, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                depth += 1
                max_depth = max(max_depth, depth)
            
            for child in ast.iter_child_nodes(n):
                walk_depth(child, depth)
        
        walk_depth(node, 0)
        return max_depth
    
    def analyze_directory(self, directory: str = None) -> AuditReport:
        """Analyze all Python files in directory."""
        directory = directory or self.target_dir
        
        print(f"\n{'='*60}")
        print(f"RUBBERDUCK AUDIT: {directory}")
        print(f"{'='*60}")
        
        self._init_detector()
        
        all_nodes = []
        files_analyzed = 0
        
        # Find all Python files
        for root, dirs, files in os.walk(directory):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for fname in files:
                if fname.endswith('.py'):
                    filepath = os.path.join(root, fname)
                    print(f"  Parsing: {filepath}")
                    nodes = self.parse_file(filepath)
                    all_nodes.extend(nodes)
                    files_analyzed += 1
        
        print(f"\n  Total files: {files_analyzed}")
        print(f"  Total nodes: {len(all_nodes)}")
        
        # Build detector graph
        if hasattr(self.detector, 'module'):
            mod = self.detector.module("audit_target")
            
            class_nodes = {}
            for n in all_nodes:
                if n['type'] == 'CLASS':
                    cls = self.detector.class_(n['name'], mod)
                    class_nodes[n['name']] = cls
            
            for n in all_nodes:
                if n['type'] in ('METHOD', 'FUNCTION'):
                    # Find parent class
                    parent = None
                    for cls_name, cls_node in class_nodes.items():
                        # Simple heuristic: check if method follows class in same file
                        parent = cls_node
                        break
                    
                    self.detector.method(
                        n['name'], 
                        body="", 
                        parent=parent,
                        line_count=n.get('line_count', 5),
                        param_count=n.get('param_count', 2),
                        nesting_depth=n.get('nesting_depth', 1)
                    )
        
        # Run detection
        smells = {}
        if hasattr(self.detector, 'detect_all'):
            results = self.detector.detect_all()
            for smell_type, reports in results.items():
                smell_name = smell_type.name if hasattr(smell_type, 'name') else str(smell_type)
                smells[smell_name] = [
                    {
                        'node': r.node.name,
                        'confidence': r.confidence,
                        'evidence': r.evidence,
                        'fix': r.suggested_fix
                    }
                    for r in reports
                ]
        
        # Calculate metrics
        metrics = self._calculate_metrics(all_nodes)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(smells, metrics)
        
        # Calculate quality score
        score = self._calculate_score(smells, metrics)
        
        report = AuditReport(
            timestamp=datetime.now().isoformat(),
            files_analyzed=files_analyzed,
            total_nodes=len(all_nodes),
            total_edges=len(self.detector.edges) if hasattr(self.detector, 'edges') else 0,
            smells=smells,
            metrics=metrics,
            recommendations=recommendations,
            score=score
        )
        
        self.history.append(report)
        
        return report
    
    def _calculate_metrics(self, nodes: List[dict]) -> Dict[str, float]:
        """Calculate quality metrics."""
        metrics = {}
        
        # Method count
        methods = [n for n in nodes if n['type'] in ('METHOD', 'FUNCTION')]
        classes = [n for n in nodes if n['type'] == 'CLASS']
        
        metrics['total_methods'] = len(methods)
        metrics['total_classes'] = len(classes)
        
        if methods:
            # Average method length
            lengths = [n.get('line_count', 0) for n in methods]
            metrics['avg_method_length'] = sum(lengths) / len(lengths)
            metrics['max_method_length'] = max(lengths) if lengths else 0
            
            # Average params
            params = [n.get('param_count', 0) for n in methods]
            metrics['avg_params'] = sum(params) / len(params)
            metrics['max_params'] = max(params) if params else 0
            
            # Average nesting
            nesting = [n.get('nesting_depth', 0) for n in methods]
            metrics['avg_nesting'] = sum(nesting) / len(nesting)
            metrics['max_nesting'] = max(nesting) if nesting else 0
        
        if classes:
            # Methods per class
            metrics['methods_per_class'] = len(methods) / len(classes)
        
        return metrics
    
    def _generate_recommendations(self, smells: Dict, metrics: Dict) -> List[str]:
        """Generate actionable recommendations."""
        recs = []
        
        # Based on smells
        smell_counts = {k: len(v) for k, v in smells.items()}
        
        if smell_counts.get('GOD_CLASS', 0) > 0:
            recs.append("CRITICAL: Split large classes into focused single-responsibility classes")
        
        if smell_counts.get('CIRCULAR_DEPENDENCY', 0) > 0:
            recs.append("CRITICAL: Break circular dependencies using interfaces or events")
        
        if smell_counts.get('LONG_METHOD', 0) > 0:
            recs.append("HIGH: Extract long methods into smaller, focused functions")
        
        if smell_counts.get('DEEP_NESTING', 0) > 0:
            recs.append("HIGH: Flatten deeply nested code using early returns and guard clauses")
        
        if smell_counts.get('FEATURE_ENVY', 0) > 0:
            recs.append("MEDIUM: Move envious methods to the class they use most")
        
        if smell_counts.get('DEAD_CODE', 0) > 0:
            recs.append("LOW: Remove or document dead code")
        
        # Based on metrics
        if metrics.get('avg_method_length', 0) > 30:
            recs.append("HIGH: Average method length too high - target < 30 lines")
        
        if metrics.get('avg_params', 0) > 4:
            recs.append("MEDIUM: Too many parameters on average - use parameter objects")
        
        if metrics.get('methods_per_class', 0) > 10:
            recs.append("HIGH: Too many methods per class - consider splitting")
        
        return recs
    
    def _calculate_score(self, smells: Dict, metrics: Dict) -> float:
        """Calculate quality score 0-100."""
        score = 100.0
        
        # Deduct for smells
        smell_weights = {
            'GOD_CLASS': 10,
            'CIRCULAR_DEPENDENCY': 15,
            'LONG_METHOD': 5,
            'DEEP_NESTING': 5,
            'FEATURE_ENVY': 3,
            'DEAD_CODE': 2,
            'LONG_PARAMETER_LIST': 3,
            'DUPLICATED_CODE': 8,
            'SPAGHETTI': 7,
            'SHOTGUN_SURGERY': 5
        }
        
        for smell_name, reports in smells.items():
            weight = smell_weights.get(smell_name, 3)
            score -= len(reports) * weight
        
        # Deduct for bad metrics
        if metrics.get('avg_method_length', 0) > 30:
            score -= (metrics['avg_method_length'] - 30) * 0.5
        
        if metrics.get('max_nesting', 0) > 4:
            score -= (metrics['max_nesting'] - 4) * 3
        
        return max(0, min(100, score))
    
    def compare_to_previous(self) -> Optional[AuditDelta]:
        """Compare current audit to previous."""
        if len(self.history) < 2:
            return None
        
        current = self.history[-1]
        previous = self.history[-2]
        
        current_smells = set()
        for smell_name, reports in current.smells.items():
            for r in reports:
                current_smells.add(f"{smell_name}:{r['node']}")
        
        previous_smells = set()
        for smell_name, reports in previous.smells.items():
            for r in reports:
                previous_smells.add(f"{smell_name}:{r['node']}")
        
        new_smells = list(current_smells - previous_smells)
        fixed_smells = list(previous_smells - current_smells)
        
        return AuditDelta(
            previous_score=previous.score,
            current_score=current.score,
            delta_score=current.score - previous.score,
            new_smells=new_smells,
            fixed_smells=fixed_smells,
            recommendations=current.recommendations
        )
    
    def print_report(self, report: AuditReport):
        """Print formatted report."""
        print(f"\n{'='*60}")
        print(f"AUDIT REPORT - {report.timestamp}")
        print(f"{'='*60}")
        
        print(f"\nFILES ANALYZED: {report.files_analyzed}")
        print(f"TOTAL NODES: {report.total_nodes}")
        print(f"TOTAL EDGES: {report.total_edges}")
        
        print(f"\nQUALITY SCORE: {report.score:.1f}/100")
        
        print(f"\n{'─'*60}")
        print("METRICS")
        print(f"{'─'*60}")
        for k, v in report.metrics.items():
            print(f"  {k}: {v:.2f}")
        
        print(f"\n{'─'*60}")
        print("SMELLS DETECTED")
        print(f"{'─'*60}")
        for smell_name, reports in report.smells.items():
            print(f"\n  [{smell_name}] - {len(reports)} instance(s)")
            for r in reports[:3]:  # Show first 3
                print(f"    • {r['node']} (conf={r['confidence']:.2f})")
                print(f"      Fix: {r['fix']}")
        
        print(f"\n{'─'*60}")
        print("RECOMMENDATIONS")
        print(f"{'─'*60}")
        for rec in report.recommendations:
            print(f"  • {rec}")
        
        print(f"\n{'='*60}")


# =============================================================================
# MINIMAL DETECTOR (fallback)
# =============================================================================

class MinimalDetector:
    """Minimal detector for standalone testing."""
    
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self._next_id = 0
    
    def module(self, name):
        return self._add_node('MODULE', name)
    
    def class_(self, name, parent=None):
        return self._add_node('CLASS', name)
    
    def method(self, name, body="", parent=None, line_count=5, param_count=2, nesting_depth=1):
        node = self._add_node('METHOD', name)
        node.line_count = line_count
        node.param_count = param_count
        node.nesting_depth = nesting_depth
        return node
    
    def _add_node(self, node_type, name):
        node = type('Node', (), {'id': self._next_id, 'name': name, 'type': node_type})()
        self.nodes[self._next_id] = node
        self._next_id += 1
        return node
    
    def detect_all(self):
        return {}


# =============================================================================
# MAIN
# =============================================================================

def audit_ladybugdb():
    """Audit LadybugDB itself."""
    # Get ladybug directory
    ladybug_dir = os.path.dirname(os.path.abspath(__file__))
    
    duck = Rubberduck(ladybug_dir)
    report = duck.analyze_directory()
    duck.print_report(report)
    
    return report


def audit_self():
    """Audit just this file."""
    duck = Rubberduck()
    
    # Parse just this file
    this_file = os.path.abspath(__file__)
    nodes = duck.parse_file(this_file)
    
    print(f"\nSELF-AUDIT: {this_file}")
    print(f"  Classes: {len([n for n in nodes if n['type'] == 'CLASS'])}")
    print(f"  Methods: {len([n for n in nodes if n['type'] == 'METHOD'])}")
    print(f"  Functions: {len([n for n in nodes if n['type'] == 'FUNCTION'])}")
    
    # Find longest method
    methods = [n for n in nodes if n['type'] in ('METHOD', 'FUNCTION')]
    if methods:
        longest = max(methods, key=lambda m: m.get('line_count', 0))
        print(f"  Longest: {longest['name']} ({longest.get('line_count', 0)} lines)")
        
        deepest = max(methods, key=lambda m: m.get('nesting_depth', 0))
        print(f"  Deepest: {deepest['name']} (depth={deepest.get('nesting_depth', 0)})")
    
    return nodes


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--self":
        audit_self()
    else:
        audit_ladybugdb()
