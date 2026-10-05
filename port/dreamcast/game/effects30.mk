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
.PHONY: effects30-force
$(OBJDIR)/effects30.h: effects30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_EFFECT_LEAN %s\n#define RE4DC_EFFECT_SPRITES %s\n#define RE4DC_EFFECT_SPRITE_MAX %s\n' '$(EFFECT_LEAN)' '$(EFFECT_SPRITES)' '$(EFFECT_SPRITE_MAX)' > $@.tmp
ifneq ($(EFFECT_ROOM),0)
	@printf '#define RE4DC_EFFECT_ROOM %s\n' '$(EFFECT_ROOM)' >> $@.tmp
endif
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
EFFECTS30_GAME = $(OBJDIR)/src/game/esp_sub.o
EFFECTS30_PLATFORM = $(OBJDIR)/platform/native_ui.o
$(EFFECTS30_GAME) $(EFFECTS30_PLATFORM): $(OBJDIR)/effects30.h
$(EFFECTS30_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/effects30.h
$(EFFECTS30_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/effects30.h
