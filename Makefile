ALIGNC ?= ./scripts/alignc
ifeq ($(strip $(ALIGNC)),)
override ALIGNC := ./scripts/alignc
endif
ifneq ($(words $(ALIGNC)),1)
$(error ALIGNC must be one command path without whitespace)
endif
ALIGN_REPO ?= ../align
CARGO ?= cargo
override SHELL := /bin/sh
override .SHELLFLAGS := -eu -c
override PINNED_ALIGNC := $(abspath $(ALIGN_REPO)/target/release/alignc)
ENTRY := src/main.align
GGML_SPIKE_ENTRY := src/ggml_spike.align
EVAL_CORPUS := eval/tasks/smoke-v1.json
CODING_CORPUS := eval/tasks/coding-v1.json

override HOSTED_CHECK_TARGETS := gate-topology-check format-check check build eval-smoke loop-smoke provider-smoke index-smoke test-selection-smoke patch-eval-smoke verify-loop-smoke failure-memory-smoke prompt-model-smoke prompt-render-parity-smoke prompt-score-smoke prompt-score-prefix-smoke prompt-verifier-smoke prompt-seed-attestation-smoke prompt-experiment-smoke prompt-generate-smoke prompt-measurement-adapter-smoke prompt-credential-lifetime-smoke prompt-state-smoke prompt-gate-validator-smoke prompt-gate-source-bundle-smoke prompt-gate-source-revalidation-smoke prompt-gate-git-replacement-graft-smoke prompt-gate-local-git-config-smoke prompt-gate-ordinary-clone-config-smoke prompt-gate-replacement-namespace-smoke prompt-gate-ancestry-smoke prompt-gate-merge-head-ancestry-smoke c6e-request2-adoption persisted-result-smoke gguf-smoke model-ir-smoke expert-trace-smoke residency-sim-smoke alignpack-smoke ggml-spike-smoke layer-forward-smoke
override CAPABLE_ONLY_CHECK_TARGETS := eval-coding baseline-check c6-evaluation-adoption
override SERIAL_CHECK_AGGREGATES := hosted-checks capable-checks ci
override REQUESTED_SERIAL_CHECK_AGGREGATES := \
  $(filter $(SERIAL_CHECK_AGGREGATES),$(MAKECMDGOALS))
ifneq ($(REQUESTED_SERIAL_CHECK_AGGREGATES),)
ifneq ($(words $(MAKECMDGOALS)),1)
$(error verification aggregates must be requested alone)
endif
endif
ifeq ($(MAKECMDGOALS),ci)
$(error fresh compiler: ERROR TRUST supervisor)
endif
ifeq ($(MAKECMDGOALS),capable-checks)
ifneq ($(ALIGN_LLM_FRESH_COMPILER),1)
$(error capable-checks requires the authenticated fresh worker)
endif
endif

.PHONY: check run build fmt format-check ggml-spike ggml-spike-smoke ggml-spike-qualification layer-forward-smoke layer-forward-qualification model-forward-qualification metal-forward-qualification moe-layer-forward-qualification moe-model-forward-qualification decode-step-qualification moe-decode-step-qualification gguf-smoke gguf-reference-parity model-ir-smoke model-ir-parity expert-trace-smoke expert-trace-parity residency-sim-smoke residency-sim-qualification alignpack-smoke alignpack-qualification eval-smoke eval-coding loop-smoke provider-smoke index-smoke test-selection-smoke patch-eval-smoke verify-loop-smoke failure-memory-smoke prompt-model-smoke prompt-render-parity-smoke prompt-score-smoke prompt-score-prefix-smoke prompt-verifier-smoke prompt-seed-attestation-smoke prompt-experiment-smoke prompt-generate-smoke prompt-measurement-adapter-smoke prompt-credential-lifetime-smoke prompt-state-smoke prompt-source-verifier-smoke prompt-snapshot-helper-smoke prompt-fixed-adapter-smoke prompt-evaluate-smoke prompt-gate-validator-smoke prompt-gate-source-bundle-smoke prompt-gate-source-revalidation-smoke prompt-gate-git-replacement-graft-smoke prompt-gate-local-git-config-smoke prompt-gate-ordinary-clone-config-smoke prompt-gate-replacement-namespace-smoke prompt-gate-ancestry-smoke prompt-gate-merge-head-ancestry-smoke prompt-gate-check baseline-check gate-topology-check fresh-worker-qualification hosted-checks capable-checks align-revision align-build align-build-only json-scan-row-ownership-adoption c6-json-decoded-owner-adoption c6-json-escape-adoption c6-json-recursive-graph-adoption c6c2-request8-adoption c6c2-request10-adoption c6-json-bounded-encoding-adoption c6-prompt-artifact-adoption c6b-memory-adoption c6-json-adoption-wave c6-borrowed-option-adoption c6-borrowed-array-adoption c6d-request18-adoption c6e-request2-adoption c6f1-request11-adoption c6f2-request14-adoption c6-evaluation-adoption c7-owned-record-source-expiry-adoption c7-persisted-result-cli-smoke c7-persisted-result-lifetime-smoke c7-persisted-result-owned-move-smoke c7-persisted-result-wire-smoke c7-persisted-result-noncanonical-input-smoke c7-persisted-result-independent-destinations-smoke persisted-result-smoke persisted-result-qualification darwin-profile-gate ci
check:
	@if [ "$${ALIGN_LLM_FRESH_COMPILER:-0}" = 1 ]; then \
	  diagnostic="$$(mktemp)"; \
	  trap 'rm -f "$$diagnostic"' EXIT HUP INT TERM; \
	  if $(ALIGNC) check-per-unit $(ENTRY) 2>"$$diagnostic"; then \
	    exit 0; \
	  fi; \
	  cat "$$diagnostic" >&2; \
	  exit 1; \
	else \
	  $(ALIGNC) check-per-unit $(ENTRY); \
	fi

