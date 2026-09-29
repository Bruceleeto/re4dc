# D367 post30: the GameCube's full-screen post look on the PVR (look-gaps 2026-09-26, part post). Included at the end
# of the Makefile. Every knob defaults to 0 and then contributes nothing (identical image). Render only.
#   POST_F00=1   Filter00's contrast lift (LIT blur type 2 feedback + contrast; r101 x1.44 on mid-tones) as ONE
#                full-screen translucent quad in the PVR tile buffer: blend (DESTCOLOR, ONE), colour grey c, so
#                d -> d + c d (8-bit, before the RGB565 write-out). c follows the live Filter00 parameters (the
#                flat-field steady state at a mid-tone). Queued at Filter00Render's OT slot in the deferred
#                translucent queue: opaque / punch-through and the translucent parts drawn before it are lifted,
#                later translucent parts and the UI quads (the HUD, OT 0x13..0x15) are not. No texture, no VRAM.
#   POST_F00=4   the same plus the bias: gain, invert, add h, invert = max(0, g d - h) (four quads), the exact
#                flat-field curve above its knee (near-black stays black).
#   POST_F00_DIAG=1  test builds: log per 600 frames how many UI quads were queued before the post (drawn after it,
#                unlike the GameCube) and how many opaque packets followed it (drawn before it on the PVR).
#   PVR_DITHER=1 assert the RGB565 write-out dither (FB_W_CTRL bit 3) after vid_set_mode and log the register.
#                KOS's vid_set_mode already sets it for PM_RGB565, so this changes nothing on a stock KOS;
#                =2 (diagnostic, not a candidate) clears it to show the undithered 565 write-out.
POST_F00 ?= 0
POST_F00_DIAG ?= 0
PVR_DITHER ?= 0
ifneq ($(POST_F00),0)
ifneq ($(D349_RENDERER_STACK),1)
$(error POST_F00 needs D349_RENDERER_STACK=1 (the deferred translucent queue))
endif
endif
.PHONY: post30-force
$(OBJDIR)/post30.h: post30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_POST_F00 %s\n#define RE4DC_POST_F00_DIAG %s\n#define RE4DC_PVR_DITHER %s\n' '$(POST_F00)' '$(POST_F00_DIAG)' '$(PVR_DITHER)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
POST30_GAME = $(OBJDIR)/src/game/filter00.o
POST30_PLATFORM = $(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/vi.o
$(POST30_GAME) $(POST30_PLATFORM): $(OBJDIR)/post30.h
$(POST30_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/post30.h
$(POST30_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/post30.h
