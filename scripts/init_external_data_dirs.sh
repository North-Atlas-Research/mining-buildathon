#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/ProjectSSD/Data"
  exit 2
fi

DATA_ROOT="$1"

mkdir -p \
  "$DATA_ROOT/Raw" \
  "$DATA_ROOT/Interim" \
  "$DATA_ROOT/Processed" \
  "$DATA_ROOT/Outputs" \
  "$DATA_ROOT/Scratch" \
  "$DATA_ROOT/Cache"

cat <<EOF
Created:
$DATA_ROOT/Raw
$DATA_ROOT/Interim
$DATA_ROOT/Processed
$DATA_ROOT/Outputs
$DATA_ROOT/Scratch
$DATA_ROOT/Cache

Next:
1. Put source datasets only in Raw.
2. Configure PROJECT_DATA_HOST to $DATA_ROOT.
3. Use Docker's :ro mount for Raw.
EOF
