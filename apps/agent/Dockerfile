# yaaos WorkspaceAgent — customer-deployed Go binary.
#
# Two-stage build: golang:1.22-alpine compiles the static binary; the
# runtime stage is `gcr.io/distroless/static-debian12:nonroot` so the
# image has no shell, no package manager, no setuid root binaries.
#
# Image is ~25 MB. The agent is the only PID 1 in the container; SIGTERM
# from ECS reaches it directly so graceful shutdown works without an
# init wrapper.
#
# Build:
#   docker build -f apps/agent/Dockerfile -t yaaos-agent:dev apps/agent
#
# Run (local against the backend in docker-compose):
#   docker run --rm \
#     -e YAAOS_BACKEND_URL=http://host.docker.internal:8080 \
#     -e YAAOS_AGENT_VERSION=dev \
#     -e YAAOS_SIGNED_STS_REQUEST=placeholder \
#     yaaos-agent:dev supervisor

# ── Stage 1: build ─────────────────────────────────────────────────────
FROM golang:1.22-alpine AS builder

# Build deps that only the compile step needs.
RUN apk add --no-cache git ca-certificates

WORKDIR /src

# Cache module downloads in a dedicated layer.
COPY go.mod ./
# When go.sum exists, copy it too — the agent currently has no external
# Go deps so the file may be absent; the COPY is conditional via the
# wildcard pattern.
COPY go.su[m] ./
RUN if [ -f go.sum ]; then go mod download; fi

# Source.
COPY cmd cmd
COPY internal internal

# Static binary. CGO_ENABLED=0 + the distroless runtime means glibc /
# musl differences don't bite. -trimpath removes local build paths from
# the binary so customers don't see /home/<runner>/... in stack traces.
RUN CGO_ENABLED=0 GOOS=linux go build \
    -trimpath \
    -ldflags '-s -w' \
    -o /out/agent \
    ./cmd/agent

# ── Stage 2: runtime ───────────────────────────────────────────────────
FROM gcr.io/distroless/static-debian12:nonroot

# Distroless's `nonroot` user is UID 65532 — the agent runs without
# privileges. ECS task definitions should NOT override this user.
WORKDIR /

# Copy CA bundle so HTTPS to the control plane works out of the box.
# (Distroless images already include this, but the COPY makes the dep
# explicit and survives a future base swap.)
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# The binary itself.
COPY --from=builder /out/agent /usr/local/bin/agent

# The agent expects to find the working directory the supervisor uses
# to clone workspaces — defaults to /var/agent/workspaces (real path
# wires alongside the workspace subcommand body in the Phase 6 follow-on).
# Distroless can't create dirs at runtime — the ECS task definition
# mounts a tmpfs / EBS volume at this path.

ENTRYPOINT ["/usr/local/bin/agent"]
CMD ["supervisor"]
