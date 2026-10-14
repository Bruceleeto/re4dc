# worldhole.mk - PS2 world holes (test 11 item E, lane t11-wh, 2026-10-14).
# WORLD_HOLE_DIAG=1 (test only, default 0: no effect): per PS2 world part that a pass does not draw (a fallback: with
# PS2_WORLD_ROOMS=2 a hole), the reason native_ui.cpp re4dc_ps2_world_direct_begin refused it, with load()'s refusal
# text for a texture that is not resident. Log: `WHD frame= room= pass= parts= refused= <counts per reason> first=<key>
# used= overflow= texwhy=` for each pass of a frame with refusals, `WHDSUM` per pass every 120 frames (room totals).
# Reasons: draw (no bind refusal recorded), nested, notready, aborted (stream aborted: an earlier model part overflowed
# the frame queues), storage, full (model packet store), tex (texture not resident), size, abort2, owner, key.
WORLD_HOLE_DIAG ?= 0
ifneq ($(filter-out 0 1,$(WORLD_HOLE_DIAG)),)
$(error WORLD_HOLE_DIAG must be 0 or 1)
endif
ifeq ($(WORLD_HOLE_DIAG),1)
ifeq ($(PS2_WORLD_MESH),0)
$(error WORLD_HOLE_DIAG needs PS2_WORLD_MESH=1)
endif
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_static.o: PLATFORM_CPPFLAGS += -DRE4DC_WORLD_HOLE_DIAG=1
endif
# WORLD_HOLE_FIX=1 (render only, default 0: no effect): a translucent model part that finds the frame queue full
# (native_ui.cpp defer_part: frame_storage 26,624 B + the 8 KiB model spill) is dropped alone instead of aborting the
# frame. The abort kept the whole frame off the screen (the last frame stays up) and refused every later PS2 world
# PT / TR part (WHD reason "aborted"): r117 entry (frames 194-236, up to 55 of 66 TR parts), the r119 El Gigante
# fight (61 frames in a row). Log: `WHFIX frame= dropped_parts= bytes= frames= total=` (first 64 frames with drops,
# then every 120th). No memory change.
WORLD_HOLE_FIX ?= 0
ifneq ($(filter-out 0 1,$(WORLD_HOLE_FIX)),)
$(error WORLD_HOLE_FIX must be 0 or 1)
endif
ifeq ($(WORLD_HOLE_FIX),1)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_WORLD_HOLE_FIX=1
endif