run:
	$(ALIGNC) run $(ENTRY)

build:
	@if [ "$${ALIGN_LLM_FRESH_COMPILER:-0}" = 1 ]; then \
	  diagnostic="$$(mktemp)"; \
	  trap 'rm -f "$$diagnostic"' EXIT HUP INT TERM; \
	  if $(ALIGNC) build $(ENTRY) 2>"$$diagnostic"; then \
	    exit 0; \
	  fi; \
	  cat "$$diagnostic" >&2; \
	  exit 1; \
	else \
	  $(ALIGNC) build $(ENTRY); \
	fi

fmt:
	@find src -name '*.align' -type f -exec $(ALIGNC) fmt {} --write \;

format-check:
	./scripts/check-format

eval-smoke: build
	./eval/runners/run-fixed.sh $(EVAL_CORPUS)
	./scripts/run-eval-invalid-smoke

eval-coding: build
	./eval/runners/run-fixed.sh $(CODING_CORPUS)
	./scripts/run-coding-task-invalid-smoke
	./scripts/run-coding-task-git-config-smoke
	./scripts/run-coding-task-timeout-smoke

loop-smoke: build
	./scripts/run-loop-smoke

provider-smoke: build
	./scripts/run-http-bounded-adoption-smoke
	./scripts/run-provider-smoke

index-smoke: build
	./scripts/run-index-smoke

test-selection-smoke: build
	./scripts/run-test-selection-smoke

patch-eval-smoke: build
	./scripts/run-patch-eval-smoke

# The docs/specs/r0-gguf-inspection.md section 4.2 narrow durable owner. It generates its own
# synthetic GGUF corpus into a temporary tree, needs no model, no network, and no reference tool,
# and runs in seconds, which is why it joins HOSTED_CHECK_TARGETS.
gguf-smoke: build
	./scripts/run-gguf-smoke

# The section 4.4 focused qualification. It is opt-in through ALIGN_LLM_GGUF_REFERENCE and
# ALIGN_LLM_GGUF_MODEL, prints an explicit N/A line when either is absent, and deliberately stays
# outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
gguf-reference-parity: build
	./scripts/run-gguf-reference-parity

# The docs/specs/r1-qwen-model-ir.md section 4.2 narrow durable owner. It is the hosted owner of a
# new consumer surface (`--model-ir`), generates its own synthetic qwen2 corpus, needs no model, no
# network, and no reference tool, and runs in seconds, which is the same justification that admitted
# gguf-smoke, so it joins HOSTED_CHECK_TARGETS.
model-ir-smoke: build
	./scripts/run-model-ir-smoke

# The section 4.4 focused qualification. It is opt-in through ALIGN_LLM_GGUF_MODEL and
# ALIGN_LLM_LLAMA_CLI, prints an explicit N/A line when either is absent, and deliberately stays
# outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
model-ir-parity: build
	./scripts/run-model-ir-parity

# The docs/specs/r2a-expert-trace.md section 4.2 narrow durable owner. It is the hosted owner of a
# new consumer surface (`--expert-trace`), generates its own synthetic eval-callback corpus, parses
# the checked-in real build-10566 excerpt, needs no model, no network, and no reference tool, and
# runs in seconds, which is the same justification that admitted gguf-smoke and model-ir-smoke, so
# it joins HOSTED_CHECK_TARGETS.
expert-trace-smoke: build
	./scripts/run-expert-trace-smoke

