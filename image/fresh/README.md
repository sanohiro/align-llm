# FRESH-IMAGE profile

This directory builds the installed Ubuntu 24.04 x86_64 trust root for the Section 9 fresh compiler.
It is deliberately independent of the repository worker delivered by FRESH-WORKER.

The image contains the ELF `fresh-supervise`, `fresh-bootstrap`,
`request6-adoption-boundary-entrypoint`, `request6-adoption-entrypoint`, and
`adoption-namespace` entrypoints, their embedded isolated Python control code, the schema-2
toolchain manifest, fixed public verification keys,
the synthetic platform self-test project, and the `fresh-profile` runtime provisioner. Private
signing seeds and the signed image attestation are deployment inputs and must never enter an image
layer or Git.

## Qualification

Run the bounded host-side control checks first:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-attestation-wire-smoke
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run-fresh-image-control-smoke
```

The Request 6 boundary is intentionally a negative, pre-consumer check. Its installed profile
smoke accepts the exact `ordinary-adoption-boundary` vector and verifies that missing or present
consumer workers are rejected before source, Make, or compiler work; it does not claim ordinary
adoption evidence.

The installed ordinary profile owns the authenticated transport for the later consumer worker. It
requires the exact `ordinary-adoption` vector, retains the supervisor-created nonce and channel,
binds the signed capsule and worker as source data, and verifies the image-owned dispatcher,
namespace helper, Python, and `/usr/bin/bwrap` runtime records from their manifest sources. A
checkout worker is not installed by this image slice: an absent or malformed worker is rejected at
the revision boundary. The installed namespace helper validates the authority/proof handoff and
then fails closed until the later worker slice supplies the complete bwrap staging, capability,
tmpfs, and descendant-lifecycle owner. The focused adoption smoke covers the canonical wire and
direct-input contracts without claiming Request 6 adoption evidence.

The installed-profile acceptance needs a Docker daemon with privileged cgroup-v2 access and nested
unprivileged user namespaces. It builds the image with ephemeral, distinct public keys, creates the
external image attestation, provisions the protected runtime and cgroup parents, runs the image-only
self-test without a network, and checks canonical trust rejection:

```text
PYTHONDONTWRITEBYTECODE=1 scripts/run-fresh-image-profile-smoke
```

The profile smoke also checks the exact ordinary dispatcher and namespace bindings, the distinct
`/usr/bin/bwrap` target/source binding, legacy self-test isolation, and ordinary missing-worker,
missing-`ALIGN_REPO`, extra-environment, and retained-dispatcher replacement failures. It also
uses a temporary smoke-only worker to exercise capsule/nonce/proof and retained-FD-27 transport;
that fixture does not install a product worker, run the namespace Make sequence, or claim ordinary
Request 6 evidence.

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
