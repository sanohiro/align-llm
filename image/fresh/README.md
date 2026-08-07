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

The installed-profile acceptance needs a Docker daemon with privileged cgroup-v2 access and nested
unprivileged user namespaces. It builds the image with ephemeral, distinct public keys, creates the
external image attestation, provisions the protected runtime and cgroup parents, runs the image-only
self-test without a network, and checks canonical trust rejection:

```text
PYTHONDONTWRITEBYTECODE=1 scripts/run-fresh-image-profile-smoke
```

The profile smoke also verifies the two fixed ordinary-adoption runtime bindings, rejects direct
dispatcher execution, and invokes `fresh-supervise --mode ordinary-adoption` against a checkout that
does not yet contain the consumer worker. That path must return exactly
`json-scan adoption: ERROR revision\n` before any Make or compiler marker. The consumer worker and
its full namespace/build acceptance remain a later adoption slice.

The hosted Ubuntu 24.04 qualification temporarily disables that runner's AppArmor restriction on
unprivileged user namespaces, verifies a nested namespace can be created, and restores the original
setting after the profile. A deployment must provide equivalent nested-user-namespace capability;
the image does not weaken the host policy itself.

Production deployment follows the same ownership boundary: build with public-key hex arguments,
produce `image-attestation.dsse` using `scripts/fresh-image-attest` and an offline image seed, mount
the four fixed files under `/run/align-llm-fresh` read-only, and mount the same persistent
`/run/user` profile into the provisioner and worker containers. The invocation runs as that uid and
must start inside the delegated `/sys/fs/cgroup/align-llm-fresh/<uid>` subtree; for Docker's cgroupfs
driver the matching parent is `--cgroup-parent=/align-llm-fresh/<uid>`. Run
`fresh-profile setup <uid>` before invoking the image and `fresh-profile cleanup <uid>` afterward.
The immutable attestation and digest files remain root-owned while only `run-signing-seed` is owned
by the invoking uid. The exact file modes and ownership are normative in Section 9.1 of
`docs/specs/check-gate-topology.md`.