# The section 4.4 focused qualification. It is opt-in through ALIGN_LLM_GGUF_MODEL and
# ALIGN_LLM_LLAMA_EVAL_CALLBACK, prints an explicit N/A line when either is absent, and deliberately
# stays outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
expert-trace-parity: build
	./scripts/run-expert-trace-parity

# The docs/specs/r3-residency-sim.md section 4.2 narrow durable owner. It is the hosted owner of a
# new consumer surface (`--simulate-residency`) and a new exchanged document (`R3_RESIDENCY_SIM`),
# builds its own synthetic olmoe containers and MoE transcripts, compares every integer of the
# document against the independent Python oracle scripts/residency_oracle.py, needs no model, no
# network, no instrument, and no GPU, writes well under a megabyte into a temporary tree, and runs
# in about a second — the same justification that admitted gguf-smoke, model-ir-smoke, and
# expert-trace-smoke, so it joins HOSTED_CHECK_TARGETS.
residency-sim-smoke: build
	./scripts/run-residency-sim-smoke

# The section 4.3 focused qualification, and the run that discharges the R3 roadmap gate on the real
# corpus. It is opt-in through exactly two variables, ALIGN_LLM_LLAMA_EVAL_CALLBACK and
# ALIGN_LLM_GGUF_MODEL: either one unset or naming something absent prints an explicit N/A line and
# exits 0. ALIGN_LLM_LOCALITY_PROMPTS (default eval/prompts/expert-locality-v1.txt),
# ALIGN_LLM_LOCALITY_PROMPT_COUNT (default 40), and ALIGN_LLM_RESIDENCY_BUDGET (default 25% of the
# model's expert byte footprint) all have defaults and are overrides rather than switches; a corpus
# that is named and missing is exit 1, not N/A. The run deletes every captured transcript
# immediately after conversion and deliberately stays outside HOSTED_CHECK_TARGETS,
# CAPABLE_ONLY_CHECK_TARGETS, and every aggregate. Section 3.3 of docs/specs/r3-residency-sim.md
# carries the same table.
residency-sim-qualification: build
	./scripts/run-residency-sim

# The docs/specs/r4-alignpack-layer-major.md section 4.2 narrow durable owner. It is the hosted
# owner of two new consumer surfaces (`--pack`, `--pack-verify`), reuses the existing synthetic qwen2
# and gpt-oss GGUF corpora, needs no model, no network, and no reference tool, and writes well under
# a megabyte into a temporary tree, which is the same justification that admitted gguf-smoke,
# model-ir-smoke, and expert-trace-smoke, so it joins HOSTED_CHECK_TARGETS.
alignpack-smoke: build
	./scripts/run-alignpack-smoke

# The section 4.4 focused qualification. It is opt-in through ALIGN_LLM_GGUF_MODEL, prints an
# explicit N/A line when the model is unset or absent or the free space is insufficient, writes a
# multi-gigabyte pack into a caller-named temporary directory outside the work tree and removes it
# on every exit path, and deliberately stays outside HOSTED_CHECK_TARGETS,
# CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
alignpack-qualification: build
	./scripts/run-alignpack-qualification

# docs/specs/r4-5-external-buffer.md section 3.2. A **separate** executable, deliberately: a
# `link(...)` clause is compile-time and unconditional and Align has no conditional compilation, so
# a ggml dependency anywhere in `src/main.align`'s import graph would put `-lggml` on every link of
# `main` on every host. `src/ggml_spike.align` is its own entry, `src/ggml_ffi.align` names exactly
# one library — the repository's own shim — and `make build` is untouched.
#
# `scripts/build-ggml-shim` selects the real shim when `ALIGN_LLM_GGML_INCLUDE` is set and the
# ggml-free stub otherwise, writes it under `build/`, which is `.gitignore`d, and prints the
# directory. The executable is renamed from the compiler's source-stem output to the CLI name the
# design and both runners use.
ggml-spike:
	@shim_dir="$$(./scripts/build-ggml-shim)"; \
	  LIBRARY_PATH="$$shim_dir$${LIBRARY_PATH:+:$$LIBRARY_PATH}" \
	  DYLD_LIBRARY_PATH="$$shim_dir$${DYLD_LIBRARY_PATH:+:$$DYLD_LIBRARY_PATH}" \
	  LD_LIBRARY_PATH="$$shim_dir$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}" \
	  $(ALIGNC) build $(GGML_SPIKE_ENTRY)
	@mv -f ggml_spike ggml-spike

