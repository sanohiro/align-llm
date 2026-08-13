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
EVAL_CORPUS := eval/tasks/smoke-v1.json
CODING_CORPUS := eval/tasks/coding-v1.json

override HOSTED_CHECK_TARGETS := gate-topology-check format-check check build eval-smoke loop-smoke provider-smoke index-smoke test-selection-smoke patch-eval-smoke verify-loop-smoke failure-memory-smoke prompt-model-smoke prompt-score-smoke prompt-score-prefix-smoke
override CAPABLE_ONLY_CHECK_TARGETS := eval-coding baseline-check
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

.PHONY: check run build fmt format-check eval-smoke eval-coding loop-smoke provider-smoke index-smoke test-selection-smoke patch-eval-smoke verify-loop-smoke failure-memory-smoke prompt-model-smoke prompt-score-smoke prompt-score-prefix-smoke baseline-check gate-topology-check fresh-worker-qualification hosted-checks capable-checks align-revision align-build align-build-only json-scan-row-ownership-adoption ci

check:
	$(ALIGNC) check-per-unit $(ENTRY)

run:
	$(ALIGNC) run $(ENTRY)

build:
	$(ALIGNC) build $(ENTRY)

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
	./scripts/run-provider-smoke

index-smoke: build
	./scripts/run-index-smoke

test-selection-smoke: build
	./scripts/run-test-selection-smoke

patch-eval-smoke: build
	./scripts/run-patch-eval-smoke

verify-loop-smoke: build
	./scripts/run-verification-loop-smoke

failure-memory-smoke: verify-loop-smoke

prompt-model-smoke:
	./scripts/run-prompt-model-smoke

prompt-score-smoke:
	./scripts/run-prompt-score-smoke

prompt-score-prefix-smoke:
	./scripts/run-prompt-score-prefix-smoke

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

ci:
	@exit 1
