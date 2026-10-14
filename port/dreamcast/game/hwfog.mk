# HW_FOG_HAZE=1 (lane hwfog 2026-10-14, issue #29; render only, default 0): the distant part of a room's camera haze
#   (Esp15, owner 0xd0, as EFFECT_PS2_HAZE draws it) is carried by the PVR fog table instead of translucent sprites.
#   hwfog.cpp holds one row per room: the keep depth (haze sprites nearer than it are still drawn: the close, visible
#   mist), the haze box depth and the mean veil the replaced sprites laid over the scene (measured per room, see
#   port/dreamcast/docs/HW_FOG_HAZE.md). re4dc_fog_frame (platform/native_static.cpp) folds that veil into the GXSetFog table, ramped from the
#   keep depth to the box depth and scaled by the haze's own indoor fade (8 steps, so the table is rewritten only when a
#   step changes). The haze code (src/game/esp_sub.cpp) asks re4dc_hwfog_haze() per haze sprite it would draw.
#   Generators, their Rnd() draws, the effect pool and every sprite's motion are unchanged (draw-time only).
#   Needs NATIVE_FOG=1 and EFFECT_PS2_HAZE=1. Default 0: hwfog.cpp is not built and no hook compiles in (identical image).
HW_FOG_HAZE ?= 0
#   HW_FOG_VEIL_PCT=n (test builds, veil calibration; default 100): every row's veil scaled to n % (0 = the distant
#   haze sprites are skipped with no veil in their place).
HW_FOG_VEIL_PCT ?= 100
ifneq ($(filter-out 0 1,$(HW_FOG_HAZE)),)
$(error HW_FOG_HAZE is 0 or 1)
endif
ifeq ($(HW_FOG_HAZE),1)
ifneq ($(NATIVE_FOG)$(EFFECT_PS2_HAZE),11)
$(error HW_FOG_HAZE=1 needs NATIVE_FOG=1 and EFFECT_PS2_HAZE=1)
endif
# The haze hook (re4dc_hwfog_haze in src/game/esp_sub.cpp's EFFECT_PS2_HAZE draw) is carried by the effects lane
# (lane/t11-fx): refuse a tree without it (the fog veil would double the still-drawn haze).
ifeq ($(shell grep -c re4dc_hwfog_haze $(ROOT)/src/game/esp_sub.cpp 2>/dev/null),)
$(error HW_FOG_HAZE=1: cannot read src/game/esp_sub.cpp)
endif
ifeq ($(shell grep -c re4dc_hwfog_haze $(ROOT)/src/game/esp_sub.cpp 2>/dev/null),0)
$(error HW_FOG_HAZE=1 needs the re4dc_hwfog_haze hook in src/game/esp_sub.cpp (lane/t11-fx))
endif
PLATFORM_OBJS += $(OBJDIR)/hwfog.o
# Included after the link rule: name the object as its prerequisite here.
$(TARGET): $(OBJDIR)/hwfog.o
$(OBJDIR)/hwfog.o: hwfog.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -Iplatform/include -DRE4DC_HW_FOG_VEIL_PCT=$(HW_FOG_VEIL_PCT) -MMD -MP -c $< -o $@
-include $(OBJDIR)/hwfog.d
$(OBJDIR)/platform/native_static.o: PLATFORM_CPPFLAGS += -DRE4DC_HW_FOG_HAZE=1
$(OBJDIR)/src/game/esp_sub.o: GAME_CPPFLAGS += -DRE4DC_HW_FOG_HAZE=1
endif