# The section 5.1 narrow durable owner. It builds the **stub** shim and the spike, generates its own
# synthetic alignpack corpus into a temporary tree, needs no model, no network, no ggml, and no
# reference tool, and runs in seconds — the same justification that admitted gguf-smoke,
# model-ir-smoke, expert-trace-smoke, and alignpack-smoke — so it joins HOSTED_CHECK_TARGETS. It
# runs the whole CLI over every fixture and reaches eleven of the sixteen error codes for real.
#
# It depends on `build` since MOE-PREREQ-DISCHARGE: the claim cells of
# `docs/specs/moe-prereq-discharge.md` section 4.6 are taken from the synthetic olmoe container
# packed by `main --pack`, exactly as `alignpack-smoke` already does, rather than from a hand-forged
# container that could disagree with the writer about where a plane lives.
ggml-spike-smoke: build
	./scripts/run-ggml-spike-smoke

# The section 5.2 focused qualification. It is opt-in through ALIGN_LLM_GGML_INCLUDE,
# ALIGN_LLM_GGML_LIB, and ALIGN_LLM_GGUF_MODEL, prints an explicit N/A line when any is absent or
# the free space is insufficient, writes a multi-gigabyte pack into a temporary directory outside
# the work tree and removes it on every exit path, and deliberately stays outside
# HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
ggml-spike-qualification: build
	./scripts/run-ggml-spike

# The docs/specs/r5a-dense-layer-forward.md section 5.1 narrow durable owner. It builds the **stub**
# shim and the spike, generates its own synthetic tiny-geometry alignpack corpus, geometry document,
# and eval-callback transcript into a temporary tree, needs no model, no network, no ggml, and no
# reference tool, and runs in seconds — the same justification that admitted gguf-smoke,
# model-ir-smoke, expert-trace-smoke, alignpack-smoke, and ggml-spike-smoke — so it joins
# HOSTED_CHECK_TARGETS. It runs the whole `--layer-forward` CLI over every fixture and reaches
# twenty-four of the twenty-six error codes **and both oracle verdicts** for real.
#
# Adding it to HOSTED_CHECK_TARGETS changes aggregate membership, so CLAUDE.md's verification rules
# select `make ci` for this capability's publication — not because a pin moved, but because the
# check topology did.
layer-forward-smoke:
	./scripts/run-layer-forward-smoke

# The section 5.2 focused qualification. It is opt-in through ALIGN_LLM_GGML_INCLUDE,
# ALIGN_LLM_GGML_LIB, ALIGN_LLM_GGUF_MODEL, and ALIGN_LLM_LLAMA_EVAL_CALLBACK, prints an explicit
# N/A line when any is absent or the free space is insufficient, writes a multi-gigabyte pack into a
# temporary directory outside the work tree and removes it on every exit path, and deliberately
# stays outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
layer-forward-qualification: build
	./scripts/run-layer-forward

# The docs/specs/r5b-model-prefill-forward.md section 5.2 focused qualification. It is opt-in
# through ALIGN_LLM_GGML_INCLUDE, ALIGN_LLM_GGML_LIB, ALIGN_LLM_GGUF_MODEL,
# ALIGN_LLM_LLAMA_EVAL_CALLBACK, and ALIGN_LLM_LLAMA_DEBUG, prints an explicit N/A line when any is
# absent or the free space is insufficient, writes a multi-gigabyte pack and both instrument
# outputs into a temporary directory outside the work tree and removes them on every exit path, and
# deliberately stays outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
#
# The R5B owner is `layer-forward-smoke`, which section 5.1 extends rather than replaces:
# `layer-forward-smoke` is already a member of HOSTED_CHECK_TARGETS, so this capability changes no
# aggregate membership and no check topology.
model-forward-qualification: build
	./scripts/run-model-forward

# The docs/specs/r5c-metal-prefill.md section 5.2 focused qualification: R5's required
# microbenchmark A, transfer plus GPU compute, on unified memory. It is opt-in through
# ALIGN_LLM_GGML_INCLUDE, ALIGN_LLM_GGML_LIB, ALIGN_LLM_GGML_BACKEND_DIR, ALIGN_LLM_GGUF_MODEL,
# ALIGN_LLM_LLAMA_DEBUG, and ALIGN_LLM_LLAMA_EVAL_CALLBACK, prints an explicit N/A line when any is
# absent, when the free space is insufficient, or when **the registry reports no device of type
# GPU**, writes a multi-gigabyte pack and both instrument outputs into a temporary directory outside
# the work tree and removes them on every exit path, and deliberately stays outside
# HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
#
# Hosted CI is Linux with no Metal device, so this target is N/A there by its device check. That is
# the intended behaviour and not a skip: the N/A line names the device as the missing input, and the
# arm's own failure surface — all three R5C_* codes — is fully stub-reachable in
# `layer-forward-smoke`, which is where R5C's owner lives.
#
# The R5C owner is `layer-forward-smoke`, which section 5.1 extends rather than replaces:
# `layer-forward-smoke` is already a member of HOSTED_CHECK_TARGETS, so this capability changes no
# aggregate membership and no check topology.
metal-forward-qualification: build
	./scripts/run-metal-forward

