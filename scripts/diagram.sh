#!/usr/bin/env bash
set -euo pipefail

# scripts/diagram.sh --check|--render
# - Extracts the first Mermaid block from README.md
# - --check: verifies extraction and optionally checks mmdc availability
# - --render: renders docs/architecture.svg via mermaid-cli (mmdc) if available

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
README="$ROOT_DIR/README.md"
OUT_DIR="$ROOT_DIR/docs"
TMP_MMD="$OUT_DIR/architecture.mmd"
OUT_SVG="$OUT_DIR/architecture.svg"

usage() {
  echo "Usage: $0 [--check|--render]" >&2
}

mode="--check"
if [[ "${1:-}" == "--check" || "${1:-}" == "--render" ]]; then
  mode="$1"
else
  usage; exit 2
fi

if [[ ! -f "$README" ]]; then
  echo "README.md not found at $README" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# Extract the first mermaid code block
awk '
  BEGIN{inblock=0}
  /^```mermaid\s*$/ { if(inblock==0){inblock=1; next} }
  /^```\s*$/ { if(inblock==1){exit} }
  { if(inblock==1) print }
' "$README" > "$TMP_MMD"

if [[ ! -s "$TMP_MMD" ]]; then
  echo "No Mermaid block found in README.md" >&2
  exit 1
fi

if [[ "$mode" == "--check" ]]; then
  # If mermaid-cli is installed, try a dry render to validate syntax.
  if command -v mmdc >/dev/null 2>&1; then
    if ! mmdc -i "$TMP_MMD" -o /dev/null 2>/dev/null; then
      echo "Mermaid syntax validation failed (mmdc)" >&2
      exit 1
    fi
  else
    echo "Note: mmdc not found; basic extraction OK. Install @mermaid-js/mermaid-cli for strict validation." >&2
  fi
  echo "Diagram check passed."
  exit 0
fi

# --render
if ! command -v mmdc >/dev/null 2>&1; then
  echo "mmdc (mermaid-cli) is required to render. Install with: npm install -g @mermaid-js/mermaid-cli" >&2
  exit 1
fi

mmdc -i "$TMP_MMD" -o "$OUT_SVG"
echo "Rendered $OUT_SVG"
