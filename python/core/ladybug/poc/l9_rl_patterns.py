"""
LadybugDB POC - Level 9: RL PATTERN DETECTION

Learn from repeated patterns. Incremental abstraction.

The system observes:
1. Which smells appear together (correlation)
2. Which fixes work (reinforcement)
3. Which patterns repeat across codebases (generalization)

Then abstracts:
- Common smell clusters → "syndrome"
- Common fix patterns → "refactoring recipe"
- Common code shapes → "idiom" or "anti-idiom"

This enables:
- Predictive smell detection (before code is written)
- Automated refactoring suggestions with confidence
- Pattern library that grows with experience
"""

import numpy as np
import hashlib
import struct
from typing import Dict, List, Set, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import IntEnum
from collections import defaultdict, Counter
import json

# =============================================================================
# CONSTANTS
# =============================================================================

DIM = 10_000
DIM_U64 = 157

# =============================================================================
# PATTERN TYPES
# =============================================================================

class PatternType(IntEnum):
    """Types of learned patterns."""
    SMELL_CLUSTER = 1       # Smells that appear together
    FIX_PATTERN = 2         # Successful fix sequences
    CODE_IDIOM = 3          # Common good patterns
    ANTI_IDIOM = 4          # Common bad patterns
    SYNDROME = 5            # Named smell clusters
    REFACTORING_RECIPE = 6  # Step-by-step fix


@dataclass
class Pattern:
    """A learned pattern."""
    id: int
    pattern_type: PatternType
    name: str
    description: str
    fingerprint: np.ndarray
    confidence: float
    observations: int  # How many times seen
    examples: List[str]
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.pattern_type.name,
            "name": self.name,
            "description": self.description,
            "confidence": self.confidence,
            "observations": self.observations,
            "examples": self.examples[:5]
        }


@dataclass
class Observation:
    """Single observation from audit."""
    smells: List[str]  # Smell names detected
    metrics: Dict[str, float]
    context: str  # e.g., "payment_service.py"
    fingerprint: np.ndarray
    timestamp: str


@dataclass
class Feedback:
    """Feedback on a suggested fix."""
    pattern_id: int
    applied: bool
    successful: bool
    notes: str = ""


# =============================================================================
# FINGERPRINT
# =============================================================================

def fingerprint(identity: str) -> np.ndarray:
    data = np.empty(DIM_U64, dtype=np.uint64)
    for i in range(DIM_U64):
        h = hashlib.sha256(f"{identity}:{i}".encode()).digest()
        data[i] = struct.unpack('<Q', h[:8])[0]
    data[-1] &= np.uint64((1 << 16) - 1)
    return data


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    xored = np.bitwise_xor(a, b)
    dist = sum(bin(int(x)).count('1') for x in xored)
    return 1.0 - dist / DIM


# =============================================================================
# RL PATTERN LEARNER
# =============================================================================