# The docs/specs/r5d-moe-layer-forward.md section 5.2 focused qualification: one **routed** OLMoE
# layer, computed by ggml over attention weights and only the routed experts' planes held in
# Align-owned buffers, against llama.cpp's own numbers for the same six tokens. It is opt-in
# through ALIGN_LLM_GGML_INCLUDE, ALIGN_LLM_GGML_LIB, ALIGN_LLM_GGUF_MODEL, and
# ALIGN_LLM_LLAMA_EVAL_CALLBACK, prints an explicit N/A line when any is absent, when the model is
# not an olmoe container, or when the free space is insufficient, writes a multi-gigabyte pack into
# a temporary directory outside the work tree and removes it on every exit path, and deliberately
# stays outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
#
# The R5D owner is `layer-forward-smoke`, which section 5.1 extends rather than replaces:
# `layer-forward-smoke` is already a member of HOSTED_CHECK_TARGETS, so this capability changes no
# aggregate membership and no check topology.
moe-layer-forward-qualification: build
	./scripts/run-moe-layer-forward

# The docs/specs/r5e-moe-model-prefill.md section 5.2 focused qualification: a whole OLMoE prefill
# through sixteen routed layers and the head, against **both** llama.cpp instruments, with all four
# oracles. It is opt-in through ALIGN_LLM_GGML_INCLUDE, ALIGN_LLM_GGML_LIB, ALIGN_LLM_GGUF_MODEL,
# ALIGN_LLM_LLAMA_EVAL_CALLBACK, and ALIGN_LLM_LLAMA_DEBUG, prints an explicit N/A line when any is
# absent or the free space is insufficient, writes a multi-gigabyte pack into a temporary directory
# outside the work tree and removes it on every exit path, and deliberately stays outside
# HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
#
# The R5E owner is `layer-forward-smoke`, which section 5.1 extends rather than replaces:
# `layer-forward-smoke` is already a member of HOSTED_CHECK_TARGETS, so this capability changes no
# aggregate membership and no check topology.
moe-model-forward-qualification: build
	./scripts/run-moe-model-forward

# The docs/specs/r6-olmoe-decode.md section 6.2 focused qualification: `N` greedy decode steps on
# the **routed** OLMoE-1B-7B over an Align-owned KV plane, gated on routing identity against
# llama.cpp at every step and on the token ids llama.cpp itself produces. It is opt-in through
# ALIGN_LLM_GGML_INCLUDE, ALIGN_LLM_GGML_LIB, ALIGN_LLM_GGUF_MODEL, ALIGN_LLM_LLAMA_EVAL_CALLBACK,
# and ALIGN_LLM_LLAMA_DEBUG, prints an explicit N/A line when any is absent, when `numpy` cannot be
# imported, or when the free space is insufficient, writes a multi-gigabyte pack and both instrument
# outputs into a temporary directory outside the work tree and removes them on every exit path, and
# deliberately stays outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and every aggregate.
#
# **A target is added where R6-STEP-N, R6-KV-PERSIST and R6-RESIDENT-WEIGHTS added none**, and the
# difference is the arm: those three extended `--decode-step` and its existing runner, so
# `decode-step-qualification` already named their work. This capability ships a **new arm** with a
# **new runner**, exactly as `--moe-layer-forward` and `--moe-model-forward` did, and each of those
# got its own target. Without one, `gmake moe-decode-step-qualification` in the documentation would
# name nothing.
#
# The R6-OLMOE-DECODE owner is `layer-forward-smoke`, which section 6.1 extends with a **seventh**
# block rather than replacing: `layer-forward-smoke` is already a member of HOSTED_CHECK_TARGETS, so
# this capability changes no aggregate membership and no check topology, and
# `scripts/check-gate-topology`'s byte-literal EXPECTED does not move.
moe-decode-step-qualification: build
	./scripts/run-moe-decode-step

# The docs/specs/r6-decode-kv-step1.md section 5 focused qualification: one decode step at
# `n_past = T` over an Align-owned KV plane, on the dense Qwen2.5-Coder-7B, against llama.cpp's own
# decode graph. It is opt-in through ALIGN_LLM_GGML_INCLUDE, ALIGN_LLM_GGML_LIB,
# ALIGN_LLM_GGUF_MODEL, ALIGN_LLM_LLAMA_EVAL_CALLBACK, and ALIGN_LLM_LLAMA_DEBUG, prints an explicit
# N/A line when any is absent or the free space is insufficient, writes a multi-gigabyte pack and
# both instrument outputs into a temporary directory outside the work tree and removes them on every
# exit path, and deliberately stays outside HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and
# every aggregate.
#
# The R6 owner is `layer-forward-smoke`, which section 5 extends rather than replaces:
# `layer-forward-smoke` is already a member of HOSTED_CHECK_TARGETS, so this capability changes no
# aggregate membership and no check topology, and `scripts/check-gate-topology`'s byte-literal
# EXPECTED does not move.
decode-step-qualification: build
	./scripts/run-decode-step

