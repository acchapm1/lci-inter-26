# Building Multi-Platform Docker Images on Apple Silicon

**Audience:** Sysadmins / technical peers  
**Host:** macOS on Apple Silicon (aarch64 / arm64)  
**Goal:** Build and push images that run on both `linux/amd64` and `linux/arm64`  
**Runtime:** Docker Desktop (standard)

---

## Overview

Apple Silicon Macs are `aarch64` (`arm64`) hosts. Most production infrastructure —
including x86 HPC cluster nodes, legacy CI runners, and many cloud VMs — runs `amd64`.
If you build a plain `docker build` on an M-series Mac, you get a native `arm64` image
that will either silently emulate (slow) or hard-fail on `amd64` hosts.

The solution is **`docker buildx`** + **QEMU** + **BuildKit**, which lets you compile
for multiple target architectures in a single build pass and push a **multi-arch manifest**
to a registry. Consumers then automatically pull the right layer for their hardware.

```
┌─────────────────────────────────────────────────────────────┐
│  MacBook (arm64 host)                                       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Docker Desktop                                       │  │
│  │                                                       │  │
│  │  BuildKit ──► native arm64 builder                    │  │
│  │           └──► QEMU-emulated amd64 builder            │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │ --push                        │
└─────────────────────────────┼───────────────────────────────┘
                              ▼
                    Registry (multi-arch manifest)
                    ├── linux/amd64  ──► amd64 hosts pull this
                    └── linux/arm64  ──► arm64 hosts pull this
```

Docker Desktop bundles QEMU and BuildKit — no manual QEMU setup required on macOS.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop ≥ 4.x | Ships with buildx and QEMU baked in |
| Registry account | Docker Hub, GHCR, or private registry |
| `docker buildx` | Bundled — verify with `docker buildx version` |

---

## Step 1 — Verify Your Environment

```bash
# Confirm buildx is available and the version
docker buildx version

# List existing builders (default driver won't do multi-platform pushes)
docker buildx ls
```

The default builder uses the `docker` driver. This driver **cannot** build multi-platform
images or push a manifest. You need a builder backed by the `docker-container` driver.

---

## Step 2 — Create a Multi-Platform Builder

```bash
# Create a new builder using the docker-container driver
docker buildx create \
  --name multiplatform \
  --driver docker-container \
  --driver-opt network=host \
  --bootstrap \
  --use
```

**Flag breakdown:**

| Flag | Purpose |
|---|---|
| `--name multiplatform` | Friendly name; reuse this builder across projects |
| `--driver docker-container` | Runs BuildKit in a container; required for multi-arch |
| `--driver-opt network=host` | Lets the BuildKit container reach your host network |
| `--bootstrap` | Starts the builder immediately and verifies it works |
| `--use` | Sets this as the active builder for subsequent commands |

Verify the new builder is active and platforms are available:

```bash
docker buildx ls
# Look for: multiplatform  docker-container  ...  linux/amd64, linux/arm64, ...

docker buildx inspect --bootstrap
# Should show linux/amd64 and linux/arm64 in the supported platforms list
```

> **Note:** You only need to create this builder once. On subsequent sessions,
> just run `docker buildx use multiplatform` to re-activate it.

---

## Step 3 — Authenticate to Your Registry

Pick your target registry and authenticate before building.

**Docker Hub:**
```bash
docker login
# Prompts for Docker Hub username and password / access token
```

**GitHub Container Registry (GHCR):**
```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

**Private / self-hosted registry:**
```bash
docker login registry.example.com
```

> **Security tip:** Use access tokens (not passwords) wherever your registry supports them.
> Docker Hub and GHCR both do.

---

## Step 4 — Write a Platform-Aware Dockerfile

For most images, a standard Dockerfile just works. However, if your build has
architecture-specific steps (installing binaries, fetching pre-built artifacts),
use BuildKit's automatic build arguments:

```dockerfile
# syntax=docker/dockerfile:1

# BUILDPLATFORM = platform of the build host (arm64 on your Mac)
# TARGETPLATFORM = platform being compiled for (amd64 or arm64)
ARG BUILDPLATFORM
ARG TARGETPLATFORM

FROM --platform=$BUILDPLATFORM ubuntu:22.04 AS builder

RUN echo "Building on $BUILDPLATFORM, targeting $TARGETPLATFORM"

# Example: fetch the correct binary for the target architecture
ARG TARGETARCH
RUN case "$TARGETARCH" in \
      amd64) ARCH=x86_64 ;; \
      arm64) ARCH=aarch64 ;; \
      *) echo "Unsupported arch: $TARGETARCH" && exit 1 ;; \
    esac && \
    curl -Lo /usr/local/bin/myapp \
      "https://releases.example.com/myapp-${ARCH}" && \
    chmod +x /usr/local/bin/myapp

