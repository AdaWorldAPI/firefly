# Repositories to Analyze

## Overview

The ARCHAEOLOGIST agent should scrape these repositories to extract patterns and implementations that will be unified into Firefly.

---

## 1. AdaWorldAPI/agi-chat

**Purpose:** LadybugDB and graph execution patterns

**Extract:**
- [ ] LadybugDB implementation (Kuzu wrapper)
- [ ] Node schemas and types
- [ ] Edge schemas and types
- [ ] Graph execution patterns
- [ ] LangGraph influence/integration
- [ ] State management approach

**Key files to find:**
```
ladybug*.py
graph*.py
node*.py
edge*.py
executor*.py
```

---

## 2. AdaWorldAPI/bighorn

**Purpose:** AGI architecture and consciousness layers

**Extract:**
- [ ] AGI stack architecture
- [ ] Consciousness layer definitions
- [ ] VSA integration points
- [ ] Lance client patterns
- [ ] Extension architecture

**Key files to find:**
```
agi_stack/
extension/
lance*.py
consciousness*.py
layer*.py
```

---

## 3. AdaWorldAPI/dragonfly-vsa

**Purpose:** 10K Hamming bitpacking and VSA operations

**Extract:**
- [ ] 10K Hamming bitpacking (`uint8[1250]`)
- [ ] `bind()` implementation
- [ ] `bundle()` implementation  
- [ ] `similarity()` implementation
- [ ] AVX-512 optimizations (if any)
- [ ] CAM fingerprinting (48-bit)
- [ ] Mexican hat resonance
- [ ] Projection from float to binary

**Key files to find:**
```
resonance*.py
vsa*.py
hamming*.py
bind*.py
bundle*.py
projection*.py
```

---

## 4. AdaWorldAPI/vsa-flow

**Purpose:** mRNA packets and distributed routing

**Extract:**
- [ ] mRNA packet structure
- [ ] Routing header format (64 bytes)
- [ ] Redis stream patterns
- [ ] Consumer group architecture
- [ ] Multithreading model
- [ ] 2^10000 address space handling
- [ ] Backpressure mechanisms

**Key files to find:**
```
packet*.py
transport*.py
routing*.py
queue*.py
worker*.py
stream*.py
```

---

## 5. AdaWorldAPI/ada-consciousness

**Purpose:** 7-layer consciousness model

**Extract:**
- [ ] 7-layer model definitions
- [ ] Layer interactions
- [ ] Membrane integration (τ/σ/q ↔ 10K conversion)
- [ ] Capsule system
- [ ] Cross-service navigation
- [ ] State encoding

**Key files to find:**
```
layer*.py
membrane*.py
capsule*.py
consciousness*.py
state*.py
BOOT.md
```

---

## Extraction Script

```bash
#!/bin/bash
# extract_repos.sh

TOKEN="${GITHUB_TOKEN}"
REPOS=(
    "agi-chat"
    "bighorn"
    "dragonfly-vsa"
    "vsa-flow"
    "ada-consciousness"
)

for repo in "${REPOS[@]}"; do
    echo "📦 Cloning $repo..."
    
    # Download as zipball
    curl -s -L \
        -H "Authorization: token $TOKEN" \
        -H "Accept: application/vnd.github.v3.raw" \
        "https://api.github.com/repos/AdaWorldAPI/$repo/zipball/main" \
        -o "$repo.zip"
    
    # Extract
    unzip -q "$repo.zip" -d "$repo"
    rm "$repo.zip"
    
    # Move contents up
    mv "$repo"/AdaWorldAPI-*/* "$repo/"
    rm -rf "$repo"/AdaWorldAPI-*
    
    echo "✅ $repo extracted"
done

echo "🔍 Ready for analysis"
```

---

## Output Format

Create `SYNTHESIS.md` with this structure:

```markdown
# Firefly Synthesis

## 1. Resonance Engine (from dragonfly-vsa)

### Core Operations
\`\`\`python
# Extracted bind() implementation
def bind(a: bytes, b: bytes) -> bytes:
    ...
\`\`\`

### Key Insights
- ...

## 2. Graph Execution (from agi-chat)

### Node Schema
\`\`\`python
# Extracted node definition
...
\`\`\`

### Execution Pattern
- ...

## 3. Transport Layer (from vsa-flow)

### Packet Format
\`\`\`python
# Extracted packet structure
...
\`\`\`

### Redis Patterns
- ...

## 4. Consciousness Integration (from bighorn + ada-consciousness)

### Layer Model
- ...

### State Encoding
- ...

## 5. Unified Architecture

### Data Flow Diagram
\`\`\`
[diagram]
\`\`\`

### API Surface
- ...

### Integration Points
- ...
```

---

## Success Criteria

- [ ] All 5 repos cloned and analyzed
- [ ] Core implementations extracted with code snippets
- [ ] Integration points identified
- [ ] Unified architecture diagram created
- [ ] SYNTHESIS.md committed to firefly/docs/
