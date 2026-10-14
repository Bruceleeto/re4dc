# fxtrim.mk - effect sprite trimming (test 11, lane t11-mt, 2026-10-14).
# FX_SPRITE_TRIM=1 (render only, default 0: no effect; needs EFFECT_SPRITES=1): an effect sprite whose texture is in
# platform/include/fx_sprite_trim_table.inc (tools/d367/fxtrim/fxtrim.py) is drawn over the part of the texture that
# can change a pixel: the box of the UV points its alpha > 0 texels reach through the bilinear filter (+ 0.5 texel
# spare), widened to UV values the PVR sprite's 16-bit UV holds exactly, so every pixel still drawn samples the texture
# exactly where it did and every pixel no longer drawn would have blended an alpha-0 texel. Only where that holds: blend
# SRCALPHA with INVSRCALPHA or ONE (alpha 0 leaves the pixel as it was), one depth for the four corners (camera-facing),
# an exact parallelogram and the whole image (UV 0..1 along the edges).
# FX_SPRITE_TRIM=2: as 1, and a big sprite (>= 4096 screen pixels) whose texture's bounding octagon (x, y, x + y, x - y
# extents of the same UV points) saves at least 10 % more than the box is drawn as an 8-vertex textured strip over the
# octagon (float UV on the sprite's own plane; not the sprite's 16-bit UV: up to a few levels differ, see the lane doc).
# FX_SPRITE_TRIM_DIAG=1 (test only, default 0): logs `fxtrim key:` once per effect texture key (size, format, blend,
# UV corners, depths; the input of fxtrim.py), `fxtrim:` totals and `fxtrim top:` (the 6 keys covering the most screen)
# every 600 frames (unclipped kilo-pixels before / after). Neither touches the generators, Rnd(), the effect pool or
# the sprite cap.
FX_SPRITE_TRIM ?= 0
FX_SPRITE_TRIM_DIAG ?= 0
ifneq ($(filter-out 0 1 2,$(FX_SPRITE_TRIM)),)
$(error FX_SPRITE_TRIM must be 0, 1 or 2)
endif
ifneq ($(filter-out 0 1,$(FX_SPRITE_TRIM_DIAG)),)
$(error FX_SPRITE_TRIM_DIAG must be 0 or 1)
endif
ifneq ($(FX_SPRITE_TRIM)$(FX_SPRITE_TRIM_DIAG),00)
ifneq ($(EFFECT_SPRITES),1)
$(error FX_SPRITE_TRIM / FX_SPRITE_TRIM_DIAG need EFFECT_SPRITES=1)
endif
endif
ifneq ($(FX_SPRITE_TRIM),0)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_FX_SPRITE_TRIM=$(FX_SPRITE_TRIM)
endif
ifeq ($(FX_SPRITE_TRIM_DIAG),1)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_FX_SPRITE_TRIM_DIAG=1
endif
