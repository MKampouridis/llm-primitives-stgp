# Running campaigns on CERES

CERES is the University of Essex cluster: Rocks 7 (CentOS 7, glibc 2.17), with jobs managed by Sun Grid Engine (Open Grid Scheduler). Jobs are submitted with `qsub`, and job arrays number their elements with `SGE_TASK_ID`, from 1. It is reached with `ssh <user>@ceres.essex.ac.uk` from campus or the university VPN, with multi-factor authentication. The home folder is shared by every node. The cluster's guide is [hpc.essex.ac.uk](https://hpc.essex.ac.uk).

This set-up follows regime-fusion-gp's, which has run on CERES since 29 October 2026 (D-046).

**How it works:**
- A campaign is a plan, `results/campaigns/<name>/tasks.json`, listing numbered tasks: one GP run each.
- The plan is written on the Mac. Each element of a job array runs one slice of its tasks.
- Tasks can be repeated safely: a finished run is skipped, so a failed or stopped element is just submitted again.
- Records come back to the Mac, where the reports are written and committed.

## 1. The cluster's rules

Checked on 29 October 2026 for regime-fusion-gp:
- **Queues.** `all.q` is for batch work and job arrays, with one slot per core. `interactive.q` is for interactive sessions (`qrsh`).
- **Limits.** A user may have 260 jobs, and a job array counts as one. An array must limit how many of its elements run at once with `-tc`: at most 60 per array, and about 250 across all of a user's arrays. regime-fusion-gp's campaign already uses some of these.
- **No run-time or memory limit** on `all.q`. Its jobs may be suspended while the higher-priority queue is busy, and resume by themselves.
- **Scripts** must say they use bash (`-S /bin/bash`). Our tasks use one core each.
- **Python.** The system's Pythons are too old. CERES recommends conda environments, built on a compute node in an interactive session, not on the login node.
- **Speed.** Measured for regime-fusion-gp, CERES's cores matched or beat the busy Mac. On 1 November 2026 one calibration-size run took 64 s (arm 2c) or 36 s (arm 6) alone on the Mac (`scripts/time_wp2.py`).

## 2. The code

The repository is public (D-045), so CERES clones it directly. On the login node:

```bash
git clone https://github.com/MKampouridis/llm-primitives-stgp.git ~/llm-primitives-stgp
cd ~/llm-primitives-stgp && git pull        # later, to bring in changes
```

## 3. The environment

```bash
screen                                       # optional: keeps the session alive if the connection drops
qrsh -q interactive.q                        # an interactive session on a compute node
cd ~/llm-primitives-stgp && bash scripts/ceres/setup.sh
exit                                         # back to the login node
```

What the script does:
- Uses the Miniforge already in `~/miniforge3`.
- Creates the conda environment `lpstgp` from conda-forge.
- Installs the package and runs the tests (`-m "not realdata"`).

**Versions.** conda-forge still builds for glibc 2.17, but its versions may differ from `uv.lock` by patch releases. `exchange-calendars` is older (4.8), but only the data steps use it, and they run on the Mac.

**roughpy.** It is only a test reference. If it does not install, `tests/operators/test_rough_paths.py` is skipped on CERES; those tests pass on the Mac and in CI.

If the set-up is cut short, run it again: it redoes only what is missing.

## 4. The data

Runs read Tier A, 74 MB. Copy it from the Mac once the data are final; each `rsync` asks for the password and the second factor:

```bash
ssh <user>@ceres.essex.ac.uk mkdir -p lpstgp-data/data lpstgp-data/results/campaigns
rsync -av ~/code/llm-primitives-stgp/data/tierA <user>@ceres.essex.ac.uk:lpstgp-data/data/
```

The job script points `LPSTGP_PATHS` at `config/paths.ceres.toml`, so data and results live in `~/lpstgp-data`.

**Check the data on CERES.** Every task checks the plan's data digest, so a plan written on the Mac refuses to run on different data.

## 5. Portability check, before the first campaign

The same task must give the same rules on CERES as on the Mac. Before the first campaign:
1. Plan the calibration on the Mac and copy the plan up (§6).
2. Run elements 1–2 on CERES.
3. Run the same two tasks on the Mac: `uv run python scripts/campaign_tasks.py run --campaign wp2-calibration --index 0 --count 2`.
4. Compare the records' `hall_of_fame`. They must be identical.

If they differ, the environment's versions differ in a way that matters. Record it in `docs/decisions.md` and run the pilot on one machine only.

## 6. A campaign

**On the Mac:**

```bash
uv run python scripts/wp2_pilot.py calibrate --mode plan       # writes results/campaigns/wp2-calibration/tasks.json
rsync -av results/campaigns/wp2-calibration <user>@ceres.essex.ac.uk:lpstgp-data/results/campaigns/
```

**On the CERES login node.** `qsub` does not work inside a `qrsh` session, so leave it with `exit` first:

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate lpstgp
unset PYTHONPATH && export LPSTGP_PATHS=~/llm-primitives-stgp/config/paths.ceres.toml
cd ~/llm-primitives-stgp && git pull && mkdir -p logs
python scripts/campaign_tasks.py status --campaign wp2-calibration     # task count and the qsub line
qsub -t 1-2 -tc 2 -v CAMPAIGN=wp2-calibration scripts/ceres/tasks.sge  # test elements
qstat -u $USER                                                         # queued (qw) or running (r)
cat logs/lpstgp.o*                                                     # no Traceback? how long?
qsub -t 3-720 -tc 60 -v CAMPAIGN=wp2-calibration scripts/ceres/tasks.sge
```

**Back on the Mac:**

```bash
rsync -av <user>@ceres.essex.ac.uk:lpstgp-data/results/campaigns/wp2-calibration results/campaigns/
uv run python scripts/wp2_pilot.py calibrate --mode report     # the choice and reports/wp2/calibration.md
```

The budget check (`budget-check`) and the go/no-go (`gonogo`, two plans: `wp2-gonogo-PL1` and `wp2-gonogo-PL2`) work the same way.

**The steps that stay on the Mac:**
- `freeze` writes the manifest, which is committed.
- `pilot-test` is the one-time read of the test years. It needs no cluster, and the committed manifest guards it.

**When something goes wrong:**
- **State `Eqw`:** the element failed to start. `qstat -j <job>` says why, and `qmod -c <job>` clears it once fixed.
- **Stopping elements:** `qdel <job>` stops a whole array; `qdel <job> -t 5-9` stops some of its elements.
- **Short tasks:** `COUNT=K` in `-v` makes each element do K tasks. `campaign_tasks.py status --count K` prints the matching `-t` range.
- **`PlanMismatchError`:** the data, settings or a library lock on CERES differ from the Mac's. Pull the code, or copy the data again.
