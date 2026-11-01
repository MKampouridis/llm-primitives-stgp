#!/bin/bash
# Sets up the Python environment on CERES, once (docs/CERES.md §3). CERES asks for conda
# environments to be built on a compute node, so start an interactive session first:
#   qrsh -q interactive.q
#   cd ~/llm-primitives-stgp && bash scripts/ceres/setup.sh
#
# CERES runs CentOS 7 (glibc 2.17). Recent pip wheels of numpy, numba and pyarrow need a newer
# glibc, so the environment comes from conda-forge (Miniforge in ~/miniforge3, already installed
# for regime-fusion-gp), which still builds for glibc 2.17. Versions may differ from the Mac's
# uv.lock by patch releases; the tests at the end, and the portability check of docs/CERES.md §5,
# show whether results are the same.
set -eo pipefail   # not -u: conda's own activation scripts use variables that may be unset
case "$(hostname)" in
    compute-*) ;;
    *) echo "Please run this on a compute node: start one with 'qrsh -q interactive.q' and run it there." >&2
       exit 1 ;;
esac
unset PYTHONPATH   # CERES sets one for its own Pythons; the environment's Python would load their packages
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PREFIX="$HOME/miniforge3"
ENV=lpstgp

if [ ! -x "$PREFIX/bin/conda" ]; then
    curl -fsSL -o "$HOME/miniforge-installer.sh" \
        https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
    bash "$HOME/miniforge-installer.sh" -b -p "$PREFIX"
    rm -f "$HOME/miniforge-installer.sh"
fi
source "$PREFIX/etc/profile.d/conda.sh"
# (Re)built unless it already has every package, so a set-up cut short can simply be run again.
if ! conda run -n "$ENV" python -c "import numpy, scipy, numba, pandas, pyarrow, deap, pytest, hypothesis, xdist, ot, antropy, pywt, sklearn, statsmodels, ta" 2>/dev/null; then
    conda create -y -n "$ENV" -c conda-forge python=3.12 "numpy>=2.0,<2.6" "scipy>=1.13" \
        "numba>=0.68" "pandas>=2.2" "pyarrow>=17" deap=1.4.4 requests xlrd exchange-calendars \
        pytest pytest-xdist hypothesis pot antropy pywavelets scikit-learn statsmodels ta
fi
conda activate "$ENV"
# Test-only references that conda-forge lacks: pure Python, so pip without dependencies.
pip install --no-deps "ordpy>=1.2.3" "nolds>=0.6.3" "kramersmoyal>=0.4.1"
# roughpy (reference for the rough-path operators' tests) has compiled wheels that may not work
# on glibc 2.17; without it those tests are skipped on CERES (they pass on the Mac and in CI).
pip install "roughpy==0.3.0" || echo "roughpy is not installable here: tests/operators/test_rough_paths.py will be skipped"
pip install --no-deps -e "$REPO"
python - <<'PY'
import numba, numpy, pandas, scipy, lpstgp
print("environment ready:", "numpy", numpy.__version__, "scipy", scipy.__version__,
      "pandas", pandas.__version__, "numba", numba.__version__)
PY
cd "$REPO"
SKIP=()
python -c "import roughpy" 2>/dev/null || SKIP=(--ignore=tests/operators/test_rough_paths.py)
python -m pytest -q -p no:warnings -m "not realdata" -n 4 "${SKIP[@]}"