verify-loop-smoke: build
	./scripts/run-verification-loop-smoke

failure-memory-smoke: verify-loop-smoke

prompt-model-smoke:
	./scripts/run-prompt-model-smoke

prompt-render-parity-smoke:
	./scripts/run-prompt-render-parity-smoke

prompt-score-smoke:
	./scripts/run-prompt-score-smoke

prompt-score-prefix-smoke:
	./scripts/run-prompt-score-prefix-smoke

prompt-verifier-smoke:
	./scripts/run-prompt-verifier-smoke

prompt-seed-attestation-smoke:
	./scripts/run-prompt-seed-attestation-smoke

prompt-experiment-smoke: build
	./scripts/run-prompt-experiment-smoke

prompt-generate-smoke: build
	./scripts/run-prompt-generate-smoke

prompt-measurement-adapter-smoke:
	./scripts/run-prompt-measurement-adapter-smoke

prompt-credential-lifetime-smoke: build
	./scripts/run-prompt-credential-lifetime-smoke

prompt-state-smoke: build
	./scripts/run-prompt-state-smoke

prompt-source-verifier-smoke:
	./scripts/test-prompt-source-verifier

prompt-snapshot-helper-smoke:
	./scripts/test-prompt-snapshot-helper

prompt-fixed-adapter-smoke:
	./scripts/test-prompt-fixed-adapter

prompt-evaluate-smoke:
	./scripts/run-prompt-evaluate-smoke

prompt-gate-validator-smoke:
	./scripts/run-prompt-gate-validator-smoke validator

prompt-gate-source-bundle-smoke:
	./scripts/run-prompt-gate-validator-smoke source-bundle

prompt-gate-source-revalidation-smoke:
	./scripts/run-prompt-gate-validator-smoke source-revalidation

prompt-gate-git-replacement-graft-smoke:
	./scripts/run-prompt-gate-validator-smoke git-replacement-graft

prompt-gate-local-git-config-smoke:
	./scripts/run-prompt-gate-validator-smoke local-git-config

prompt-gate-ordinary-clone-config-smoke:
	./scripts/run-prompt-gate-validator-smoke ordinary-clone-config

prompt-gate-replacement-namespace-smoke:
	./scripts/run-prompt-gate-validator-smoke replacement-namespace

prompt-gate-ancestry-smoke:
	./scripts/run-prompt-gate-validator-smoke ancestry

prompt-gate-merge-head-ancestry-smoke:
	./scripts/run-prompt-gate-validator-smoke merge-head-ancestry

# The C6-MEASURED capable gate. Every input is an explicit command-line value; there is no
# environment, ambient-interpreter, or sibling-checkout fallback, and a missing or empty value
# fails before the validator starts. The declared interpreter is also the launcher, so the target
# never invokes an ambient Python or Git to reach the validator.
prompt-gate-check:
	@if [ -z "$(C6_GATE_SOURCE_BUNDLE_ROOT)" ] \
	  || [ -z "$(C6_GATE_PYTHON_EXECUTABLE_PATH)" ] \
	  || [ -z "$(C6_GATE_GIT_EXECUTABLE_PATH)" ] \
	  || [ -z "$(C6_GATE_GENERATION_CHILD_PATH)" ] \
	  || [ -z "$(C6_GATE_GENERATION_CHILD_SHA256)" ]; then \
	  echo 'prompt gate: ERROR explicit C6_GATE_* input' >&2; \
	  exit 1; \
	fi; \
	"$(C6_GATE_PYTHON_EXECUTABLE_PATH)" ./scripts/prompt-gate-validator.py \
	  --source-bundle-root "$(C6_GATE_SOURCE_BUNDLE_ROOT)" \
	  --python-executable-path "$(C6_GATE_PYTHON_EXECUTABLE_PATH)" \
	  --git-executable-path "$(C6_GATE_GIT_EXECUTABLE_PATH)" \
	  --generation-child-path "$(C6_GATE_GENERATION_CHILD_PATH)" \
	  --generation-child-sha256 "$(C6_GATE_GENERATION_CHILD_SHA256)"

