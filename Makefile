ALIGNC ?= ./scripts/alignc
ALIGN_REPO ?= ../align
override PINNED_ALIGNC := $(abspath $(ALIGN_REPO)/target/release/alignc)
ENTRY := src/main.align
EVAL_CORPUS := eval/tasks/smoke-v1.json
CODING_CORPUS := eval/tasks/coding-v1.json

.PHONY: check run build fmt format-check eval-smoke eval-coding loop-smoke provider-smoke index-smoke test-selection-smoke baseline-check align-revision align-build ci

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

baseline-check:
	python3 ./eval/runners/verify-baseline.py
	./scripts/run-baseline-invalid-smoke
	./scripts/run-baseline-failure-smoke

align-revision:
	./scripts/check-align-revision

align-build: align-revision
	cargo build --manifest-path $(ALIGN_REPO)/Cargo.toml --locked --release \
		-p align_runtime -p align_driver

ci: align-build
	@test -x "$(PINNED_ALIGNC)" || { echo "pinned Align compiler was not built at $(PINNED_ALIGNC)" >&2; exit 1; }
	$(MAKE) ALIGNC="$(PINNED_ALIGNC)" format-check check build eval-smoke eval-coding loop-smoke baseline-check
