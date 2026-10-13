# Exact PS2 app2 source-selected lost-head geometry; default-off local candidate.
ACTOR_GANADO_PS2_STUMP ?= 0
ACTOR_GANADO_PS2_STUMP_DIR ?=
ifeq ($(filter $(ACTOR_GANADO_PS2_STUMP),0 1),)
$(error ACTOR_GANADO_PS2_STUMP must be 0 or 1)
endif
ifeq ($(ACTOR_GANADO_PS2_STUMP),1)
ifneq ($(ACTOR_TRANSACTION)$(COARSE_SKIN_FTRV)$(PS2_GANADO),111)
$(error ACTOR_GANADO_PS2_STUMP needs ACTOR_TRANSACTION=1 COARSE_SKIN_FTRV=1 PS2_GANADO=1)
endif
ifeq ($(wildcard $(ACTOR_GANADO_PS2_STUMP_DIR)/ganado_ps2_stump_runtime.h),)
$(error ACTOR_GANADO_PS2_STUMP_DIR must contain the qualified ganado_ps2_stump_runtime.h)
endif
$(OBJDIR)/coarse_actor.o $(OBJDIR)/coarse_ganado_cast.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_GANADO_PS2_STUMP=1
$(OBJDIR)/coarse_ganado_cast.o: GAME_CPPFLAGS += -I$(ACTOR_GANADO_PS2_STUMP_DIR)
$(OBJDIR)/coarse_ganado_cast.o: $(ACTOR_GANADO_PS2_STUMP_DIR)/ganado_ps2_stump_runtime.h
endif
