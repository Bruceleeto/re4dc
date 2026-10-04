# D367 lane crowd (2026-09-30): Ganado draw cost and crowd draw policy on the ACTOR_TRANSACTION owner path
# (coarse_actor_transaction.inc, coarse_actor_owner_ganado.inc). All default off: no -D is added and the
# default image is unchanged. Render only: every Ganado still exists, moves, animates its skeleton and collides
# exactly as before (logic trace STRICT); these knobs only decide whether its cast mesh is skinned and submitted.
#
# CROWD_CULL=1 (exact, look unchanged): a Ganado whose every visible chunk is provably off-screen (COARSE_PREGATE's
#              per-bone balls against the actor path's culling planes: a screen edge, or a far plane at the fog
#              gate's cull depth, the fogged View far, which the GC clips) is not
#              acquired: no bones, palettes, texture pins, preflight or submission. re4dc_actor_submit would have
#              emitted nothing for it, so the image is the same. Applies only after the owner path admitted the
#              actor (plan + semantics), so no Ganado changes path. =2 check build: nothing is skipped; each actor the
#              cull would skip must emit no triangle over both passes ("CROWDCULL" lines: violations must stay 0).
# CROWD_CENSUS=1 (diagnostic): one "CROWDC" line per frame in the UI-frame window CROWD_CENSUS_FROM..TO: Ganados
#              seen by the owner path, admitted, culled off-screen, drawn, drawn with no output, distance bands.
# CROWD_DRAW_MAX=N (look change, user's call; -1 = off): at most N Ganados drawn a frame, the nearest by the previous
#              frame's camera distances among those the cull keeps; the rest are not drawn (still simulated).
# CROWD_DRAW_M=D (look change, user's call; 0 = off): Ganados farther than D metres from the camera are not drawn.
# CROWD_READOPT=1 (fix; look change vs today's play build): a Ganado info with no live material-lifetime record is
#              proved again (the load-time proof) when its actor plans, so it stops falling back to the source path.
#              =1 Ganados only; =2 Ganados and Leon (Leon then also leaves the lit source path for the flat owner path).
# CROWD_FOGSKIP=1 (look change, user's call): a Ganado whose root is more than 2.5 m beyond the fogged View far
#              (where the GC clips) is not drawn; the actor path otherwise emits some of them fully fogged.
# CROWD_FAR_M=D (look change, user's call; 0 = off): a Ganado farther than D metres draws the far tier (the external
#              cast's lighter v4-fit level, ganado_far_runtime.h in the asset dir: tools/d367/crowd/far_header.py).
# CROWD_NEAR_MAX=N (look change, user's call; -1 = off): only the N nearest Ganados (previous frame's distances among
#              those drawn) draw the near tier; the rest draw the far tier. Either knob sets RE4DC_CROWD_FAR.
# CROWD_FREEZE_AT=N (look sheets only): the CPU stops in game frame N's first owner draw; frame N-1 stays on screen.
#              CROWD_FREEZE_HOLD=S: resume after S seconds (0 = never); CROWD_FREEZE_AT2=M: hold again at frame M.
#
# ACTOR_APPEARANCE_ALIAS=1 (native scene coverage, 2026-10-03; default 0): the owner path also admits the Ganado
#              (module, model type) pairs listed in actor_appearance_aliases.inc, which tools/native_appearance_alias.py
#              generates only for types whose EmXXSet loads byte-identical source entries (every model slot mot[0..20]
#              and every reachable role BIN/TPL) to an already certified appearance: em12 types 0/3/4 = the em15
#              type 0/3/4 casts (r100, r103). Every role/owner/material/semantics proof still runs per draw; gore,
#              unknown hands, fades and other states still fall back to the source path. Render only.
#              Every enabled row is rendered with the owner path's Ganado lighting (see ACTOR_GANADO_SOURCE_LIGHT).
#              =2 (native scene coverage extension, 2026-10-03): the same check, reading actor_appearance_aliases_ext.inc
#              (the same generator, --knob 2: em12 0/3/4, em13 0/1/3/4, em16 3/4, em17 0/1/3, em10 0/3/4; em16 11 and
#              em10 1 are held out because their sack accessory differs from the certified type's).
# ACTOR_GANADO_SOURCE_LIGHT=1 (native look fidelity, 2026-10-03; default 0; look change vs today's play build, the
#              user's call): every Ganado drawn by the owner path (appearances 0..4, Leon excluded) is lit with the
#              source's own GX lighting (LightSetModel's lights / channel / ambient / material, nrm = part.mv^-T,
#              TEV scale gxCsScale) through the existing lit kernel instead of the approved flat constant colour.
#              A Ganado whose roles disagree on matrix or material colour, or that uses vertex colour sources,
#              falls back to the source path (ATD 26). Specular is still omitted, as in the flat look. Render only.
#              (Hunk copied from the sup-native-scene worker's helper; with NATIVE_MODEL_REGISTRY it also lights
#              the registry descriptors: every non-Leon plan.)
ACTOR_APPEARANCE_ALIAS ?= 0
ACTOR_GANADO_SOURCE_LIGHT ?= 0
ifeq ($(filter $(ACTOR_APPEARANCE_ALIAS),0 1 2),)
$(error ACTOR_APPEARANCE_ALIAS must be 0, 1 or 2)
endif
ifeq ($(filter $(ACTOR_GANADO_SOURCE_LIGHT),0 1),)
$(error ACTOR_GANADO_SOURCE_LIGHT must be 0 or 1)
endif
ifeq ($(ACTOR_APPEARANCE_ALIAS),1)
ifneq ($(ACTOR_TRANSACTION),1)
$(error ACTOR_APPEARANCE_ALIAS acts on the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_APPEARANCE_ALIAS=1
endif
ifeq ($(ACTOR_APPEARANCE_ALIAS),2)
ifneq ($(ACTOR_TRANSACTION),1)
$(error ACTOR_APPEARANCE_ALIAS acts on the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_APPEARANCE_ALIAS=2
endif
ifeq ($(ACTOR_GANADO_SOURCE_LIGHT),1)
ifneq ($(ACTOR_TRANSACTION),1)
$(error ACTOR_GANADO_SOURCE_LIGHT acts on the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_GANADO_SOURCE_LIGHT=1
endif
CROWD_CULL ?= 0
CROWD_CENSUS ?= 0
CROWD_CENSUS_FROM ?= 900
CROWD_CENSUS_TO ?= 1380
CROWD_DRAW_MAX ?= -1
CROWD_DRAW_M ?= 0
CROWD_FREEZE_AT ?= 0
CROWD_FREEZE_AT2 ?= 0
CROWD_FREEZE_HOLD ?= 0
CROWD_READOPT ?= 0
CROWD_FOGSKIP ?= 0
CROWD_FAR_M ?= 0
CROWD_NEAR_MAX ?= -1
CROWD_KNOBS := $(filter-out 0,$(CROWD_CULL) $(CROWD_CENSUS) $(CROWD_DRAW_M) $(CROWD_FREEZE_AT) $(CROWD_READOPT) $(CROWD_FOGSKIP) $(CROWD_FAR_M)) $(filter-out -1,$(CROWD_DRAW_MAX) $(CROWD_NEAR_MAX))
ifneq ($(strip $(CROWD_KNOBS)),)
ifneq ($(ACTOR_TRANSACTION),1)
$(error CROWD_* knobs act on the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
ifneq ($(COARSE_PREGATE)$(COARSE_GATE_ONCE),11)
$(error CROWD_* knobs reuse the cast Ganado pregate (COARSE_PREGATE=1 COARSE_GATE_ONCE=1))
endif
ifeq ($(filter $(CROWD_CULL),0 1 2),)
$(error CROWD_CULL must be 0, 1 or 2)
endif
CROWD_DEFS := -DRE4DC_CROWD_CULL=$(CROWD_CULL) -DRE4DC_CROWD_CENSUS=$(CROWD_CENSUS) \
  -DRE4DC_CROWD_CENSUS_FROM=$(CROWD_CENSUS_FROM) -DRE4DC_CROWD_CENSUS_TO=$(CROWD_CENSUS_TO) \
  -DRE4DC_CROWD_DRAW_MAX=$(CROWD_DRAW_MAX) -DRE4DC_CROWD_DRAW_M=$(CROWD_DRAW_M) -DRE4DC_CROWD_FREEZE_AT=$(CROWD_FREEZE_AT) -DRE4DC_CROWD_FREEZE_AT2=$(CROWD_FREEZE_AT2) -DRE4DC_CROWD_FREEZE_HOLD=$(CROWD_FREEZE_HOLD) -DRE4DC_CROWD_READOPT=$(CROWD_READOPT) -DRE4DC_CROWD_FOGSKIP=$(CROWD_FOGSKIP) -DRE4DC_CROWD=1 \
  -DRE4DC_CROWD_FAR_M=$(CROWD_FAR_M) -DRE4DC_CROWD_NEAR_MAX=$(CROWD_NEAR_MAX)
ifneq ($(filter-out 0,$(CROWD_FAR_M))$(filter-out -1,$(CROWD_NEAR_MAX)),)
CROWD_DEFS += -DRE4DC_CROWD_FAR=1
endif
$(OBJDIR)/coarse_actor.o $(OBJDIR)/coarse_ganado.o: GAME_CPPFLAGS += $(CROWD_DEFS)
# The census and the cull check read native_ui.cpp's emitted-triangle total (otherwise a silent missing-symbol stub).
ifneq ($(CROWD_CENSUS)$(filter 2,$(CROWD_CULL)),0)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_CROWD_OUTPUT=1
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_CROWD_OUTPUT=1
endif
endif
