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
# ACTOR_PL08=1 (native scene coverage, 2026-10-04; default 0): the no-jacket Leon (pl08.drs, NINE source infos) on the
#              ACTOR_TRANSACTION owner path (coarse_actor_owner_pl08.inc). Plans only when the 0x108 role rows
#              (actor_material_records_pl08*.inc, generated from the original pl08.drs) prove all nine infos; otherwise the
#              whole model keeps the source path. Role capacity 8 -> 9 and owner runs 21 -> 22 for every TU (layouts with
#              0 unchanged). ACTOR_PL08_DIR = private dir with leon_pl08_runtime.h; the disc must carry the pl08 atlas
#              dc/tex/7/7506e95f-68cf2211.re4tex (else the texture lease declines and the source path draws).
# ACTOR_PL08_PACK=1 (2026-10-04; default 0; needs ACTOR_PL08=1 and NATIVE_STATIC=1): the three pl08-only immutable chunks
#              (roles 0 / 1 / 8, 33,916 B) are not compiled in. They are read from dc/native/pl08/leon_pl08.re4cp
#              (tools/d367/pl08_pack.py from the frozen leon_pl08_runtime.h) into one heap-4 room cell only while the
#              bound player archive is pl08 (ReadPlayerData file 0x5A), validated against actor_pl08_pack_identity.inc
#              (every field and array hash) and preflighted before anything publishes; retired at room leave, unpublished
#              by a bind away from pl08 (coarse_actor_pl08_pack.inc, actor_pl08_pack_check.inc). Missing or refused:
#              pl08 keeps the whole source path. ACTOR_PL08_DIR is not used.
ACTOR_PL08_PACK ?= 0
ACTOR_PL08 ?= 0
ifeq ($(filter $(ACTOR_PL08),0 1),)
$(error ACTOR_PL08 must be 0 or 1)
endif
ifeq ($(filter $(ACTOR_PL08_PACK),0 1),)
$(error ACTOR_PL08_PACK must be 0 or 1)
endif
ifeq ($(ACTOR_PL08)$(ACTOR_PL08_PACK),01)
$(error ACTOR_PL08_PACK=1 needs ACTOR_PL08=1)
endif
ifeq ($(ACTOR_PL08),1)
ifneq ($(ACTOR_TRANSACTION),1)
$(error ACTOR_PL08 acts on the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
ifeq ($(ACTOR_PL08_PACK),0)
ifndef ACTOR_PL08_DIR
$(error ACTOR_PL08=1 needs ACTOR_PL08_DIR (the private dir with leon_pl08_runtime.h))
endif
endif
GAME_CPPFLAGS += -DRE4DC_ACTOR_PL08=1
PLATFORM_CPPFLAGS += -DRE4DC_ACTOR_PL08=1
ifeq ($(ACTOR_PL08_PACK),0)
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -I$(ACTOR_PL08_DIR)
$(OBJDIR)/coarse_actor.o: $(ACTOR_PL08_DIR)/leon_pl08_runtime.h coarse_actor_owner_pl08.inc actor_material_records_pl08.inc     actor_material_records_pl08_roles.inc actor_material_records_pl08_blobs.inc
else
ifneq ($(NATIVE_STATIC),1)
$(error ACTOR_PL08_PACK=1 loads into the native static room storage (NATIVE_STATIC=1))
endif
GAME_CPPFLAGS += -DRE4DC_ACTOR_PL08_PACK=1
$(OBJDIR)/coarse_actor.o: coarse_actor_owner_pl08.inc coarse_actor_pl08_pack.inc actor_pl08_pack_check.inc actor_pl08_pack_identity.inc     actor_material_records_pl08.inc actor_material_records_pl08_roles.inc actor_material_records_pl08_blobs.inc
endif
endif
ifeq ($(ACTOR_GANADO_SOURCE_LIGHT),1)
ifneq ($(ACTOR_TRANSACTION),1)
$(error ACTOR_GANADO_SOURCE_LIGHT acts on the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_GANADO_SOURCE_LIGHT=1
endif
# SS_CERT=1 (native scene, 2026-10-04; default 0; needs ACTOR_TRANSACTION=1 and SUBSCREEN=1): room archive
#              certificates survive the sub screen memory swap (actor_swap_park.inc). At open the records of every
#              archive in the 3 MiB window leave the live tables; frees inside the window while it is swapped (heap 12)
#              do not touch them; at close they are published again under new serials only when their bytes hash as
#              at open and nothing retired, replaced or overlapped them meanwhile. Otherwise the source path draws them,
#              as without the knob (first-visit r101: the cow after the entry inventory).
SS_CERT ?= 0
ifeq ($(filter $(SS_CERT),0 1),)
$(error SS_CERT must be 0 or 1)
endif
ifeq ($(SS_CERT),1)
ifneq ($(ACTOR_TRANSACTION)$(SUBSCREEN),11)
$(error SS_CERT=1 needs ACTOR_TRANSACTION=1 and SUBSCREEN=1)
endif
$(OBJDIR)/coarse_actor.o $(OBJDIR)/sscrn_bridge.o: GAME_CPPFLAGS += -DRE4DC_SS_CERT=1
$(OBJDIR)/coarse_actor.o: actor_swap_park.inc
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
# CROWD_READOPT_MEMO=1 (perf-20261004 candidate 3; render only, exact; needs CROWD_READOPT): a re-adoption proof that
#              failed with its asset current is not run again until the lifetime epoch moves or the info's pData /
#              tpl_addr / TPL descriptor word / asset current() change (actor_lifetime.inc). The r100 h-fight s03
#              corpse (id 0x12) failed it every drawn tick (~0.76 hw ms) and then drew through the source path anyway.
CROWD_READOPT_MEMO ?= 0
ifeq ($(filter $(CROWD_READOPT_MEMO),0 1),)
$(error CROWD_READOPT_MEMO must be 0 or 1)
endif
ifeq ($(CROWD_READOPT_MEMO)$(CROWD_READOPT),10)
$(error CROWD_READOPT_MEMO=1 needs CROWD_READOPT=1 or 2)
endif
# ACTOR_BIND_REUSE=1 (perf-20261004 candidate 11, the 2026-10-04 actor-preparation handover's POC; render only, exact):
#              a Ganado's palette build reuses its plan's owner binding (role search, source BINs) within the same
#              actor transaction when the token, the lifetime serial, the Ganado slot, the live info list and the
#              lifetime binding (read-only) all still match; the finite-matrix scan runs live; any miss runs the full
#              bind (coarse_actor_owner_ganado.inc). =2 check build: the full bind decides, "ABR" lines count hits whose
#              reuse would have differed (bad must be 0).
ACTOR_BIND_REUSE ?= 0
ifeq ($(filter $(ACTOR_BIND_REUSE),0 1 2),)
$(error ACTOR_BIND_REUSE must be 0, 1 or 2)
endif
ifneq ($(ACTOR_BIND_REUSE),0)
ifneq ($(ACTOR_TRANSACTION)$(COARSE_GANADO_CAST),11)
$(error ACTOR_BIND_REUSE acts on the ACTOR_TRANSACTION Ganado cast owner path (ACTOR_TRANSACTION=1 COARSE_GANADO_CAST=1))
endif
$(OBJDIR)/coarse_actor.o $(OBJDIR)/coarse_ganado.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_BIND_REUSE=$(ACTOR_BIND_REUSE)
endif
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
ifeq ($(CROWD_READOPT_MEMO),1)
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_CROWD_READOPT_MEMO=1
endif
# The census and the cull check read native_ui.cpp's emitted-triangle total (otherwise a silent missing-symbol stub).
ifneq ($(CROWD_CENSUS)$(filter 2,$(CROWD_CULL)),0)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_CROWD_OUTPUT=1
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_CROWD_OUTPUT=1
endif
endif

# CROWD_INVIS_SKIP=1 (lane iv 2026-10-05; render only, exact; default 0): a Ganado the player cannot see gets no
#              drawing-side work after the game's own view test. ModelTrans (trans.cpp), once AddOt has queued the
#              Ganado (everything that test writes is kept), asks re4dc_invis_decide (coarse_actor_owner_ganado.inc)
#              before the screen matrices. An owner-path Ganado (its last draw admitted the cast plan) is skipped
#              when the crowd policy would cull it anyway (CROWD_FOGSKIP's root test, CROWD_CULL's pregate balls with
#              the fog far plane) or when every ball lies behind the near plane. A Ganado whose last draw the owner
#              plan declined (source path) is skipped when every per-bone sphere of its source mesh (all drawn infos,
#              built once from vtxOrig / weights / bind matrices) lies outside one screen edge or the near plane.
#              A skipped Ganado keeps commonScreenMat's texture animation / UV scroll advance; an owner-path one
#              loses its OT entry (as the screen-matrix failure path), a source-path one keeps it and its ModelRender
#              replays only the texture-object cache step (TPL / cTexChg) the source draw would have taken. The view
#              is the next Render's: projection from pG->Cam.ProjMat, viewport and fogged far as the previous Render
#              saw them (the fog only while LightEnv predicts the same value). Never with shadow lights, morphs,
#              render-to-texture or foot shadows (needs FX_LEAN=1).
#              =2 (check build): nothing is skipped; each Ganado the knob would skip must emit 0 triangles in its
#              ModelRender and take the predicted path under the predicted projection / viewport / fog ("INVIS2"
#              lines: violations and mismatches must stay 0).
CROWD_INVIS_SKIP ?= 0
ifeq ($(filter $(CROWD_INVIS_SKIP),0 1 2),)
$(error CROWD_INVIS_SKIP must be 0, 1 or 2)
endif
ifneq ($(CROWD_INVIS_SKIP),0)
ifneq ($(CROWD_CULL)$(FX_LEAN)$(ACTOR_FOG_GATE)$(SCENERY_GATE),1111)
$(error CROWD_INVIS_SKIP needs CROWD_CULL=1 FX_LEAN=1 ACTOR_FOG_GATE=1 SCENERY_GATE=1)
endif
$(OBJDIR)/src/game/trans.o $(OBJDIR)/coarse_actor.o $(OBJDIR)/coarse_ganado.o: GAME_CPPFLAGS += -DRE4DC_CROWD_INVIS_SKIP=$(CROWD_INVIS_SKIP)
ifeq ($(CROWD_INVIS_SKIP),2)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_CROWD_OUTPUT=1
endif
endif

# ACTOR_EARLY_COARSE=1: labelled four-role Ganado coarse path, selected before
# source preparation only through the existing complete source/material proof.
# A next-frame texture ticket lives in the existing source frame ledger. Other
# actors keep the original complete source/owner route. No default/play adoption.
ACTOR_EARLY_COARSE ?= 0
ACTOR_EARLY_COARSE_DIAG ?= 0
ifeq ($(filter $(ACTOR_EARLY_COARSE),0 1),)
$(error ACTOR_EARLY_COARSE must be 0 or 1)
endif
ifeq ($(filter $(ACTOR_EARLY_COARSE_DIAG),0 1),)
$(error ACTOR_EARLY_COARSE_DIAG must be 0 or 1)
endif
ifeq ($(ACTOR_EARLY_COARSE),1)
ifneq ($(ACTOR_TRANSACTION)$(COARSE_SOURCE_ACTORS)$(COARSE_GANADO_CAST)$(COARSE_SKIN_FTRV)$(COARSE_ONE_SUBMIT),11111)
$(error ACTOR_EARLY_COARSE needs the existing transaction owner, source ledger, cast, FTRV and grouped submit)
endif
GAME_CPPFLAGS += -DRE4DC_ACTOR_EARLY_COARSE=1 -DRE4DC_ACTOR_EARLY_COARSE_DIAG=$(ACTOR_EARLY_COARSE_DIAG)
PLATFORM_CPPFLAGS += -DRE4DC_ACTOR_EARLY_COARSE=1 -DRE4DC_ACTOR_EARLY_COARSE_DIAG=$(ACTOR_EARLY_COARSE_DIAG)
endif
