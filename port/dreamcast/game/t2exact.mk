# t2exact.mk - lane t2exact (2026-10-15): tranche 2 exact levers of PERF-BACKLOG-CH1-2 (A2b; B4 and B6 were dropped: docs/lanes/t2exact.md). Every
# knob defaults to 0: no effect, the image is unchanged. docs/lanes/t2exact.md has the measurements and gates.
#
# GC_CENSUS_TRIM=1 (A2b; exact, render only): the GC render census's leftover per-call work, without a change to any
# value: (#3) gx_fast.h - the hot GXGetProjectionv / GXGetViewportv / GXSetProjection callers (re4dc_draw_model_part,
# EspCommonTrans, the ID quad, CameraSetProjection) copy / store gx_stub.cpp's state words inline; (#11) trans.cpp
# sourceActorIdentity reads room heap 4's live flag and generation in place of re4dc_room4_state(), and
# re4dc_coarse_actor_source / re4dc_coarse_ganado_source find a static chunk table element from the table's
# address range (chunk_find.h) instead of comparing every element. Census #12 (re4dc_model_diagnostic_enabled) is
# lane g1parts' G1_DIAG_INLINE and is not repeated here.
GC_CENSUS_TRIM ?= 0
ifneq ($(GC_CENSUS_TRIM),0)
ifneq ($(GC_CENSUS_TRIM),1)
$(error GC_CENSUS_TRIM must be 0 or 1)
endif
# gx_stub.cpp's GXGetViewportv adds the alternate-line jitter when RES_ALTERNATE is on (game30.mk: RENDER_OPTION=1
# without RENDER_DOUBLE=1); the inline copy must do the same (gx_stub.cpp checks the two agree).
T2X_GXF_JITTER := $(if $(filter 1,$(RENDER_OPTION)),$(if $(filter 1,$(RENDER_DOUBLE)),0,1),0)
GAME_CPPFLAGS += -DRE4DC_GC_CENSUS_TRIM=1 -DRE4DC_GXF_JITTER=$(T2X_GXF_JITTER)
PLATFORM_CPPFLAGS += -DRE4DC_GC_CENSUS_TRIM=1 -DRE4DC_GXF_JITTER=$(T2X_GXF_JITTER)
endif
