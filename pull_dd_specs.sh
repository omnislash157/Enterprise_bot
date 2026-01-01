#!/bin/bash

# Mirror Analytics - Integration Spec Extractor
# Pulls key files from DataDog integrations-core for skill building

set -e

WORK_DIR="$HOME/mirror_analytics_specs"
REPO_URL="https://github.com/DataDog/integrations-core.git"

# Top 10 integrations to extract
INTEGRATIONS=(
    "postgres"
    "mysql"
    "redisdb"
    "mongo"
    "nginx"
    "docker"
    "kubernetes"
    "kubernetes_state_core"
    "apache"
    "rabbitmq"
)

echo "=========================================="
echo "  MIRROR ANALYTICS - Spec Extractor"
echo "=========================================="

# Create work directory
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Sparse clone - only what we need
echo "[1/4] Cloning DataDog integrations-core (sparse)..."
if [ -d "integrations-core" ]; then
    echo "  Repo exists, pulling latest..."
    cd integrations-core && git pull && cd ..
else
    git clone --depth 1 --filter=blob:none --sparse "$REPO_URL"
    cd integrations-core
    
    # Set up sparse checkout for our targets
    git sparse-checkout init --cone
    git sparse-checkout set ${INTEGRATIONS[@]}
    cd ..
fi

# Create organized output structure
echo "[2/4] Extracting specs..."
OUTPUT_DIR="$WORK_DIR/skills_input"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

for INT in "${INTEGRATIONS[@]}"; do
    echo "  Processing: $INT"
    INT_DIR="$OUTPUT_DIR/$INT"
    mkdir -p "$INT_DIR"
    
    SRC="$WORK_DIR/integrations-core/$INT"
    
    # Copy key files if they exist
    [ -f "$SRC/metadata.csv" ] && cp "$SRC/metadata.csv" "$INT_DIR/"
    [ -f "$SRC/README.md" ] && cp "$SRC/README.md" "$INT_DIR/"
    [ -f "$SRC/manifest.json" ] && cp "$SRC/manifest.json" "$INT_DIR/"
    
    # Config example (nested path)
    CONF_PATH="$SRC/datadog_checks/$INT/data/conf.yaml.example"
    [ -f "$CONF_PATH" ] && cp "$CONF_PATH" "$INT_DIR/"
    
    # Some have different naming
    ALT_CONF="$SRC/datadog_checks/${INT}/data/conf.yaml.example"
    [ -f "$ALT_CONF" ] && cp "$ALT_CONF" "$INT_DIR/" 2>/dev/null || true
    
    # Service checks
    [ -f "$SRC/assets/service_checks.json" ] && cp "$SRC/assets/service_checks.json" "$INT_DIR/"
done

# Create the SKILL.md index (table of contents for lazy loading)
echo "[3/4] Building SKILL.md index..."

cat > "$OUTPUT_DIR/SKILL.md" << 'EOF'
# Mirror Analytics - Integration Specs

## Purpose
This skill contains extracted specs from DataDog integrations-core (BSD-3-Clause).
Use for building OTel-compatible integrations for Mirror Analytics.

## Structure
Each subfolder contains specs for one integration:
- `metadata.csv` - Complete metric list with names, types, units, descriptions
- `conf.yaml.example` - Full configuration schema with all options
- `README.md` - Setup docs, prerequisites, data sources
- `service_checks.json` - Health check definitions
- `manifest.json` - Integration metadata

## Integrations Included

| Integration | Folder | Priority |
|-------------|--------|----------|
| PostgreSQL | `postgres/` | CRITICAL |
| MySQL | `mysql/` | CRITICAL |
| Redis | `redisdb/` | HIGH |
| MongoDB | `mongo/` | HIGH |
| Nginx | `nginx/` | HIGH |
| Docker | `docker/` | HIGH |
| Kubernetes | `kubernetes/` | CRITICAL |
| Kubernetes State | `kubernetes_state_core/` | CRITICAL |
| Apache | `apache/` | MEDIUM |
| RabbitMQ | `rabbitmq/` | MEDIUM |

## Usage Pattern

When building a skill for integration X:
1. Read `X/metadata.csv` for complete metric definitions
2. Read `X/conf.yaml.example` for config schema
3. Reference `X/README.md` for data source details
4. Build OTel receiver config that maps to these metrics

## Output Format

For each integration, produce:
```
integration_name/
├── SKILL.md           # How to use this integration skill
├── otel_config.yaml   # OTel collector receiver config
├── metrics_map.yaml   # DD metric name → OTel semantic name
├── actions.yaml       # Available remediation actions
└── prompts/
    └── analysis.md    # LLM prompt for anomaly analysis
```

## License
Source: DataDog/integrations-core (BSD-3-Clause)
Derivative work for Mirror Analytics
EOF

# Create summary of what we got
echo "[4/4] Generating manifest..."

cat > "$OUTPUT_DIR/MANIFEST.txt" << EOF
Mirror Analytics Spec Extraction
Generated: $(date)
Source: github.com/DataDog/integrations-core

Files extracted:
EOF

find "$OUTPUT_DIR" -type f -name "*.csv" -o -name "*.yaml" -o -name "*.json" -o -name "*.md" | sort >> "$OUTPUT_DIR/MANIFEST.txt"

echo ""
echo "=========================================="
echo "  COMPLETE"
echo "=========================================="
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "Files ready for skill building:"
ls -la "$OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "1. Start new Claude session"
echo "2. Upload the $OUTPUT_DIR folder or zip it"
echo "3. Say: 'Build integration skills from these specs'"
echo ""

# Optional: create zip for easy upload
cd "$WORK_DIR"
zip -r skills_input.zip skills_input/
echo "ZIP created: $WORK_DIR/skills_input.zip"