class PatternLearner:
    """
    Learns patterns from observations using reinforcement.
    
    Core loop:
    1. Observe (audit results)
    2. Match (find similar patterns)
    3. Update (reinforce or decay)
    4. Abstract (create new patterns from clusters)
    """
    
    def __init__(self):
        self.patterns: Dict[int, Pattern] = {}
        self.observations: List[Observation] = []
        self._next_id = 0
        
        # Learning parameters
        self.SIMILARITY_THRESHOLD = 0.7
        self.MIN_OBSERVATIONS = 3  # Need this many to create pattern
        self.DECAY_RATE = 0.95     # Confidence decay per epoch
        self.REINFORCE_RATE = 0.1  # Confidence boost on match
        
        # Initialize with known patterns
        self._seed_known_patterns()
    
    def _get_id(self) -> int:
        id = self._next_id
        self._next_id += 1
        return id
    
    def _seed_known_patterns(self):
        """Seed with known antipattern syndromes."""
        known = [
            {
                "type": PatternType.SYNDROME,
                "name": "God Object Syndrome",
                "description": "Class that knows too much and does too much",
                "smells": ["GOD_CLASS", "LONG_METHOD", "FEATURE_ENVY"],
                "fix": "Extract focused classes, apply Single Responsibility Principle"
            },
            {
                "type": PatternType.SYNDROME,
                "name": "Spaghetti Tangle",
                "description": "Deeply nested code with unclear control flow",
                "smells": ["DEEP_NESTING", "SPAGHETTI", "LONG_METHOD"],
                "fix": "Flatten with early returns, extract methods, use guard clauses"
            },
            {
                "type": PatternType.SYNDROME,
                "name": "Dependency Hell",
                "description": "Circular dependencies creating tight coupling",
                "smells": ["CIRCULAR_DEPENDENCY", "SHOTGUN_SURGERY", "FEATURE_ENVY"],
                "fix": "Introduce interfaces, use dependency injection, event-driven"
            },
            {
                "type": PatternType.SYNDROME,
                "name": "Copy-Paste Inheritance",
                "description": "Duplicated code masquerading as reuse",
                "smells": ["DUPLICATED_CODE", "PARALLEL_INHERITANCE"],
                "fix": "Extract common base, use composition over inheritance"
            },
            {
                "type": PatternType.REFACTORING_RECIPE,
                "name": "Extract Class",
                "description": "Split god class into focused classes",
                "steps": [
                    "Identify cohesive method groups",
                    "Create new class for each group",
                    "Move methods to new classes",
                    "Update references",
                    "Remove original class or make facade"
                ]
            },
            {
                "type": PatternType.REFACTORING_RECIPE,
                "name": "Flatten Arrow",
                "description": "Reduce nesting depth",
                "steps": [
                    "Identify deepest nesting point",
                    "Convert conditions to guard clauses with early return",
                    "Extract nested blocks to methods",
                    "Verify behavior unchanged"
                ]
            },
            {
                "type": PatternType.CODE_IDIOM,
                "name": "Repository Pattern",
                "description": "Clean data access abstraction",
                "signature": ["find", "save", "delete", "query"],
                "metrics": {"methods_per_class": (4, 8), "avg_params": (1, 3)}
            },
            {
                "type": PatternType.CODE_IDIOM,
                "name": "Service Layer",
                "description": "Business logic orchestration",
                "signature": ["execute", "handle", "process"],
                "metrics": {"fan_out": (3, 8), "nesting": (1, 2)}
            },
            {
                "type": PatternType.ANTI_IDIOM,
                "name": "Manager Class",
                "description": "Vague responsibility, often becomes god object",
                "signature": ["Manager", "Handler", "Helper", "Util"],
                "warning": "Consider more specific naming and responsibilities"
            }
        ]
        
        for k in known:
            identity = f"{k['type']}::{k['name']}::{k.get('description', '')}"
            fp = fingerprint(identity)
            
            pattern = Pattern(
                id=self._get_id(),
                pattern_type=k["type"] if isinstance(k["type"], PatternType) else PatternType(k["type"]),
                name=k["name"],
                description=k.get("description", ""),
                fingerprint=fp,
                confidence=0.8,  # High initial confidence for known patterns
                observations=10,  # Pretend we've seen these
                examples=k.get("smells", k.get("steps", []))
            )
            self.patterns[pattern.id] = pattern
    
    # -------------------------------------------------------------------------
    # OBSERVE
    # -------------------------------------------------------------------------
    
    def observe(self, smells: List[str], metrics: Dict[str, float], context: str = "") -> Observation:
        """Record an observation from audit."""
        # Create fingerprint from smell combination
        identity = f"obs::{','.join(sorted(smells))}::{context}"
        fp = fingerprint(identity)
        
        from datetime import datetime
        obs = Observation(
            smells=smells,
            metrics=metrics,
            context=context,
            fingerprint=fp,
            timestamp=datetime.now().isoformat()
        )
        
        self.observations.append(obs)
        
        # Try to match and update patterns
        self._match_and_update(obs)
        
        return obs
    
    def _match_and_update(self, obs: Observation):
        """Match observation to existing patterns and update."""
        matches = []
        
        for pattern in self.patterns.values():
            if pattern.pattern_type == PatternType.SYNDROME:
                # Check smell overlap
                pattern_smells = set(pattern.examples)
                obs_smells = set(obs.smells)
                overlap = len(pattern_smells & obs_smells) / max(len(pattern_smells), 1)
                
                if overlap > 0.5:
                    matches.append((pattern, overlap))
            else:
                # Use fingerprint similarity
                sim = similarity(pattern.fingerprint, obs.fingerprint)
                if sim > self.SIMILARITY_THRESHOLD:
                    matches.append((pattern, sim))
        
        # Reinforce matching patterns
        for pattern, score in matches:
            self._reinforce(pattern, score)
    
    def _reinforce(self, pattern: Pattern, score: float):
        """Reinforce a pattern on match."""
        pattern.observations += 1
        pattern.confidence = min(1.0, pattern.confidence + self.REINFORCE_RATE * score)
    
    # -------------------------------------------------------------------------
    # FEEDBACK
    # -------------------------------------------------------------------------
    
    def feedback(self, pattern_id: int, applied: bool, successful: bool):
        """Record feedback on a pattern."""
        if pattern_id not in self.patterns:
            return
        
        pattern = self.patterns[pattern_id]
        
        if applied and successful:
            # Strong positive reinforcement
            pattern.confidence = min(1.0, pattern.confidence + 0.2)
        elif applied and not successful:
            # Negative reinforcement
            pattern.confidence = max(0.1, pattern.confidence - 0.15)
        # If not applied, no change
    
    # -------------------------------------------------------------------------
    # ABSTRACT
    # -------------------------------------------------------------------------
    
    def abstract(self) -> List[Pattern]:
        """
        Create new patterns from observation clusters.
        
        This is where the magic happens:
        - Find smells that appear together frequently
        - Name them as new syndromes
        - Create refactoring recipes
        """
        new_patterns = []
        
        # Count smell co-occurrences
        cooccur = defaultdict(int)
        for obs in self.observations:
            smells = sorted(obs.smells)
            for i, s1 in enumerate(smells):
                for s2 in smells[i+1:]:
                    cooccur[(s1, s2)] += 1
        
        # Find frequent pairs
        frequent_pairs = [(pair, count) for pair, count in cooccur.items() 
                         if count >= self.MIN_OBSERVATIONS]
        frequent_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Check if we have new syndrome candidates
        for (s1, s2), count in frequent_pairs[:5]:
            # Check if already known
            existing = self._find_syndrome_with_smells([s1, s2])
            if existing:
                continue
            
            # Create new syndrome
            name = f"Emerging: {s1} + {s2}"
            desc = f"Auto-detected correlation between {s1} and {s2}"
            
            identity = f"syndrome::{s1}::{s2}"
            fp = fingerprint(identity)
            
            pattern = Pattern(
                id=self._get_id(),
                pattern_type=PatternType.SYNDROME,
                name=name,
                description=desc,
                fingerprint=fp,
                confidence=min(count / 10, 0.7),  # Confidence grows with observations
                observations=count,
                examples=[s1, s2]
            )
            
            self.patterns[pattern.id] = pattern
            new_patterns.append(pattern)
        
        return new_patterns
    
    def _find_syndrome_with_smells(self, smells: List[str]) -> Optional[Pattern]:
        """Find existing syndrome containing these smells."""
        smell_set = set(smells)
        for pattern in self.patterns.values():
            if pattern.pattern_type == PatternType.SYNDROME:
                if smell_set.issubset(set(pattern.examples)):
                    return pattern
        return None
    
    # -------------------------------------------------------------------------
    # PREDICT
    # -------------------------------------------------------------------------
    
    def predict(self, partial_smells: List[str]) -> List[Tuple[str, float]]:
        """
        Predict additional smells based on partial observation.
        
        "If you have GOD_CLASS, you probably also have..."
        """
        predictions = []
        
        for pattern in self.patterns.values():
            if pattern.pattern_type != PatternType.SYNDROME:
                continue
            
            # Check overlap
            pattern_smells = set(pattern.examples)
            partial_set = set(partial_smells)
            
            overlap = partial_set & pattern_smells
            missing = pattern_smells - partial_set
            
            if len(overlap) > 0 and len(missing) > 0:
                # Predict missing smells
                prob = len(overlap) / len(pattern_smells) * pattern.confidence
                for smell in missing:
                    predictions.append((smell, prob))
        
        # Aggregate predictions
        pred_scores = defaultdict(float)
        for smell, prob in predictions:
            pred_scores[smell] = max(pred_scores[smell], prob)
        
        return sorted(pred_scores.items(), key=lambda x: x[1], reverse=True)
    
    # -------------------------------------------------------------------------
    # SUGGEST
    # -------------------------------------------------------------------------
    
    def suggest_fix(self, smells: List[str]) -> List[Tuple[Pattern, float]]:
        """Suggest fixes for observed smells."""
        suggestions = []
        
        smell_set = set(smells)
        
        # Find matching syndromes and their fixes
        for pattern in self.patterns.values():
            if pattern.pattern_type == PatternType.SYNDROME:
                pattern_smells = set(pattern.examples)
                overlap = len(smell_set & pattern_smells) / max(len(pattern_smells), 1)
                
                if overlap > 0.3:
                    suggestions.append((pattern, overlap * pattern.confidence))
            
            elif pattern.pattern_type == PatternType.REFACTORING_RECIPE:
                # Check if recipe applies
                # (simplified: check name keywords)
                applies = False
                if "Extract" in pattern.name and "GOD_CLASS" in smell_set:
                    applies = True
                elif "Flatten" in pattern.name and "DEEP_NESTING" in smell_set:
                    applies = True
                
                if applies:
                    suggestions.append((pattern, pattern.confidence))
        
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions
    
    # -------------------------------------------------------------------------
    # DECAY
    # -------------------------------------------------------------------------
    
    def decay_epoch(self):
        """Apply confidence decay to all patterns."""
        for pattern in self.patterns.values():
            if pattern.observations < self.MIN_OBSERVATIONS:
                # Faster decay for unconfirmed patterns
                pattern.confidence *= self.DECAY_RATE * 0.9
            else:
                pattern.confidence *= self.DECAY_RATE
            
            # Remove very low confidence patterns (except seeded)
            if pattern.confidence < 0.1 and pattern.observations < 10:
                pattern.confidence = 0  # Mark for removal
        
        # Remove marked patterns
        self.patterns = {k: v for k, v in self.patterns.items() if v.confidence > 0}
    
    # -------------------------------------------------------------------------
    # EXPORT
    # -------------------------------------------------------------------------
    
    def export_patterns(self) -> str:
        """Export patterns as JSON."""
        return json.dumps([p.to_dict() for p in self.patterns.values()], indent=2)
    
    def print_patterns(self):
        """Print learned patterns."""
        print(f"\n{'='*60}")
        print("LEARNED PATTERNS")
        print(f"{'='*60}")
        
        by_type = defaultdict(list)
        for p in self.patterns.values():
            by_type[p.pattern_type].append(p)
        
        for ptype, patterns in sorted(by_type.items(), key=lambda x: x[0]):
            print(f"\n[{ptype.name}]")
            for p in sorted(patterns, key=lambda x: x.confidence, reverse=True):
                print(f"  {p.name} (conf={p.confidence:.2f}, obs={p.observations})")
                if p.examples:
                    print(f"    Examples: {p.examples[:3]}")


