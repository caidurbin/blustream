#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <host>" >&2
  exit 1
fi

host="$1"
cd "$(dirname "$0")"

python main.py --host "$host" --json status | jq -r '
  .routing
  | group_by(.output)[]
  | (.[0].output) as $out
  | if (map(.from_input) | unique | length) == 1
    then "Out\($out) <- \(if .[0].from_input then "In\(.[0].from_input)" else "—" end)"
    else "Out\($out) " + (map("\(.channel)<-\(if .from_input then "In\(.from_input)" else "—" end)") | join(" "))
    end
'
