# FRESH-IMAGE profile

This directory builds the installed Ubuntu 24.04 x86_64 trust root for the Section 9 fresh compiler.
It is deliberately independent of the repository worker delivered by FRESH-WORKER.

The image contains the ELF `fresh-supervise` and `fresh-bootstrap` entrypoints, their embedded
isolated Python control code, the schema-2 toolchain manifest, fixed public verification keys,
the synthetic platform self-test project, and the `fresh-profile` runtime provisioner. Private
signing seeds and the signed image attestation are deployment inputs and must never enter an image
layer or Git.

## Qualification

Run the bounded host-side control checks first:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-attestation-wire-smoke
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke
```

The installed-profile acceptance needs a Docker daemon with privileged cgroup-v2 access. It builds
the image with ephemeral, distinct public keys, creates the external image attestation, provisions
the protected runtime and cgroup parents, runs the image-only self-test without a network, and
checks canonical trust rejection:

```text
PYTHONDONTWRITEBYTECODE=1 scripts/run-fresh-image-profile-smoke
```

Production deployment follows the same ownership boundary: build with public-key hex arguments,
produce `image-attestation.dsse` using `scripts/fresh-image-attest` and an offline image seed, mount
the four fixed files under `/run/align-llm-fresh` read-only, and mount the same persistent
`/run/user` profile into the provisioner and worker containers. Run `fresh-profile setup <uid>`
before invoking the image and `fresh-profile cleanup <uid>` afterward. The exact file modes and
ownership are normative in Section 9.1 of `docs/specs/check-gate-topology.md`.
