#!/bin/bash
# LadybugDB Docker Test Runner
# Usage: ./docker_test.sh

set -e

echo "============================================================"
echo "LADYBUGDB DOCKER TEST SUITE"
echo "============================================================"
echo "Started at: $(date)"
echo ""

# Change to ladybugdb directory
cd "$(dirname "$0")"

# Run all level POCs
echo "[LEVEL 1-5] Basic structure tests..."
python3 poc.py 2>&1 | grep -E "(L[0-9]+:|PASS|FAIL|✓|✗)"

echo ""
echo "[LEVEL 6] NARS Reasoning..."
python3 poc/l6_nars.py 2>&1 | grep -E "(✓|✗|PASS|FAIL)" | tail -20

echo ""
echo "[LEVEL 7] Meta-heuristics..."
python3 poc/l7_meta.py 2>&1 | grep -E "(✓|✗|PASS|FAIL)" | tail -20

echo ""
echo "[LEVEL 8] Antipattern Battery..."
python3 poc/l8_antipatterns.py 2>&1 | grep -E "(✓|✗|PASS|FAIL)" | tail -20

echo ""
echo "[LEVEL 9] RL Pattern Detection..."
python3 poc/l9_rl_patterns.py 2>&1 | grep -E "(✓|✗|PASS|FAIL|Proved:)" | tail -25

echo ""
echo "[LEVEL 10] TRANSCENDENCE..."
python3 poc/l10_transcendence.py 2>&1 | grep -E "(✓|✗|PASS|FAIL|EPIPHANY|Proved:)" | tail -30

echo ""
echo "[RUBBERDUCK] Self-audit..."
python3 rubberduck/auditor.py 2>&1 | grep -E "(QUALITY SCORE|FILES ANALYZED|NODES|RECOMMENDATIONS)"

echo ""
echo "============================================================"
echo "COMPLETE at: $(date)"
echo "============================================================"
