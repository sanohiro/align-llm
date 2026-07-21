ALIGNC := ./scripts/alignc
ENTRY := src/main.align

.PHONY: check run build fmt

check:
	$(ALIGNC) check-per-unit $(ENTRY)

run:
	$(ALIGNC) run $(ENTRY)

build:
	$(ALIGNC) build $(ENTRY)

fmt:
	@find src -name '*.align' -type f -print0 | while IFS= read -r -d '' file; do \
		$(ALIGNC) fmt "$$file" --write; \
	done
