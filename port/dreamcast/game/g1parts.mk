# g1parts.mk (lane g1parts 2026-10-15): "group 1" exact speed items. Every knob defaults to 0 (knob-off image unchanged);
# each changes only how the same work is done (logic STRICT, picture identical). Lane doc: TEST14-SCOPE.md "Group 1 parts".

# G1_DIAG_INLINE=1 (census #12): the per-part callers of re4dc_model_diagnostic_enabled() (re4dc_draw_model_part,
# re4dc_model_submit, re4dc_model_packet_reserve, the crowd note in trans.cpp) read its latched value inline
# (native_model.h RE4DC_MODEL_DIAG); the first call still opens the flag file. About 700 calls per frame at the cross.
G1_DIAG_INLINE ?= 0
ifneq ($(filter-out 0 1,$(G1_DIAG_INLINE)),)
$(error G1_DIAG_INLINE must be 0 or 1)
endif
ifeq ($(G1_DIAG_INLINE),1)
$(OBJDIR)/src/game/trans.o $(OBJDIR)/model_bridge.o: GAME_CPPFLAGS += -DRE4DC_G1_DIAG_INLINE=1
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_model.o: PLATFORM_CPPFLAGS += -DRE4DC_G1_DIAG_INLINE=1
endif

# G1_FP_UNSIGNED=1 (render only, exact): unsigned -> float conversions on the per-part / per-sprite path
# (re4dc_model_packet_reserve u/v scale, inlined into packet_begin; fx_packet su/sv) go through int: the values are
# picture sizes (< 2^31), so the floats are the same, without GCC's double-precision unsigned conversion (FPSCR.PR
# switched twice per conversion).
G1_FP_UNSIGNED ?= 0
ifneq ($(filter-out 0 1,$(G1_FP_UNSIGNED)),)
$(error G1_FP_UNSIGNED must be 0 or 1)
endif
ifeq ($(G1_FP_UNSIGNED),1)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_G1_FP_UNSIGNED=1
endif

# G1_PART_CENSUS=1 (DIAGNOSTIC only, never in a play recipe): "G1PC actor" / "G1PC tex" lines every 120 frames counting
# repeated per-part work on the native side (parts, model changes, light builds with the previous build's inputs,
# texture lookups of the previous lookup's image, model header cache hits) to price g1parts item 4.
G1_PART_CENSUS ?= 0
ifneq ($(G1_PART_CENSUS),0)
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_actor_fast.o: PLATFORM_CPPFLAGS += -DRE4DC_G1_PART_CENSUS=1
endif

# G1_PRESORT_LAZY=1 (render only, exact; needs PVR_READY_STRICT=1, which wraps pvr_set_presort_mode): a scene's presort
# requests are written once at pvr_scene_finish, only when the bank's tiles hold the other mode (native_ui.cpp
# presort_lazy). In play the stream opens presorted and the world switches to autosort in the same scene, so KOS
# rewrote ~600 tile control words (uncached VRAM) twice per frame; the bank now keeps autosort and nothing is written.
# A "G1 presort lazy" line every 1800 frames counts requests / writes / skips.
G1_PRESORT_LAZY ?= 0
ifneq ($(filter-out 0 1,$(G1_PRESORT_LAZY)),)
$(error G1_PRESORT_LAZY must be 0 or 1)
endif
ifeq ($(G1_PRESORT_LAZY),1)
ifneq ($(PVR_READY_STRICT),1)
$(error G1_PRESORT_LAZY needs PVR_READY_STRICT=1)
endif
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_G1_PRESORT_LAZY=1
GAME_LDFLAGS += -Wl,--wrap=pvr_scene_finish
endif
