# Contextual docked display, default off. No objects/flags when disabled.
VMU_CONTEXT ?= 0
VMU_MOTION ?= 1
ifeq ($(VMU_CONTEXT),1)
.PHONY: vmu-context-force
$(OBJDIR)/vmu-context-options.h: vmu-context-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_VMU_CONTEXT 1\n#define RE4DC_VMU_MOTION %s\n#include "re4dc_vmu.h"\n' '$(VMU_MOTION)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
VMU_GAME = $(OBJDIR)/src/game/main.o $(OBJDIR)/src/game/sscrn.o $(OBJDIR)/src/game/pl_sub.o \
 $(OBJDIR)/mod/pl11/src/pl11/pl11.o $(OBJDIR)/mod/pl14/src/pl14/pl14.o \
 $(OBJDIR)/mod/Sscrn/src/Sscrn/ss_term.o
VMU_PORT_GAME = $(OBJDIR)/pace.o $(OBJDIR)/dbgslot_bridge.o $(OBJDIR)/vmu_context.o $(OBJDIR)/vmu_render.o
VMU_PLATFORM = $(OBJDIR)/platform/pad.o $(OBJDIR)/platform/vmu_lcd.o $(OBJDIR)/platform/native_ui.o
$(VMU_GAME) $(VMU_PORT_GAME) $(VMU_PLATFORM): $(OBJDIR)/vmu-context-options.h
$(VMU_GAME) $(VMU_PORT_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/vmu-context-options.h
$(VMU_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/vmu-context-options.h
# Image size (heap 4 couples to _end): the display's own objects are built for size, off the frame path.
$(OBJDIR)/platform/vmu_lcd.o: PLATFORM_CPPFLAGS += -Os
VMU_OPT = -Os
# Luis's page needs his module (pl14, not in the native recipe): his portraits are linked only with it.
VMU_LUIS := $(if $(filter pl14 pl14:%,$(MODULES)),1,0)
$(OBJDIR)/vmu_render.o: VMU_OPT += -DRE4DC_VMU_LUIS=$(VMU_LUIS)
PLATFORM_OBJS += $(OBJDIR)/vmu_context.o $(OBJDIR)/vmu_render.o
$(TARGET): $(OBJDIR)/vmu_context.o $(OBJDIR)/vmu_render.o $(OBJDIR)/platform/vmu_lcd.o
$(OBJDIR)/vmu_context.o: vmu_context.cpp vmu_context.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) $(VMU_OPT) -MMD -MP -c $< -o $@
$(OBJDIR)/vmu_render.o: vmu_render.cpp vmu_context.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) $(VMU_OPT) -MMD -MP -c $< -o $@
-include $(OBJDIR)/vmu_context.d $(OBJDIR)/vmu_render.d
endif
