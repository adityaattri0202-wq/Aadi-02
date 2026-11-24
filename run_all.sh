#!/usr/bin/env bash
# Run every stage in order for one topic, pausing at each paid stage.
#
#   ./run_all.sh livyatan                 # real providers, asks before spending
#   ./run_all.sh livyatan --dry-run       # plan only, no API calls
#   ./run_all.sh livyatan --provider mock # offline end-to-end check
#   ./run_all.sh livyatan --accent uk     # British voice
set -euo pipefail

TOPIC="${1:?usage: ./run_all.sh <topic_slug> [--dry-run] [--provider NAME] [--accent us|uk]}"
shift
EXTRA=("$@")
PY="${PYTHON:-python3}"
DRY=false
for a in "${EXTRA[@]}"; do [[ "$a" == "--dry-run" ]] && DRY=true; done

# Load API keys from .env if present (never committed).
if [[ -f .env ]]; then set -a; source .env; set +a; fi

stage() { "$PY" -m pipeline "$1" --topic "$TOPIC" "${@:2}" "${EXTRA[@]}"; }

stage script_check
stage shot_plan
stage review_report   # shows the cost estimate before anything is spent

for s in image_generate motion_generate voiceover; do
  echo
  echo "=== $s: plan ==="
  stage "$s" --dry-run
  if $DRY; then continue; fi
  read -r -p "Approve $s and spend the estimated credits? Type 'yes' to continue: " answer
  if [[ "$answer" == "yes" ]]; then
    stage "$s" --approve
  else
    echo "Skipped $s (nothing spent). Re-run later with: $PY -m pipeline $s --topic $TOPIC --approve"
  fi
done

stage manifest
stage review_report
echo
echo "Done. See topics/$TOPIC/review_report.md and topics/$TOPIC/manifest.json"