c6d-request18-adoption: build
	ALIGN_C6D_REQUEST18_ADOPTION=1 ./scripts/run-prompt-state-smoke

c6e-request2-adoption:
	./scripts/run-http-timeout-adoption-smoke

c6f1-request11-adoption:
	./scripts/run-c6f1-request11-adoption

c6f2-request14-adoption:
	./scripts/run-c6f2-request14-adoption

c6-evaluation-adoption:
	+MAKEFLAGS= GNUMAKEFLAGS= $(MAKE) --no-print-directory -j1 \
	  c6f1-request11-adoption c6f2-request14-adoption \
	  prompt-source-verifier-smoke prompt-snapshot-helper-smoke \
	  prompt-fixed-adapter-smoke prompt-evaluate-smoke

baseline-check:
	python3 ./eval/runners/verify-baseline.py
	./scripts/run-baseline-invalid-smoke
	./scripts/run-baseline-failure-smoke
	python3 ./scripts/check-baseline-chain

gate-topology-check: override export ALIGN_LLM_HOSTED_CHECK_TARGETS := $(HOSTED_CHECK_TARGETS)
gate-topology-check: override export ALIGN_LLM_CAPABLE_ONLY_CHECK_TARGETS := $(CAPABLE_ONLY_CHECK_TARGETS)
gate-topology-check: override export ALIGN_LLM_SERIAL_CHECK_AGGREGATES := $(SERIAL_CHECK_AGGREGATES)
gate-topology-check:
	@python3 ./scripts/check-gate-topology

fresh-worker-qualification:
	@python3 ./scripts/run-fresh-worker-qualification

hosted-checks: gate-topology-check
	+MAKEFLAGS= GNUMAKEFLAGS= $(MAKE) --no-print-directory -j1 \
	  $(filter-out gate-topology-check,$(HOSTED_CHECK_TARGETS))

capable-checks: gate-topology-check
	+MAKEFLAGS= GNUMAKEFLAGS= $(MAKE) --no-print-directory -j1 \
	  $(filter-out gate-topology-check,$(HOSTED_CHECK_TARGETS)) \
	  $(CAPABLE_ONLY_CHECK_TARGETS)

align-revision:
	@if [ "$${ALIGN_LLM_FRESH_COMPILER:-}" = 1 ]; then \
	  /tools/bash /private-project/scripts/check-align-revision >/dev/null 2>&1; \
	else \
	  ./scripts/check-align-revision >/dev/null 2>&1; \
	fi

align-build: align-revision
	@$(CARGO) build --manifest-path $(ALIGN_REPO)/Cargo.toml --locked --release \
		-p align_runtime -p align_driver >/dev/null 2>&1

align-build-only:
	@$(CARGO) build --manifest-path $(ALIGN_REPO)/Cargo.toml --locked --release \
		-p align_runtime -p align_driver >/dev/null 2>&1

json-scan-row-ownership-adoption:
	@/tools/python3 /private-project/scripts/run-json-scan-row-ownership-adoption-smoke

c6-json-decoded-owner-adoption:
	./scripts/run-c6-json-decoded-owner-adoption

c6-json-escape-adoption:
	./scripts/run-c6-json-escape-adoption

c6-json-recursive-graph-adoption:
	./scripts/run-c6-json-recursive-graph-adoption

c6c2-request8-adoption:
	./scripts/run-c6c2-request8-adoption

c6c2-request10-adoption:
	./scripts/run-c6c2-request10-adoption

c6-json-bounded-encoding-adoption:
	./scripts/run-c6-json-bounded-encoding-adoption

c6-prompt-artifact-adoption:
	./scripts/run-c6-prompt-artifact-adoption

c6b-memory-adoption:
	+MAKEFLAGS= GNUMAKEFLAGS= $(MAKE) --no-print-directory -j1 \
	  prompt-model-smoke c6-prompt-artifact-adoption

c6-json-adoption-wave:
	+MAKEFLAGS= GNUMAKEFLAGS= $(MAKE) --no-print-directory -j1 \
	  c6-json-decoded-owner-adoption c6-json-escape-adoption \
	  c6-json-recursive-graph-adoption \
	  c6c2-request8-adoption c6c2-request10-adoption \
	  c6-json-bounded-encoding-adoption c6-prompt-artifact-adoption

c6-borrowed-option-adoption: c6-borrowed-array-adoption

c6-borrowed-array-adoption:
	./scripts/run-c6-borrowed-array-adoption

c7-owned-record-source-expiry-adoption:
	./scripts/run-c7-owned-record-source-expiry-adoption