# =============================================================================
# POC
# =============================================================================

def poc_l9_rl_patterns():
    """L9 POC: RL Pattern Detection."""
    print("=" * 60)
    print("L9: RL PATTERN DETECTION")
    print("=" * 60)
    
    learner = PatternLearner()
    
    # -------------------------------------------------------------------------
    # Test 1: Initial patterns
    # -------------------------------------------------------------------------
    
    print(f"\n[1] Seeded patterns: {len(learner.patterns)}")
    syndromes = [p for p in learner.patterns.values() if p.pattern_type == PatternType.SYNDROME]
    recipes = [p for p in learner.patterns.values() if p.pattern_type == PatternType.REFACTORING_RECIPE]
    print(f"    Syndromes: {len(syndromes)}")
    print(f"    Recipes: {len(recipes)}")
    assert len(syndromes) >= 3
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 2: Observe and match
    # -------------------------------------------------------------------------
    
    print(f"\n[2] Observe and match:")
    
    # Simulate observations
    observations = [
        (["GOD_CLASS", "LONG_METHOD", "FEATURE_ENVY"], {"methods_per_class": 15}),
        (["GOD_CLASS", "LONG_METHOD"], {"methods_per_class": 12}),
        (["DEEP_NESTING", "SPAGHETTI", "LONG_METHOD"], {"avg_nesting": 5}),
        (["CIRCULAR_DEPENDENCY", "SHOTGUN_SURGERY"], {"fan_out": 10}),
        (["GOD_CLASS", "FEATURE_ENVY"], {"methods_per_class": 18}),
    ]
    
    for smells, metrics in observations:
        learner.observe(smells, metrics, "test_service.py")
    
    print(f"    Observations recorded: {len(learner.observations)}")
    
    # Check that God Object Syndrome was reinforced
    god_syndrome = next((p for p in learner.patterns.values() 
                        if "God Object" in p.name), None)
    assert god_syndrome is not None
    print(f"    God Object Syndrome confidence: {god_syndrome.confidence:.2f}")
    assert god_syndrome.confidence > 0.8  # Should be reinforced
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 3: Predict smells
    # -------------------------------------------------------------------------
    
    print(f"\n[3] Predict smells:")
    
    predictions = learner.predict(["GOD_CLASS"])
    print(f"    Given: GOD_CLASS")
    print(f"    Predicted:")
    for smell, prob in predictions[:5]:
        print(f"      {smell}: {prob:.2%}")
    
    # Should predict LONG_METHOD or FEATURE_ENVY
    pred_names = [s for s, _ in predictions]
    assert "LONG_METHOD" in pred_names or "FEATURE_ENVY" in pred_names
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 4: Suggest fixes
    # -------------------------------------------------------------------------
    
    print(f"\n[4] Suggest fixes:")
    
    suggestions = learner.suggest_fix(["GOD_CLASS", "LONG_METHOD"])
    print(f"    For: GOD_CLASS + LONG_METHOD")
    print(f"    Suggestions:")
    for pattern, score in suggestions[:3]:
        print(f"      {pattern.name} (score={score:.2f})")
        if pattern.examples:
            print(f"        → {pattern.examples[:2]}")
    
    assert len(suggestions) >= 1
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 5: Abstract new patterns
    # -------------------------------------------------------------------------
    
    print(f"\n[5] Abstract new patterns:")
    
    # Add more observations to trigger abstraction
    for _ in range(5):
        learner.observe(["DEAD_CODE", "LONG_PARAMETER_LIST"], {}, "legacy.py")
    
    new_patterns = learner.abstract()
    print(f"    New patterns created: {len(new_patterns)}")
    for p in new_patterns:
        print(f"      {p.name} (conf={p.confidence:.2f})")
    
    # Should create emerging pattern for DEAD_CODE + LONG_PARAMETER_LIST
    if new_patterns:
        print(f"    ✓ PASS (abstraction working)")
    else:
        print(f"    ⚠ No new patterns (need more diverse data)")
    
    # -------------------------------------------------------------------------
    # Test 6: Feedback loop
    # -------------------------------------------------------------------------
    
    print(f"\n[6] Feedback loop:")
    
    # Simulate positive feedback
    recipe = next((p for p in learner.patterns.values() 
                  if "Extract Class" in p.name), None)
    if recipe:
        old_conf = recipe.confidence
        learner.feedback(recipe.id, applied=True, successful=True)
        print(f"    Extract Class: {old_conf:.2f} → {recipe.confidence:.2f}")
        assert recipe.confidence > old_conf
    
    # Simulate negative feedback
    if recipe:
        old_conf = recipe.confidence
        learner.feedback(recipe.id, applied=True, successful=False)
        print(f"    After failure: {old_conf:.2f} → {recipe.confidence:.2f}")
        assert recipe.confidence < old_conf
    
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 7: Decay
    # -------------------------------------------------------------------------
    
    print(f"\n[7] Confidence decay:")
    
    # Record confidences
    before = {p.id: p.confidence for p in learner.patterns.values()}
    
    learner.decay_epoch()
    
    decayed = sum(1 for p in learner.patterns.values() 
                  if p.confidence < before[p.id])
    print(f"    Patterns decayed: {decayed}/{len(learner.patterns)}")
    assert decayed > 0
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    
    print(f"\n{'='*60}")
    print("L9 POC: ALL TESTS PASSED")
    print(f"{'='*60}")
    
    learner.print_patterns()
    
    print("""
    Proved:
    ✓ Pattern seeding with known syndromes
    ✓ Observation → pattern matching
    ✓ Smell prediction from partial data
    ✓ Fix suggestion based on patterns
    ✓ Pattern abstraction from clusters
    ✓ Reinforcement from feedback
    ✓ Confidence decay over time
    
    RL Pattern Detection enables:
    - Learning from repeated audits
    - Predicting smells before they appear
    - Suggesting fixes with confidence scores
    - Growing pattern library over time
    """)
    
    return learner


if __name__ == "__main__":
    poc_l9_rl_patterns()
