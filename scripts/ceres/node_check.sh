#!/bin/bash
# Submits the node check (D-054) to up to two all.q nodes of each core count, from the login node:
#   cd ~/llm-primitives-stgp && mkdir -p logs && bash scripts/ceres/node_check.sh
# Results: ~/lpstgp-data/results/node_check2/<host>.json, one per node.
set -eo pipefail
declare -A seen
for instance in $(qselect -q all.q); do
    host="${instance#*@}"
    ncpu=$(qhost -h "$host" | awk 'NR > 3 && $3 ~ /^[0-9]+$/ {print $3; exit}')
    [ -n "$ncpu" ] || continue
    if [ "${seen[$ncpu]:-0}" -lt 2 ]; then
        seen[$ncpu]=$(( ${seen[$ncpu]:-0} + 1 ))
        echo "node $host ($ncpu cores):"
        qsub -l h="$host" scripts/ceres/node_check.sge
    fi
done
