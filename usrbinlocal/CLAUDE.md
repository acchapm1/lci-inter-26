# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A flat copy of `/usr/local/bin` from ASU Research Computing's Sol supercomputer (Slurm-based HPC cluster). It is not a software project: there is no build system, no test suite, no linter config, and it is not a git repository. Each file is a standalone executable — mostly Bash, a few POSIX sh and Python scripts, and several large prebuilt binaries.

Most scripts cannot be meaningfully executed outside the cluster — they depend on Slurm commands (`salloc`, `srun`, `squeue`, `scontrol`, `sinfo`, `sacct`), cluster paths (`/packages/...`, `/warewulf/config`, `/etc/slurm/slurm.conf`), and node hardware (`nvidia-smi`, `dcgmi`, `ipmitool`). Validate shell changes with `bash -n <script>` and Python changes with `python3 -m py_compile <script>`.

## File categories

- **Interactive session launchers** — a family of `salloc`/`srun`/`sbatch` wrappers: `interactive` (current default, plain `salloc`), `__interactive` (salloc + temp script that waits for the job then `srun --pty bash -l`), `aux-interactive` (`--no-shell` salloc + ssh), `classic-interactive`/`_interactive`/`_interactive_screen` (legacy screen-based, supports Singularity via `$SIF`/`$SIMG`), `gh_interactive` (Grace Hopper nodes), `vscode` (VS Code tunnel via srun), `mkjupy` (register a conda env as a Jupyter kernel).
- **Slurm info formatters** — `myjobs`, `alljobs`, `sq`, `summary`, `showparts`, `showgpus`, `showjob`, `showlimited`, `myaccounts`, `myfairshare`, `mysacct`, `thisjob`, `pestat`, `ns` (Python node-status table), `stest` (Python sbatch script validator that parses `slurm.conf`).
- **Slurm node hooks** — `_prolog`/`_epilog` (production) and `_dev_prolog`/`_dev_epilog` (dev, adds `dcgmi stats`). They maintain GPU→job mappings in `/var/run/dcgm_job_maps` for dcgm_exporter; `_epilog` also records job details to `~/.local/var/log/slurm/slurm_record_$SLURM_JOBID` (skipped when `SLURM_SKIP_EPILOG=1`).
- **Admin/node diagnostics** — `thisnode`, `_config_mig` (NVIDIA MIG setup), `find_completing_jobs`/`clear_completing_jobs`, `get-slurmstepd-processes`, `get-beegfs-stats`, `get-user-disk-stats`, `get-fairshare-report`, `usage_compare`, `minutes_in_use`.
- **Python 3.6 shims** — `pip`, `pip3`, `pip3.6`, `f2py*`, `websockify` are standard entry-point shims pinned to `/usr/bin/python3.6`.
- **Misc user utilities** — `rewind` (restore files from `.snapshot` dirs), `getline`, `join_arr`, `dtn` (ssh to data-transfer node), `rofs`, `remove_conda_from_bashrc`.

Naming convention: a leading underscore means the script is invoked by Slurm or another script (prolog/epilog, helper stages), not directly by users.

## Code conventions

- Wrapper scripts collect options in a `readonly opts=(...)` bash array with defaults first, then append `$@` so user arguments override defaults, and pass `"${opts[@]}"` to the underlying Slurm command. Follow this pattern when changing defaults (partition `-p`, QOS `-q`, time `-t`, etc.).
- Many scripts define an inner function documented with a `: << __HELPSTRING` heredoc, then call it with `"$@"` at the bottom (`sq`, `summary`, `vscode`, `showparts`).
- Output formatting is done with long `squeue/scontrol | awk | tr | column` pipelines; column merging/renaming logic lives in the awk program (see `myjobs` and `alljobs`, which are near-duplicates differing mainly by `--me` and the UserName column — keep them in sync).
- Scripts are intentionally self-contained: helpers like `join_arr` are duplicated inline rather than sourced, since these deploy as independent files in `/usr/local/bin`.
- Attribution is by a `# Blame:`/`# BLAME` comment with an `@asu.edu` email at the top of each script.
- Cluster specifics baked into scripts: partitions `htc`, `general`, `lightwork`; QOS `public`; software under `/packages/apps/...` and `/packages/envs/scicomp/...`.
