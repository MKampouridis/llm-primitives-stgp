"""Gate 4, across processes: every operator gives bitwise-identical output in a fresh interpreter
with a different BLAS thread count and hash seed."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

from lpstgp.gates import checks
from lpstgp.gates.synthetic import make_input
from lpstgp.operators.registry import discover

SCRIPT = r"""
import hashlib, json, sys
from lpstgp.gates import checks
from lpstgp.gates.synthetic import make_input
from lpstgp.operators.registry import discover

def inputs_for(spec):
    counts, values = {}, []
    for t in spec.inputs:
        v = counts.get(t, 0); counts[t] = v + 1
        values.append(make_input(t, 900, 7, v))
    return values

out = {}
for key, spec in sorted(discover().operators.items()):
    params = checks.sample_params(spec, 7)[-1]
    result = checks.run(spec, inputs_for(spec), params)
    out[key] = hashlib.sha256(result.tobytes()).hexdigest()
json.dump(out, sys.stdout)
"""


def local_hashes() -> dict[str, str]:
    hashes = {}
    for key, spec in sorted(discover().operators.items()):
        counts, values = {}, []
        for t in spec.inputs:
            v = counts.get(t, 0)
            counts[t] = v + 1
            values.append(make_input(t, 900, 7, v))
        params = checks.sample_params(spec, 7)[-1]
        hashes[key] = hashlib.sha256(checks.run(spec, values, params).tobytes()).hexdigest()
    return hashes


def test_outputs_identical_in_a_fresh_process():
    env = dict(os.environ, OPENBLAS_NUM_THREADS="4", OMP_NUM_THREADS="4", PYTHONHASHSEED="12345")
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT], capture_output=True, text=True, env=env, check=True
    )
    remote = json.loads(result.stdout)
    assert remote == local_hashes()
