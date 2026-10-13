# D367 effects30: effect sprites (EspCommonTrans). Included at the end of the Makefile. Every
# knob defaults to 0 and then contributes nothing (identical image).
#   EFFECT_LEAN=1    the common sprite draw keeps only the GX state the native side reads
#                    (projection, normal matrix, channel control/material colour, TEV scale);
#                    no blend/TEV/vertex-format/texture-load/display-list stub traffic. The
#                    heat-shimmer and frame-buffer ("nega") variants are untouched. Render only.
#   EFFECT_SPRITES=1 native PVR sprites for the approved classes: weapon muzzle flash (owners
#                    0x34..0x4f), the core effects of the same shot (owner 0) and blood (owner
#                    0x10). Excluded: full-screen sheets (0xd0), room ambient/screen effects (0x01),
#                    masked, spline (Esp1b), texture-render targets, non-blend modes. Sprites go
#                    into the deferred translucent queue in OT order; on queue pressure a sprite
#                    is dropped, never the frame. Render only.
#   EFFECT_SPRITE_MAX=N  sprites per frame (default 64).
#   EFFECT_ROOM=M    (needs EFFECT_SPRITES=1) bit mask: the room's own effects join the native
#                    sprite classes. 1: the room owner's est sets (owner 0x01: r101's pyre, R101Init:
#                    flames, smoke, embers); 2: the room effect sets SstSet starts at room init (owner
#                    0xd0: glows, light shafts, smoke), apart from 4: their camera haze particles (id
#                    0x15) and mist sheets (id 0x48), the fill-heavy class (r101: ~3 Mpx a frame).
#                    3 = the fires and glows, 7 = everything the GameCube draws. Same eligibility
#                    rules otherwise (no mask stage, render target, Esp1b spline or non-blend mode).
#                    With the knob on, a sprite wholly off screen or wholly beyond the fogged View far
#                    (ACTOR_FOG_GATE's value; the fog table is at 100% there) is not queued, for every
#                    class. Render only.
#   COARSE_FX_SPRITES=1 (needs COARSE=1, EFFECT_SPRITES=1 and PACE_TRANS_SKIP bit 2048): a drawn coarse
#                    image's logic-only EspTrans also queues the live effects the sprite path draws
#                    (EspCommonTrans + the EFFECT_SPRITES / EFFECT_ROOM classes), so they draw as native
#                    sprites in the effect OT, and coarse.cpp draws no opaque marker for them. =2: no
#                    markers at all (the other effects are not drawn in coarse images). The queue step
#                    writes no game state for these classes (the render-target flag 0x10000 is not
#                    eligible). Render only.
EFFECT_LEAN ?= 0
EFFECT_SPRITES ?= 0
# The source laser uses Esp19, a line rather than an EspCommonTrans sprite.
# Native packet extension only: existing OT queue and frame storage, no texture.
NATIVE_LASER ?= 0
ifneq ($(filter-out 0 1,$(NATIVE_LASER)),)
$(error NATIVE_LASER is 0 or 1)
endif
ifeq ($(NATIVE_LASER),1)
ifneq ($(EFFECT_SPRITES),1)
$(error NATIVE_LASER needs EFFECT_SPRITES=1)
endif
$(OBJDIR)/src/game/esp.o $(OBJDIR)/src/game/esp_sub.o $(OBJDIR)/src/game/esp19.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_LASER=1
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_NATIVE_LASER=1
endif
COARSE_FX_SPRITES ?= 0
ifneq ($(COARSE_FX_SPRITES),0)
ifneq ($(EFFECT_SPRITES),1)
$(error COARSE_FX_SPRITES needs EFFECT_SPRITES=1)
endif
$(OBJDIR)/src/game/trans.o $(OBJDIR)/src/game/esp.o $(OBJDIR)/src/game/esp_sub.o $(OBJDIR)/coarse.o: GAME_CPPFLAGS += -DRE4DC_COARSE_FX_SPRITES=$(COARSE_FX_SPRITES)
endif
EFFECT_SPRITE_MAX ?= 64
EFFECT_ROOM ?= 0
#   ESP_SPRITE_FAST=1 (needs EFFECT_LEAN=1 and EFFECT_SPRITES=1; lane fx 2026-10-04): the effect sprite pass without
#                    work nothing reads. EspCommonTrans returns at once for a sprite the native path does not take
#                    (under EFFECT_LEAN nothing draws it: only m_Mat and GX state were written), and after the native
#                    sprite for one it does (no normal matrix inverse/load); the coarse sprite pass reads the fogged
#                    View far once per pass; re4dc_effect_sprite tests finiteness on the bits and reuses the last
#                    compiled sprite header when texture, blend and screen flag match. Render only, writes no game
#                    state. (The lane's EspTrans dead-slot skip over GAME_FX_SCAN's live map measured neutral and
#                    was left out at integration, 2026-10-05.)
#   ESP47_SKIP_LEAN=1 (needs PACE_CATCHUP; lane fx 2026-10-04): on an iteration that draws nothing, Esp47 (screen
#                    wrap overlays, queued by the logic-only effect pass for its m_Pos wrap) keeps the wrap and the
#                    shifted m_Pos round trips and drops its sprite draws. Render only.
ESP_SPRITE_FAST ?= 0
ifneq ($(ESP_SPRITE_FAST),0)
ifneq ($(EFFECT_LEAN)$(EFFECT_SPRITES),11)
$(error ESP_SPRITE_FAST needs EFFECT_LEAN=1 and EFFECT_SPRITES=1)
endif
$(OBJDIR)/src/game/esp.o $(OBJDIR)/src/game/esp_sub.o: GAME_CPPFLAGS += -DRE4DC_ESP_SPRITE_FAST=$(ESP_SPRITE_FAST)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_ESP_SPRITE_FAST=$(ESP_SPRITE_FAST)
endif
ESP47_SKIP_LEAN ?= 0
ifneq ($(ESP47_SKIP_LEAN),0)
ifeq ($(PACE_CATCHUP),0)
$(error ESP47_SKIP_LEAN needs PACE_CATCHUP (pace.cpp re4dc_pace_skipping))
endif
$(OBJDIR)/src/game/esp47.o: GAME_CPPFLAGS += -DRE4DC_ESP47_SKIP_LEAN=$(ESP47_SKIP_LEAN)
endif
#   EFFECT_PS2_HAZE=1 (needs EFFECT_SPRITES=1 and EFFECT_ROOM bit 4; lane ph 2026-10-05): the room generator's
#                    camera haze (Esp15, owner 0xd0) as the PS2 release draws it, in the rooms whose PS2 EFF has it
#                    (r100, r101, r103; others unchanged): a fixed subset of the live sprites (pool slot % 5 / 2 / 1)
#                    inside the PS2's camera box (5.0 / 5.0 / 5.3 m deep), the PS2 size (x1.48 / 1.46 / 1.64), colour,
#                    alpha (34 / 35 / 35 against GC 70 / 25 / 30) and fades (near 3.0 -> 0.5 m, far: last 30 % of the
#                    box). About 11 / 8 / 11 sprites in view against GC 60 / 39 / 41 live. Render only: the
#                    generator, its Rnd() draws and every sprite's motion run as before; only the draw is changed.
#   EFFECT_PS2_STREAK=1 (needs EFFECT_SPRITES=1 and EFFECT_ROOM bit 2): r100's house window streaks (sst 0x09
#                    records 5, 8, 13: the Esp0a copies, up to ~80 static additive sprites; the stairs glare) are
#                    not drawn, as on the PS2. =2 (needs EFFECT_FADE_CLAMP=1) also draws the PS2's light shafts in
#                    their place (texture e9: the stairs window's, inside its PS2 area 13, and the back window's
#                    two). Render only: the generators, their Rnd() and the copies themselves still run.
#   EFFECT_FADE_CLAMP=1 port fix: ChannelSet's near fade (m_Del_far -> m_Del_near) goes negative inside m_Del_near;
#                    the GameCube's (u8) store saturates that to 0, SH-4 wrapped it (near-opaque sprites inside the
#                    near distance: haze within 1 m, the streak copies, the dust). Clamped at 0. Render only.
#   EFFECT_PS2_TOGGLE=1 test builds (needs one of the three above): the look starts at the GameCube's (as the
#                    base) and hold X + press START steps GC -> GF (fade clamp) -> PH (PS2 haze) -> PS (PS2 haze +
#                    streak) over the built ones (START is masked while the chord is down; L/R must be up: R + START
#                    paces, L + START is the debug slot); the PACE_VMU page shows the look after its GPU (or MODE)
#                    line; DBG_WARP's warp.txt `fxmode <flags>` (1 clamp, 2 haze, 4 streak) sets it at load.
#   EFFECT_HAZE_LEAN=<mask> (Phase 2 B6, STUDY2 section 1; needs EFFECT_PS2_HAZE=1; render only, default 0): cheaper
#                    outdoor haze in r100 / r101 / r103 while the PS2 haze look is on. 1 (M1): the GameCube mist
#                    sheets (id 0x48: f6 / cb / d0 / f3 / 33) the PS2 deleted are not drawn. 2 (M3): the fog table
#                    carries ~55 % of the haze's mean veil (1 -> 5 m ramp; r100 0.034, r101 0.025, r103 0.035 x the
#                    indoor fade in 8 steps) and only ~30 % of the PS2 subset draws (slot % 16 / 7 / 3) at alpha x1.5.
#                    4 (M2): each haze sprite is an octagon (apothem 0.9 of the half side: -33 % pixels). Generators,
#                    Rnd() and sprite motion are untouched (draw-time choices only).
#   EFFECT_HAZE_LEAN_TOGGLE=1 (test builds; needs EFFECT_HAZE_LEAN=7 and LOOK_TOGGLE=1): the haze mode at run time,
#                    X + D-pad up + START steps W (as off) -> M1 -> M2 -> M3 -> all; the name shows top left for 3 s.
#   PS2_FX_ROOMS=1 (lane psfx 2026-10-13, user option A; needs EFFECT_PS2_HAZE=1 and EFFECT_PS2_STREAK>=1; render only,
#                    default 0): the PS2 haze recipe and the PS2's removed window streaks in more route rooms, from
#                    the PS2 rNNN.dat EFF (re4-ps2-table-survey-20261013 WORLD-FX.md). r106: both haze sets (GC 30 x
#                    2.6 m, R 6.5 m, alpha 30 / 25 -> PS2 10 x 2.0 m, R 5.0 / 4.0 m, alpha 40 / 35; near fades 3.0 ->
#                    0.5 m / 2.0 -> 1.0 m) and its five Esp0a window streak records (sst 0x08 / 0x09 / 0x0b: their
#                    id-0 copies are not drawn). r10a: GC 41 x 1.33 m, R 6.3 m, alpha 20 -> PS2 10 x 1.7 m, R 4.0 m,
#                    alpha 20 (near 2.0 -> 1.0 m). As EFFECT_PS2_HAZE: the generators, their Rnd() draws, the pool
#                    and every sprite's motion run as before; only the draw changes.
PS2_FX_ROOMS ?= 0
ifneq ($(PS2_FX_ROOMS),0)
ifneq ($(PS2_FX_ROOMS),1)
$(error PS2_FX_ROOMS is 0 or 1)
endif
ifneq ($(EFFECT_PS2_HAZE),1)
$(error PS2_FX_ROOMS needs EFFECT_PS2_HAZE=1)
endif
ifeq ($(filter 1 2,$(EFFECT_PS2_STREAK)),)
$(error PS2_FX_ROOMS needs EFFECT_PS2_STREAK=1 or 2)
endif
endif
## Stage-1 PS2 recipe extensions are draw-only and independently reversible.
PS2_FX_STAGE1 ?= 0
ifneq ($(PS2_FX_STAGE1),0)
ifneq ($(PS2_FX_STAGE1)$(PS2_FX_ROOMS),11)
$(error PS2_FX_STAGE1 must be 0 or 1 and needs PS2_FX_ROOMS=1)
endif
endif
EFFECT_HAZE_LEAN ?= 0
EFFECT_HAZE_LEAN_TOGGLE ?= 0
EFFECT_PS2_HAZE ?= 0
EFFECT_PS2_STREAK ?= 0
EFFECT_FADE_CLAMP ?= 0
EFFECT_PS2_TOGGLE ?= 0
ifneq ($(filter-out 0 1,$(EFFECT_PS2_HAZE))$(filter-out 0 1 2,$(EFFECT_PS2_STREAK))$(filter-out 0 1,$(EFFECT_FADE_CLAMP))$(filter-out 0 1,$(EFFECT_PS2_TOGGLE)),)
$(error EFFECT_PS2_HAZE / EFFECT_FADE_CLAMP / EFFECT_PS2_TOGGLE are 0 or 1, EFFECT_PS2_STREAK 0..2)
endif
ifneq ($(EFFECT_PS2_HAZE)$(EFFECT_PS2_STREAK),00)
ifneq ($(EFFECT_SPRITES),1)
$(error EFFECT_PS2_HAZE / EFFECT_PS2_STREAK need EFFECT_SPRITES=1)
endif
endif
ifeq ($(EFFECT_PS2_HAZE),1)
ifeq ($(filter 4 5 6 7,$(EFFECT_ROOM)),)
$(error EFFECT_PS2_HAZE needs EFFECT_ROOM bit 4 (the haze class drawn))
endif
endif
ifneq ($(EFFECT_PS2_STREAK),0)
ifeq ($(filter 2 3 6 7,$(EFFECT_ROOM)),)
$(error EFFECT_PS2_STREAK needs EFFECT_ROOM bit 2 (the room glows / streaks drawn))
endif
endif
ifeq ($(EFFECT_PS2_STREAK),2)
ifneq ($(EFFECT_FADE_CLAMP),1)
$(error EFFECT_PS2_STREAK=2 needs EFFECT_FADE_CLAMP=1 (the shafts' near fade))
endif
endif
ifneq ($(EFFECT_HAZE_LEAN),0)
ifeq ($(filter $(EFFECT_HAZE_LEAN),1 2 3 4 5 6 7),)
$(error EFFECT_HAZE_LEAN is a mask 1..7)
endif
ifneq ($(EFFECT_PS2_HAZE),1)
$(error EFFECT_HAZE_LEAN needs EFFECT_PS2_HAZE=1)
endif
ifneq ($(filter 2 3 6 7,$(EFFECT_HAZE_LEAN)),)
$(OBJDIR)/platform/native_static.o: $(OBJDIR)/effects30.h
$(OBJDIR)/platform/native_static.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/effects30.h
endif
endif
ifeq ($(EFFECT_HAZE_LEAN_TOGGLE),1)
ifneq ($(EFFECT_HAZE_LEAN)$(LOOK_TOGGLE),71)
$(error EFFECT_HAZE_LEAN_TOGGLE=1 needs EFFECT_HAZE_LEAN=7 and LOOK_TOGGLE=1 (the X + START chord and the label))
endif
$(OBJDIR)/platform/pad.o: PLATFORM_CPPFLAGS += -DRE4DC_EFFECT_HAZE_LEAN_TOGGLE=1
$(OBJDIR)/platform/native_static.o: PLATFORM_CPPFLAGS += -DRE4DC_EFFECT_HAZE_LEAN_TOGGLE=1
else ifneq ($(EFFECT_HAZE_LEAN_TOGGLE),0)
$(error EFFECT_HAZE_LEAN_TOGGLE is 0 or 1)
endif
ifeq ($(EFFECT_PS2_TOGGLE),1)
ifeq ($(EFFECT_PS2_HAZE)$(EFFECT_PS2_STREAK)$(EFFECT_FADE_CLAMP),000)
$(error EFFECT_PS2_TOGGLE needs EFFECT_PS2_HAZE, EFFECT_PS2_STREAK or EFFECT_FADE_CLAMP)
endif
$(OBJDIR)/platform/pad.o: PLATFORM_CPPFLAGS += -DRE4DC_EFFECT_PS2_TOGGLE=1
$(OBJDIR)/pace.o: GAME_CPPFLAGS += -DRE4DC_EFFECT_PS2_TOGGLE=1
$(OBJDIR)/dbgwarp_bridge.o: GAME_CPPFLAGS += -DRE4DC_EFFECT_PS2_TOGGLE=1
endif
.PHONY: effects30-force
$(OBJDIR)/effects30.h: effects30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_EFFECT_LEAN %s\n#define RE4DC_EFFECT_SPRITES %s\n#define RE4DC_EFFECT_SPRITE_MAX %s\n' '$(EFFECT_LEAN)' '$(EFFECT_SPRITES)' '$(EFFECT_SPRITE_MAX)' > $@.tmp
ifneq ($(EFFECT_ROOM),0)
	@printf '#define RE4DC_EFFECT_ROOM %s\n' '$(EFFECT_ROOM)' >> $@.tmp
endif
ifneq ($(EFFECT_PS2_HAZE),0)
	@printf '#define RE4DC_EFFECT_PS2_HAZE %s\n' '$(EFFECT_PS2_HAZE)' >> $@.tmp
endif
ifneq ($(EFFECT_PS2_STREAK),0)
	@printf '#define RE4DC_EFFECT_PS2_STREAK %s\n' '$(EFFECT_PS2_STREAK)' >> $@.tmp
endif
ifneq ($(EFFECT_FADE_CLAMP),0)
	@printf '#define RE4DC_EFFECT_FADE_CLAMP %s\n' '$(EFFECT_FADE_CLAMP)' >> $@.tmp
endif
ifneq ($(EFFECT_PS2_TOGGLE),0)
	@printf '#define RE4DC_EFFECT_PS2_TOGGLE %s\n' '$(EFFECT_PS2_TOGGLE)' >> $@.tmp
endif
ifneq ($(EFFECT_HAZE_LEAN),0)
	@printf '#define RE4DC_EFFECT_HAZE_LEAN %s\n' '$(EFFECT_HAZE_LEAN)' >> $@.tmp
endif
ifneq ($(EFFECT_HAZE_LEAN_TOGGLE),0)
	@printf '#define RE4DC_EFFECT_HAZE_LEAN_TOGGLE 1\n' >> $@.tmp
endif
ifneq ($(PS2_FX_ROOMS),0)
	@printf '#define RE4DC_PS2_FX_ROOMS %s\n' '$(PS2_FX_ROOMS)' >> $@.tmp
endif
ifneq ($(PS2_FX_STAGE1),0)
	@printf '#define RE4DC_PS2_FX_STAGE1 %s\n' '$(PS2_FX_STAGE1)' >> $@.tmp
endif
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
EFFECTS30_GAME = $(OBJDIR)/src/game/esp_sub.o
EFFECTS30_PLATFORM = $(OBJDIR)/platform/native_ui.o
$(EFFECTS30_GAME) $(EFFECTS30_PLATFORM): $(OBJDIR)/effects30.h
$(EFFECTS30_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/effects30.h
$(EFFECTS30_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/effects30.h
