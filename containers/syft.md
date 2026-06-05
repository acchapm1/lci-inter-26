# Generating a Software Bill of Materials (SBOM) from Apptainer Containers with Syft

This guide covers installing [Syft](https://github.com/anchore/syft) (by Anchore) without
admin rights on an HPC/shared cluster, and using it to produce a Software Bill of
Materials (SBOM) from Apptainer/Singularity containers — both built `.sif` image files and
unpacked `--sandbox` directories.

It is written for a **rootless HPC environment**: no `sudo`, module systems, scratch
directories, and Apptainer rather than Docker.

> **Naming note:** Apptainer is the renamed/community fork of Singularity. The commands are
> interchangeable — substitute `singularity` for `apptainer` if that is what your cluster
> provides. The Syft workflow is identical either way.

---

## Table of Contents

1. [What Syft Does (and Its Limits)](#1-what-syft-does-and-its-limits)
2. [Installing Syft Without Root](#2-installing-syft-without-root)
   - [Option A: Official install script (curl)](#option-a-official-install-script-curl)
   - [Option B: Download a release tarball directly](#option-b-download-a-release-tarball-directly)
   - [Verify the install](#verify-the-install)
3. [Scanning Apptainer Images](#3-scanning-apptainer-images)
   - [Scanning a SIF file](#scanning-a-sif-file)
   - [Scanning a sandbox directory](#scanning-a-sandbox-directory)
   - [Which approach should I use?](#which-approach-should-i-use)
4. [Output Formats](#4-output-formats)
   - [SPDX](#spdx)
   - [CycloneDX](#cyclonedx)
   - [Syft native JSON and table](#syft-native-json-and-table)
   - [Emitting multiple formats at once](#emitting-multiple-formats-at-once)
5. [CI / Automation](#5-ci--automation)
   - [Batch-scanning a directory of SIF files](#batch-scanning-a-directory-of-sif-files)
   - [Slurm batch job example](#slurm-batch-job-example)
   - [GitHub Actions example](#github-actions-example)
6. [Configuration File (Optional)](#6-configuration-file-optional)
7. [Troubleshooting](#7-troubleshooting)
8. [Quick Reference](#8-quick-reference)

---

## 1. What Syft Does (and Its Limits)

Syft inspects a container filesystem and **catalogs installed software**: OS packages
(apt/yum/apk/rpm), language packages (Python/pip, Conda, npm, Go modules, Java/Maven,
Rust, Ruby, etc.), and binaries. It produces an SBOM — a manifest of "what is inside this
image" — in standard, machine-readable formats.

Syft does **not** scan for vulnerabilities; that is [Grype](https://github.com/anchore/grype)'s
job, which consumes a Syft SBOM. This guide focuses on SBOM generation.

**Key point for Apptainer:** Syft has no native SIF reader. The reliable, format-agnostic
approach on a cluster is to point Syft at the container's **root filesystem** — either by
converting the `.sif` to a sandbox directory, or by scanning an existing sandbox. Both are
covered below and both work fully rootless.

---

## 2. Installing Syft Without Root

Pick **one** of the two options. Both install a single static binary into a user-writable
directory already on your `PATH` (we use `~/.local/bin`). No admin rights required.

First, make sure the target directory exists and is on your `PATH`:

```bash
mkdir -p ~/.local/bin

# Add to PATH for this session and persist it (skip the export if already present)
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH"
     echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc ;;
esac
```

### Option A: Official install script (curl)

The Anchore install script auto-detects your OS/arch and drops the binary wherever you
tell it with `-b`. This is the simplest method on most clusters.

```bash
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
  | sh -s -- -b ~/.local/bin
```

Pin a specific version (recommended for reproducibility) by appending the tag:

```bash
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
  | sh -s -- -b ~/.local/bin v1.45.0
```

> If your cluster login nodes block outbound HTTPS to GitHub, download on a machine that
> has access and `scp` the binary/tarball over, or use Option B from an interactive node
> that does have egress.

### Option B: Download a release tarball directly

Useful when you want to vendor a specific, checksum-verified binary (air-gapped transfers,
provenance records, or sites that forbid `curl | sh`).

```bash
# --- choose version and architecture ---
SYFT_VERSION=1.45.0          # without the leading 'v'
ARCH=linux_amd64             # or linux_arm64 on ARM clusters

cd "$(mktemp -d)"

base="https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}"

# Download the tarball + checksums
curl -sSfLO "${base}/syft_${SYFT_VERSION}_${ARCH}.tar.gz"
curl -sSfLO "${base}/syft_${SYFT_VERSION}_checksums.txt"

# Verify the checksum (fails loudly if the file is corrupt/tampered)
grep "syft_${SYFT_VERSION}_${ARCH}.tar.gz" syft_${SYFT_VERSION}_checksums.txt \
  | sha256sum -c -

# Extract and install just the binary into a PATH dir
tar -xzf "syft_${SYFT_VERSION}_${ARCH}.tar.gz" syft
install -m 0755 syft ~/.local/bin/syft
```

Asset names follow the pattern `syft_<version>_<os>_<arch>.tar.gz`. Browse all releases at
<https://github.com/anchore/syft/releases>.

> **Optional — verify the signature.** Releases are signed with
> [cosign](https://github.com/sigstore/cosign). If cosign is available you can verify
> `syft_<version>_checksums.txt` against `.sig` and `.pem` before trusting the checksums.
> The `sha256sum -c` step above is sufficient for most needs.

### Verify the install

```bash
syft version
```

You should see the version, build date, and Go version. If `command not found`, your shell
hasn't picked up `~/.local/bin` yet — open a new shell or re-source `~/.bashrc`.

---

## 3. Scanning Apptainer Images

Syft reads a container's root filesystem. With Apptainer the cleanest path is to expose
that filesystem as a **sandbox directory**, then point Syft at the directory.

Load Apptainer first if your cluster uses environment modules:

```bash
module load apptainer    # or: module load singularity
```

### Scanning a SIF file

Convert the immutable `.sif` to a writable sandbox directory, then scan the directory. This
works rootless and does not require root-only mounts.

```bash
IMAGE=myimage.sif
SANDBOX="$(mktemp -d)/rootfs"

# Unpack the SIF into a sandbox dir (rootless; uses user namespaces)
apptainer build --sandbox "$SANDBOX" "$IMAGE"

# Catalog the sandbox's filesystem
syft scan "dir:$SANDBOX" -o table

# Clean up when done
rm -rf "$(dirname "$SANDBOX")"
```

The explicit `dir:` scheme tells Syft to treat the path as a directory tree to walk. (Plain
`syft scan "$SANDBOX"` also works, but being explicit avoids ambiguity in scripts.)

> **Where to put the sandbox:** on HPC, build sandboxes in fast node-local scratch
> (e.g. `$TMPDIR`, `/tmp`, `/scratch/$USER`) — **not** on a shared parallel filesystem like
> Lustre/GPFS. Sandboxes contain tens of thousands of small files; scratch is far faster and
> avoids hammering the shared FS. `mktemp -d` honors `$TMPDIR` automatically.

> **Disk usage:** a sandbox is a fully expanded copy of the image. Ensure scratch has room
> for the uncompressed image size, and always `rm -rf` the sandbox afterward.

### Scanning a sandbox directory

If you already have a sandbox (e.g. one you built with `--sandbox` for interactive
development), scan it directly — no conversion needed:

```bash
syft scan dir:/scratch/$USER/myimage-sandbox -o table
```

### Which approach should I use?

| You have...                          | Do this                                                            |
|--------------------------------------|--------------------------------------------------------------------|
| A built `.sif` file                  | `apptainer build --sandbox` → scan the sandbox dir                 |
| An existing `--sandbox` directory    | Scan the directory directly with `dir:<path>`                      |
| The upstream Docker/OCI image        | `syft scan docker:repo/image:tag` *(before* converting to SIF)*    |

> **Alternative — scan the OCI source instead of the SIF.** If your `.def` file is
> `Bootstrap: docker` from a registry, you can SBOM the **source** image directly without
> building anything: `syft scan registry:docker.io/library/ubuntu:22.04`. This captures what
> went *in*, but not anything added by your `%post` section — scan the sandbox if you need
> the as-built contents.

---

## 4. Output Formats

Use `-o <format>` to choose a format, and `-o <format>=<file>` to write straight to a file.

### SPDX

[SPDX](https://spdx.dev/) is a Linux Foundation / ISO-standard SBOM format, common for
compliance and license tracking.

```bash
# SPDX in JSON (recommended; widely supported)
syft scan dir:"$SANDBOX" -o spdx-json=myimage.spdx.json

# SPDX tag-value (classic text form)
syft scan dir:"$SANDBOX" -o spdx-tag-value=myimage.spdx
```

### CycloneDX

[CycloneDX](https://cyclonedx.org/) is an OWASP standard, popular for security tooling and
supply-chain workflows.

```bash
# CycloneDX in JSON (recommended)
syft scan dir:"$SANDBOX" -o cyclonedx-json=myimage.cdx.json

# CycloneDX in XML
syft scan dir:"$SANDBOX" -o cyclonedx-xml=myimage.cdx.xml
```

### Syft native JSON and table

The `table` format is for humans (quick eyeball of what's inside). `syft-json` is Syft's own
richest format and the best input for Grype.

```bash
# Human-readable table to the terminal
syft scan dir:"$SANDBOX" -o table

# Syft native JSON to a file
syft scan dir:"$SANDBOX" -o syft-json=myimage.syft.json
```

### Emitting multiple formats at once

Stack multiple `-o` flags to write every format you need from a single scan — the
efficient choice, since the filesystem is only walked once:

```bash
syft scan dir:"$SANDBOX" \
  -o table \
  -o spdx-json=myimage.spdx.json \
  -o cyclonedx-json=myimage.cdx.json \
  -o syft-json=myimage.syft.json
```

List every supported format with:

```bash
syft scan -o '?'
```

---

## 5. CI / Automation

For scripting, drive verbosity with the `SYFT_QUIET` env var or `-q`, and rely on Syft's
non-zero exit code to fail a job on error.

### Batch-scanning a directory of SIF files

Generate SPDX + CycloneDX SBOMs for every `.sif` in a directory, writing outputs alongside a
results folder. Sandboxes are built in node-local scratch and cleaned up per image.

```bash
#!/usr/bin/env bash
set -euo pipefail

module load apptainer 2>/dev/null || true

IMAGE_DIR="${1:-.}"           # dir containing .sif files
OUT_DIR="${2:-./sboms}"       # where SBOMs are written
mkdir -p "$OUT_DIR"

shopt -s nullglob
for sif in "$IMAGE_DIR"/*.sif; do
  name="$(basename "${sif%.sif}")"
  sandbox="$(mktemp -d "${TMPDIR:-/tmp}/${name}.XXXXXX")/rootfs"

  echo ">> Building sandbox for $name"
  apptainer build --sandbox "$sandbox" "$sif"

  echo ">> Generating SBOMs for $name"
  syft scan "dir:$sandbox" \
    -o spdx-json="$OUT_DIR/${name}.spdx.json" \
    -o cyclonedx-json="$OUT_DIR/${name}.cdx.json" \
    -o syft-json="$OUT_DIR/${name}.syft.json"

  rm -rf "$(dirname "$sandbox")"
  echo ">> Done: $name"
done

echo "All SBOMs written to $OUT_DIR"
```

Run it:

```bash
./generate-sboms.sh /path/to/images ./sboms
```

### Slurm batch job example

Wrap the above for a scheduler. Request node-local scratch and clean up on exit.

```bash
#!/usr/bin/env bash
#SBATCH --job-name=syft-sbom
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=syft-sbom-%j.log

set -euo pipefail
module load apptainer

export PATH="$HOME/.local/bin:$PATH"   # so 'syft' is found
export TMPDIR="${SLURM_TMPDIR:-/scratch/$USER/$SLURM_JOB_ID}"
mkdir -p "$TMPDIR"

SIF=/path/to/myimage.sif
OUT_DIR=/scratch/$USER/sboms
mkdir -p "$OUT_DIR"

sandbox="$(mktemp -d)/rootfs"
trap 'rm -rf "$(dirname "$sandbox")"' EXIT   # always clean up

apptainer build --sandbox "$sandbox" "$SIF"

syft scan "dir:$sandbox" \
  -o spdx-json="$OUT_DIR/myimage.spdx.json" \
  -o cyclonedx-json="$OUT_DIR/myimage.cdx.json"

echo "SBOMs written to $OUT_DIR"
```

Submit with `sbatch syft-sbom.sbatch`.

### GitHub Actions example

If images are built in CI, the official action attaches an SBOM with no manual install.
(Most useful for the OCI/Docker stage of a pipeline that later converts to SIF.)

```yaml
- name: Generate SBOM with Syft
  uses: anchore/sbom-action@v0
  with:
    image: myregistry/myimage:latest
    format: spdx-json
    output-file: myimage.spdx.json
```

Or call the binary directly after installing it (mirrors the cluster workflow):

```yaml
- name: Install Syft
  run: curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b "$HOME/.local/bin" v1.45.0

- name: SBOM
  run: |
    export PATH="$HOME/.local/bin:$PATH"
    syft scan dir:./rootfs -o cyclonedx-json=sbom.cdx.json
```

---

## 6. Configuration File (Optional)

Repeated flags can live in a config file so every invocation is consistent. Syft looks for
`.syft.yaml` in the working directory, or `~/.syft.yaml`, among other locations.

```yaml
# ~/.syft.yaml
output:
  - "spdx-json"
  - "cyclonedx-json"
  - "table"

# Catalog packages from the image's declared OS only (faster on huge images),
# or leave default to scan everything found on disk.
# scope: "squashed"
```

With this in place, `syft scan dir:"$SANDBOX"` emits all three formats automatically.

---

## 7. Troubleshooting

| Symptom                                              | Cause / Fix                                                                                                    |
|------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| `syft: command not found`                            | `~/.local/bin` not on `PATH`. Re-source `~/.bashrc` or open a new shell.                                        |
| `apptainer build --sandbox` fails / permission error | User namespaces may be restricted on login nodes. Try an interactive compute node, or ask admins about rootless/setuid Apptainer config. |
| Scan is very slow / FS overloaded                    | Sandbox is on a shared parallel FS. Rebuild it in node-local scratch (`$TMPDIR`, `/scratch/$USER`).            |
| "No packages discovered" / sparse SBOM               | You scanned the `.sif` directly instead of an unpacked dir. Convert to `--sandbox` first, then scan `dir:`.    |
| Out of space during `--sandbox` build                | A sandbox is the fully decompressed image. Point `$TMPDIR` at a volume with enough free space.                 |
| Need to scan the *source* image, not as-built        | Use `syft scan registry:<repo>/<image>:<tag>` to catalog the upstream OCI image directly.                      |
| Login node blocks GitHub egress                      | Download the tarball elsewhere and `scp` it in (see [Option B](#option-b-download-a-release-tarball-directly)). |

---

## 8. Quick Reference

```bash
# Install (curl, pinned version)
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
  | sh -s -- -b ~/.local/bin v1.45.0

# Load Apptainer
module load apptainer

# SIF -> sandbox -> SBOM (SPDX + CycloneDX + table)
SANDBOX="$(mktemp -d)/rootfs"
apptainer build --sandbox "$SANDBOX" myimage.sif
syft scan "dir:$SANDBOX" \
  -o table \
  -o spdx-json=myimage.spdx.json \
  -o cyclonedx-json=myimage.cdx.json
rm -rf "$(dirname "$SANDBOX")"

# Scan an existing sandbox directory
syft scan dir:/scratch/$USER/myimage-sandbox -o syft-json=myimage.syft.json

# Scan the upstream OCI image directly (no build needed)
syft scan registry:docker.io/library/ubuntu:22.04 -o table

# List all output formats
syft scan -o '?'
```

---

*References: [Syft repo & docs](https://github.com/anchore/syft) ·
[Syft releases](https://github.com/anchore/syft/releases) ·
[Apptainer docs](https://apptainer.org/docs/) ·
[SPDX](https://spdx.dev/) · [CycloneDX](https://cyclonedx.org/). Examples pinned to Syft
v1.45.0; bump the version as new releases land.*
