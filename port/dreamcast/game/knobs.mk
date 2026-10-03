# knobs.mk - `make re4dc-knobs KNOBS_FILE=<file> KNOB_NAMES="<names>"` with the build's own arguments writes
# NAME=value for each name as the makefiles resolved it (defaults, the command line, and overrides such as
# D349_RENDERER_STACK=1 forcing MODEL_DRAW_PLANS=1), one per line. It builds nothing. tools/d367/build-r21.sh
# writes $(OUT)/resolved-knobs.txt this way after every build.
.PHONY: re4dc-knobs
re4dc-knobs:
	$(if $(KNOBS_FILE),,$(error re4dc-knobs needs KNOBS_FILE))
	$(file >$(KNOBS_FILE),# resolved make knobs: $(words $(KNOB_NAMES)) names)
	$(foreach v,$(KNOB_NAMES),$(file >>$(KNOBS_FILE),$(v)=$($(v))))
	@:
