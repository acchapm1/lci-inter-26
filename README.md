# lci-inter-26 — LCI Intermediate 2026 workshop materials

Teaching materials, labs, and reference guides for the **Linux Clusters
Institute (LCI) Intermediate 2026** workshop. The repository is organized by
topic, each in its own top-level directory: building and signing **containers**,
authoring **environment modules** (Lmod / Tcl), and standing up a **Slurm**
scheduler from source.

Each directory is self-contained and has its own README or guide(s). Start in
the directory for the topic you're working on.

## Layout

```
lci-inter-26/
├── containers/   Apptainer image signing + multi-arch Docker builds
├── modules/      example Lmod/Tcl modulefiles + a build-from-source helper
└── slurm/        one-command Slurm cluster install + hands-on lab
```

## Topics

### `containers/` — container build & signing

Standalone reference guides for HPC sysadmins:

- **`apptainer-key.md`** — generate a PGP key pair, publish it to
  `keys.openpgp.org`, and sign/verify SIF containers with Apptainer. Includes
  key export/import, backup, and keyserver management.
- **`apptainer-key-commands`** — the bare command list from the guide above,
  for quick copy-paste.
- **`docker-multiarch-build.md`** — build and push multi-arch
  (`linux/amd64` + `linux/arm64`) Docker images from an Apple Silicon Mac using
  `buildx` + QEMU + BuildKit.
- **`Apptainer-QuickReference.pdf`** — printable Apptainer cheat sheet.

### `modules/` — environment modulefiles

Example modulefiles that accompany the **Software Modules** session. Most
packages ship as a matched TCL (Environment Modules) and Lua (Lmod) pair so you
can read the same install side-by-side in both syntaxes (`python`, `gcc`,
`cuda`, `cudnn`, `openfoam`, `tensorflow`, and TCL-only `hwloc` / `hpcx`).

- **`letsbuildpython.sh`** — builds Python from source *and* auto-generates its
  `.lua` modulefile (the production "build + modulefile" pattern).
- **`ollama/`** — download helper, start/stop scripts, and versioned modulefiles
  for running Ollama on a cluster (notes target ASU's Sol). See
  `ollama/README.md`.
- **`moshpit/`** — Lmod module wrapping a MOSHPIT (QIIME 2) Apptainer container.

See `modules/README.md` for which example teaches which concept.

### `slurm/` — Slurm cluster install + lab

A self-contained bundle that installs a working Slurm cluster in **one
command** (head-node configuration, then Slurm built from source and deployed to
the compute nodes via Ansible), plus the full hands-on lab.

```bash
# Run as root on the head node:
cd slurm
./install_all.sh 07               # use YOUR cluster number
./install_all.sh --configless 07  # configless variant
```

Key files (full detail in `slurm/README.md`):

- **`install_all.sh`** / **`uninstall_all.sh`** — installer and full teardown.
- **`commands`** — source of truth for the lab: every command, top to bottom.
- **`INSTALL.md`** — what `install_all.sh` actually does.
- **`HANDSONLAB.md`** — the "why" behind each lab section (fairshare, priority,
  accounting limits, preemption).
- **`Storage-options.md`** — where on disk to run the lab depending on which
  shared filesystem (Ceph / BeeGFS / Lustre / Storage Scale) the storage track
  left mounted.
- **`head_node/`** / **`slurm/`** — the two Ansible playbooks the installer runs.

This bundle deliberately does **not** set up shared storage — that's built in a
separate storage lab. See `slurm/Storage-options.md`.

## Requirements

Requirements vary by topic; the Slurm bundle targets Rocky Linux 9.7 on head and
compute nodes with host-based SSH between them. See each directory's own
README/guide for the specifics.
