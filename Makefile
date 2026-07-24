ALIGNC := ./scripts/alignc
ALIGN_REPO ?= ../align
ENTRY := src/main.align
EVAL_CORPUS := eval/tasks/smoke-v1.json

.PHONY: check run build fmt format-check eval-smoke loop-smoke align-revision align-build ci

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

loop-smoke: build
	./scripts/run-loop-smoke

align-revision:
	./scripts/check-align-revision

align-build: align-revision
	cargo build --manifest-path $(ALIGN_REPO)/Cargo.toml --locked --release \
		-p align_runtime -p align_driver

ci: align-build format-check check build eval-smoke loop-smoke