FROM ubuntu:22.04
COPY --from=builder /usr/local/bin/myapp /usr/local/bin/myapp
ENTRYPOINT ["/usr/local/bin/myapp"]
```

**Key build args injected automatically by BuildKit:**

| Variable | Example value | Notes |
|---|---|---|
| `BUILDPLATFORM` | `linux/arm64` | Host platform |
| `TARGETPLATFORM` | `linux/amd64` | Current build target |
| `TARGETARCH` | `amd64` | Short arch name — useful in shell |
| `TARGETOS` | `linux` | Target OS |

> **`FROM --platform=$BUILDPLATFORM`** on your intermediate build stage keeps heavy
> compilation steps running natively on your Mac's arm64, avoiding slow QEMU emulation
> for the build toolchain itself. Only the final stage is cross-compiled.

---

## Step 5 — Build and Push

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag docker.io/youruser/yourimage:latest \
  --tag docker.io/youruser/yourimage:1.0.0 \
  --push \
  .
```

**Flag breakdown:**

| Flag | Purpose |
|---|---|
| `--platform linux/amd64,linux/arm64` | Build for both targets in one pass |
| `--tag` | Can specify multiple tags; all get the multi-arch manifest |
| `--push` | Push directly to the registry (required for multi-arch manifests) |
| `.` | Build context; change if your Dockerfile is elsewhere |

> **Why can't I use `--load` for multi-platform?**  
> `--load` imports the image into your local Docker daemon, which only supports a
> single architecture. Use `--push` instead. If you need to test locally, build
> for a single platform first: `--platform linux/amd64 --load`.

**Build with cache (speeds up iterative builds):**

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --cache-from type=registry,ref=docker.io/youruser/yourimage:cache \
  --cache-to   type=registry,ref=docker.io/youruser/yourimage:cache,mode=max \
  --tag docker.io/youruser/yourimage:latest \
  --push \
  .
```

`mode=max` caches all intermediate layers, not just the final image — worth it on
slow QEMU-emulated amd64 builds.

---

## Step 6 — Verify the Multi-Arch Manifest

After pushing, confirm both architectures are present in the registry:

```bash
# Human-readable manifest inspection (no pull required)
docker buildx imagetools inspect docker.io/youruser/yourimage:latest
```

Expected output should list both digest entries:

```
Name:      docker.io/youruser/yourimage:latest
MediaType: application/vnd.oci.image.index.v1+json
Digest:    sha256:abc123...

Manifests:
  Name:      docker.io/youruser/yourimage:latest@sha256:def456...
  MediaType: application/vnd.oci.image.manifest.v1+json
  Platform:  linux/amd64

  Name:      docker.io/youruser/yourimage:latest@sha256:789abc...
  MediaType: application/vnd.oci.image.manifest.v1+json
  Platform:  linux/arm64
```

You can also pull a specific platform explicitly to test:

```bash
# Force-pull the amd64 variant (even on your arm64 Mac)
docker pull --platform linux/amd64 docker.io/youruser/yourimage:latest
docker run --rm --platform linux/amd64 docker.io/youruser/yourimage:latest uname -m
# Should output: x86_64
```

---

## Troubleshooting

### Builder fails to start or shows no platforms

```bash
# Remove and recreate the builder
docker buildx rm multiplatform
docker buildx create --name multiplatform --driver docker-container --bootstrap --use
```

### `exec format error` when running the image

The wrong architecture variant was pulled or run. Verify with:

```bash
docker inspect --format '{{.Architecture}}' IMAGE_ID
```

### `--push` fails with auth error

Re-run `docker login [registry]` — credentials may have expired, or the token
lacks `write:packages` scope (GHCR).

### amd64 build is extremely slow

This is expected — QEMU emulates an x86_64 CPU in software. Strategies to reduce pain:

- Use `FROM --platform=$BUILDPLATFORM` for compile-heavy stages (native arm64 build tools)
- Only cross-compile the final artifact; copy it into the target stage
- Use `--cache-from / --cache-to` (registry cache) to avoid rebuilding unchanged layers
- Consider a native amd64 remote builder for large projects (see `docker buildx create --append`)

### Can't push — "multi-platform image push is not supported with the docker driver"

You're still on the default builder. Run:
```bash
docker buildx use multiplatform
```

---

## Quick Reference

```bash
# One-time setup
docker buildx create --name multiplatform --driver docker-container --bootstrap --use

# Re-activate in a new session
docker buildx use multiplatform

# Build and push multi-arch
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag registry/user/image:tag \
  --push .

# Verify manifest
docker buildx imagetools inspect registry/user/image:tag

# Test a specific platform locally
docker run --rm --platform linux/amd64 registry/user/image:tag uname -m

# List builders
docker buildx ls

# Clean up builder
docker buildx rm multiplatform
```

---

## See Also

- [Docker Buildx docs](https://docs.docker.com/buildx/working-with-buildx/)
- [Multi-platform images guide](https://docs.docker.com/build/building/multi-platform/)
- [BuildKit `--platform` ARGs reference](https://docs.docker.com/engine/reference/builder/#automatic-platform-args-in-the-global-scope)