# C7-PERSISTED-RESULT bounded functional smokes. Each one remains its own focused target; the
# bounded functional owner admitted to the hosted list by the docs/specs/c7-persisted-result.md
# section 12 measured decision is `persisted-result-smoke`, which drives all six.
c7-persisted-result-cli-smoke: build
	./scripts/run-c7-persisted-result-cli-smoke

c7-persisted-result-lifetime-smoke:
	./scripts/run-c7-persisted-result-lifetime-smoke

c7-persisted-result-owned-move-smoke:
	./scripts/run-c7-persisted-result-owned-move-smoke

c7-persisted-result-wire-smoke:
	./scripts/run-c7-persisted-result-wire-smoke

c7-persisted-result-noncanonical-input-smoke:
	./scripts/run-c7-persisted-result-noncanonical-input-smoke

c7-persisted-result-independent-destinations-smoke:
	./scripts/run-c7-persisted-result-independent-destinations-smoke

# docs/specs/c7-persisted-result.md section 9.4 acceptance-runner process boundary. Both C7 runners
# resolve the selected compiler and the product executable here, at the repository root, before any
# child changes its working directory. The selection order is the repository order: the
# authenticated fresh compiler when required, an explicit `ALIGNC`, an explicit `ALIGN_REPO`
# release/debug compiler, then the managed `.align-revision` release compiler. There is no implicit
# sibling or `PATH` fallback, and the `scripts/alignc` selector wrapper is never passed to a child.
define c7_resolve_and_run
@if [ "$${ALIGN_LLM_FRESH_COMPILER:-0}" = 1 ]; then \
  if [ "$${ALIGNC:-}" != "/tools/fresh-alignc" ]; then \
    printf '%s\n' "$(1): the fresh profile requires the authenticated launcher" >&2; \
    exit 1; \
  fi; \
  compiler=/tools/fresh-alignc; \
else \
  if [ -n "$${ALIGNC:-}" ]; then \
    selected="$${ALIGNC}"; \
  elif [ -n "$${ALIGN_REPO:-}" ]; then \
    if [ -x "$${ALIGN_REPO}/target/release/alignc" ]; then \
      selected="$${ALIGN_REPO}/target/release/alignc"; \
    elif [ -x "$${ALIGN_REPO}/target/debug/alignc" ]; then \
      selected="$${ALIGN_REPO}/target/debug/alignc"; \
    else \
      printf '%s\n' "$(1): alignc was not found in explicit ALIGN_REPO=$${ALIGN_REPO}" >&2; \
      exit 127; \
    fi; \
  else \
    selected="$$(./scripts/align-toolchain ensure compiler)"; \
  fi; \
  compiler="$$(realpath -e "$$selected" 2>/dev/null || realpath "$$selected")"; \
  if [ "$$compiler" = "$(CURDIR)/scripts/alignc" ]; then \
    printf '%s\n' "$(1): the scripts/alignc selector wrapper is not a child compiler" >&2; \
    exit 1; \
  fi; \
  case "$$compiler" in /*) ;; *) \
    printf '%s\n' "$(1): the selected compiler is not an absolute path" >&2; exit 1;; esac; \
  if [ ! -f "$$compiler" ] || [ ! -x "$$compiler" ]; then \
    printf '%s\n' "$(1): the selected compiler is not a regular executable" >&2; exit 1; \
  fi; \
fi; \
product="$$(realpath -e "$(CURDIR)/main" 2>/dev/null || realpath "$(CURDIR)/main")"; \
if [ ! -f "$$product" ] || [ ! -x "$$product" ]; then \
  printf '%s\n' "$(1): the product executable is not a regular executable" >&2; exit 1; \
fi; \
./scripts/$(1) "$$compiler" "$$product"
endef

# The docs/specs/c7-persisted-result.md section 12 bounded functional owner. Its measured cost
# admitted it to HOSTED_CHECK_TARGETS; the six member smokes remain individually invocable.
persisted-result-smoke: build
	$(call c7_resolve_and_run,run-persisted-result-smoke)

# The section 12 focused qualification. It owns the independent reference, the seeded differential
# corpus, the malformed/mutation corpus, and the temporary source mutation, and it deliberately
# stays outside every routine hosted/capable aggregate.
persisted-result-qualification: build
	$(call c7_resolve_and_run,run-persisted-result-qualification)

# The docs/specs/check-gate-topology.md section 10 `aarch64-apple-darwin` platform-profile gate. It
# is a named focused qualification run at a pin bump, a C7 owner-boundary change, or an explicit
# audit, so it is deliberately absent from HOSTED_CHECK_TARGETS, CAPABLE_ONLY_CHECK_TARGETS, and
# every aggregate. The script takes no Make variable: its inputs are the environment it validates.
darwin-profile-gate:
	@python3 ./scripts/check-darwin-profile

ci:
	@exit 1
