# D367 generic native models (2026-10-03): NATIVE_MODEL_REGISTRY on the ACTOR_TRANSACTION owner path
# (coarse_actor_owner_registry.inc; registry branches in coarse_actor_transaction.inc, coarse_actor_material.inc,
# actor_lifetime.inc, actor_material_records.inc, coarse_actor_geometry_once.inc). Default 0: no -D is added and the
# image is unchanged. Render only: the source simulation, skeleton, collision, AI, events and animation cadence run as
# before; an admitted actor's presentation is drawn from a validated pack instead of the source preparation.
#
# NATIVE_MODEL_REGISTRY=1: actors whose every source info the archive adoption proof binds to one descriptor's exact
#              source BIN + TPL rows, whose skeleton has the descriptor's bone count / parents / rest rotations and
#              that pass the transaction (layout, semantics, immutable chunk proof, the material certificate's
#              registry branch, the shared leases and preflight) draw the descriptor's chunks. Anything else keeps
#              the whole source path. Unregistered model ids are rejected by an O(1) id mask.
# NATIVE_MODEL_REGISTRY=2: compare mode: the same admission plus the palette build into a scratch buffer; the actor
#              keeps the source path (no lease, no native TA submission); "would" counts what =1 would draw.
#              Requires NATIVE_MODEL_REGISTRY_CENSUS=1 (its only output is the census).
# NATIVE_MODEL_REGISTRY_CENSUS (diagnostic, default 0; never in a cost or production image): "NMRD" / "NMRU" / "NMRS"
#              lines (every 600 UI frames and at room changes): per descriptor planned / admitted / would / declined
#              by reason and the largest accepted rest-inverse deviation, and the scene census of every model whose
#              first OT pass reaches the transaction (native, crowd-skip, declined, registry-declined, absent).
#              With 0 none of the census storage, counters or the per-actor scene walk is compiled.
# NATIVE_MODEL_REGISTRY_DIR: a private bundle from tools/d367/model_registry.py (native_model_registry.h, the three
#              source-row includes, tex/). Stage its tex/*.re4tex on the disc (dc/tex/<crc>-<fnv>.re4tex).
# NATIVE_MODEL_REGISTRY_PACK (default 0: the compiled provider above, kept as a diagnostic):
#   =1: no registry data is compiled in (no NATIVE_MODEL_REGISTRY_DIR; no geometry or identity arrays in the ELF).
#       At every room enter (ui_bridge.cpp re4dc_room_enter, before the room's archives load) the room's package
#       dc/native/r<room>/registry.re4nmr (tools/d367/model_registry.py --package-room) is read into one heap-4 room
#       cell (re4dc_static_alloc: the room storage and its 80 KiB source reserve) and validated completely (header
#       and payload hashes, section table, every count, offset, alignment, capacity, identifier and cross reference,
#       duplicate geometry, finite binds and weights, the chunk preflight and the skin build) before anything is
#       published. Its identity rows then join the material / lifetime rows for that room generation
#       (actor_material_records.inc). Any failure publishes nothing: every actor keeps the whole source path. At
#       room leave (re4dc_room_leave, before the heap-4 close) the rows, the adopted records using them, the registry
#       bindings and the immutable chunk proofs of its IDs are retired and the cell is freed. Needs NATIVE_STATIC=1.
# NATIVE_MODEL_REGISTRY_TX (default 0; needs NATIVE_MODEL_REGISTRY=1 and NATIVE_MODEL_REGISTRY_PACK=1; render only):
#              one registry actor transaction proves each thing once. The decisions are the =0 decisions:
#   - the palette build reuses the plan's registry_bind proof (shape, revision, role rows, skeleton parents / rest
#     inverse / finite matrices) of the SAME re4dc_actor_transaction_draw call (a one-use token: call serial, model,
#     binding slot, room generation) instead of running it a second time; anything else runs the whole proof;
#   - the pass that acquired the actor keeps the actor_semantics verdict it got before actor_acquire (a later pass,
#     another OT group, proves it again);
#   - the skeleton's finite test skips the rest inverses (the bind comparison already fails NaN / inf: no
#     -ffinite-math-only in this image) and tests the current matrices and the palette outputs with an exact integer
#     reduction of coarse_finite;
#   - a registry appearance's role-row scans visit only the info's set role bits (info_current's first clause);
#   - the registry plan is built in the transaction's plan (no second zeroed plan, no whole-plan copy).
#   Audit (plan -> palettes / semantics, one call): actor_plan_layout (writes the plan), actor_semantics (reads),
#   actor_acquire: re4dc_bind_actor_frame (native frame scratch), texture / workspace / palette-arena / prim-tail
#   leases, the palette build, re4dc_actor_skin_acquire, actor_source_lighting (reads GX state), preflight; then
#   re4dc_actor_transaction_choose (the ledger's presentation choice, not its membership). None runs source code or
#   writes cModel / cParts / cModelInfo, the lifetime records or the room rows; the room leave clears the token.
#   =2: compare build: every reused or reduced verdict is also computed the =0 way, the =0 verdict decides, and
#   "NMRTX" lines (every 600 frames and at room leave) count uses and differences (bind_bad, skeleton_bad, finite_bad,
#   semantics_bad, roles_bad must be 0).
# NATIVE_MODEL_REGISTRY_PALBOUND (default 0; needs NATIVE_MODEL_REGISTRY_TX=1; render only): the registry palette
#              build tests its used bone matrices T (|t| < 2^125, finite) instead of every palette output element when
#              every weight of the descriptor lies in [0, 1] (checked once per room generation at the skin build):
#              each output element is a sum of at most 4 products w*t (coarse_skin_sh4.S groups: FTRV of (w0,w1,w2,0)
#              through used-bone rows; one-bone entries copy), so it is finite. Otherwise the whole output test runs.
#              The verdict equals the output test's. =2: compare build (the output test decides; "NMRPB" lines count
#              bounded chunks whose outputs are not finite, which must be 0, and bound misses that ran the test).
#              The source's own per-info palettes (trans.cpp MakeWeightPalette + re4dc_skin_defer_lazy) are NOT
#              reusable here: the pack's weight groups differ from the source BIN's (generic-models/wcmp.py).
NATIVE_MODEL_REGISTRY_PALBOUND ?= 0
ifeq ($(filter $(NATIVE_MODEL_REGISTRY_PALBOUND),0 1 2),)
$(error NATIVE_MODEL_REGISTRY_PALBOUND must be 0, 1 or 2)
endif
ifneq ($(NATIVE_MODEL_REGISTRY_PALBOUND),0)
ifneq ($(NATIVE_MODEL_REGISTRY_TX),1)
$(error NATIVE_MODEL_REGISTRY_PALBOUND needs NATIVE_MODEL_REGISTRY_TX=1)
endif
endif
NATIVE_MODEL_REGISTRY ?= 0
NATIVE_MODEL_REGISTRY_CENSUS ?= 0
NATIVE_MODEL_REGISTRY_PACK ?= 0
NATIVE_MODEL_REGISTRY_TX ?= 0
ifeq ($(filter $(NATIVE_MODEL_REGISTRY_TX),0 1 2),)
$(error NATIVE_MODEL_REGISTRY_TX must be 0, 1 or 2)
endif
ifneq ($(NATIVE_MODEL_REGISTRY_TX),0)
ifneq ($(NATIVE_MODEL_REGISTRY)$(NATIVE_MODEL_REGISTRY_PACK),11)
$(error NATIVE_MODEL_REGISTRY_TX needs NATIVE_MODEL_REGISTRY=1 and NATIVE_MODEL_REGISTRY_PACK=1)
endif
endif
ifeq ($(filter $(NATIVE_MODEL_REGISTRY_PACK),0 1),)
$(error NATIVE_MODEL_REGISTRY_PACK must be 0 or 1)
endif
ifeq ($(NATIVE_MODEL_REGISTRY),0)
ifneq ($(NATIVE_MODEL_REGISTRY_PACK),0)
$(error NATIVE_MODEL_REGISTRY_PACK needs NATIVE_MODEL_REGISTRY=1 or 2)
endif
endif
ifeq ($(filter $(NATIVE_MODEL_REGISTRY_CENSUS),0 1),)
$(error NATIVE_MODEL_REGISTRY_CENSUS must be 0 or 1)
endif
ifeq ($(NATIVE_MODEL_REGISTRY),0)
ifneq ($(NATIVE_MODEL_REGISTRY_CENSUS),0)
$(error NATIVE_MODEL_REGISTRY_CENSUS needs NATIVE_MODEL_REGISTRY=1 or 2)
endif
endif
ifneq ($(NATIVE_MODEL_REGISTRY),0)
ifeq ($(filter $(NATIVE_MODEL_REGISTRY),1 2),)
$(error NATIVE_MODEL_REGISTRY must be 0, 1 or 2)
endif
ifneq ($(ACTOR_TRANSACTION),1)
$(error NATIVE_MODEL_REGISTRY extends the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
ifneq ($(COARSE_SKIN_FTRV),1)
$(error NATIVE_MODEL_REGISTRY builds its palettes with COARSE_SKIN_FTRV=1)
endif
ifeq ($(NATIVE_MODEL_REGISTRY_PACK),0)
ifndef NATIVE_MODEL_REGISTRY_DIR
$(error NATIVE_MODEL_REGISTRY_DIR must point at a private bundle from tools/d367/model_registry.py)
endif
else
ifneq ($(NATIVE_STATIC),1)
$(error NATIVE_MODEL_REGISTRY_PACK=1 loads into the native static room storage (NATIVE_STATIC=1))
endif
ifdef NATIVE_MODEL_REGISTRY_DIR
$(error NATIVE_MODEL_REGISTRY_PACK=1 compiles no bundle: unset NATIVE_MODEL_REGISTRY_DIR and stage the room package)
endif
endif
ifeq ($(NATIVE_MODEL_REGISTRY)$(NATIVE_MODEL_REGISTRY_CENSUS),20)
$(error NATIVE_MODEL_REGISTRY=2 reports only through the census (NATIVE_MODEL_REGISTRY_CENSUS=1))
endif
# The entry gate: trans.cpp's re4dc_actor_transaction_candidate (platform/include/source_actor_owner_hooks.inc)
# also nominates registry ids, so their OT callbacks leave the FRONT_NATIVE fast return for the transaction.
$(OBJDIR)/src/game/trans.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY=$(NATIVE_MODEL_REGISTRY)
ifeq ($(NATIVE_MODEL_REGISTRY_PACK),0)
NATIVE_MODEL_REGISTRY_FILES := $(addprefix $(NATIVE_MODEL_REGISTRY_DIR)/,native_model_registry.h \
  native_model_registry_facts.inc native_model_registry_roles.inc native_model_registry_blobs.inc)
$(OBJDIR)/coarse_actor.o: $(NATIVE_MODEL_REGISTRY_FILES)
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY=$(NATIVE_MODEL_REGISTRY)   -DRE4DC_NATIVE_MODEL_REGISTRY_CENSUS=$(NATIVE_MODEL_REGISTRY_CENSUS) -I$(NATIVE_MODEL_REGISTRY_DIR)
else
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY=$(NATIVE_MODEL_REGISTRY)   -DRE4DC_NATIVE_MODEL_REGISTRY_CENSUS=$(NATIVE_MODEL_REGISTRY_CENSUS) -DRE4DC_NATIVE_MODEL_REGISTRY_PACK=1
ifneq ($(NATIVE_MODEL_REGISTRY_TX),0)
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY_TX=$(NATIVE_MODEL_REGISTRY_TX)
endif
ifneq ($(NATIVE_MODEL_REGISTRY_PALBOUND),0)
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY_PALBOUND=$(NATIVE_MODEL_REGISTRY_PALBOUND)
endif
# The room hooks: re4dc_room_enter opens and re4dc_room_leave retires the room's package (coarse_actor_registry_pack.inc).
$(OBJDIR)/ui_bridge.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY_PACK=1
endif
endif

# ACTOR_PROOF_LEAN (default 0; needs ACTOR_TRANSACTION=1; render only; independent of the registry knobs): one actor
# transaction proves each thing once, for Leon, the Ganado cast and registry plans alike. The decisions are the =0
# decisions:
#   - the pass that acquired the actor in the SAME re4dc_actor_transaction_draw call keeps its pre-acquire
#     actor_semantics verdict and the modelviews actor_acquire computed, while the lifetime serial (life::next: adopt,
#     retire, revoke, forget, stream pending, binding refresh) has not moved since that verdict; a later pass (Leon's
#     second OT group) and any lifetime change run the whole proof (coarse_actor_transaction.inc has the audit);
#   - the material certificate looks up each role's current row once per evaluation: the owner proof is implied by the
#     unique current row, and the Ganado run loop and source material reuse it (coarse_actor_material.inc).
#   Role rows are held per plan info slot (sizeof Re4dcActorPlan::info), not a fixed role count.
#   =2: compare build: the =0 proofs also run and decide; "APL" lines (every 600 frames) count every reuse and how often
#   the =0 result differed (semantics_bad, mv_bad, owner_bad, rows_bad, materials_bad must be 0). Not with
#   NATIVE_MODEL_REGISTRY_TX=2 (a separate compare build).
ACTOR_PROOF_LEAN ?= 0
ifeq ($(filter $(ACTOR_PROOF_LEAN),0 1 2),)
$(error ACTOR_PROOF_LEAN must be 0, 1 or 2)
endif
ifneq ($(ACTOR_PROOF_LEAN),0)
ifneq ($(ACTOR_TRANSACTION),1)
$(error ACTOR_PROOF_LEAN acts on the ACTOR_TRANSACTION owner path (ACTOR_TRANSACTION=1))
endif
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_PROOF_LEAN=$(ACTOR_PROOF_LEAN)
endif

# ACTOR_MATERIAL_RECORD (default 0; private prototype; needs ACTOR_PROOF_LEAN=1; render only): the material
# certificate keeps, per model (16 records, 44 bytes each), what is fixed while the lifetime epoch is unchanged: each
# role's lifetime record slot and unique current row and info()'s archive verdict (TPL descriptors / headers / R4xREF
# / CLUT and ModelPart header bytes inside the owner archives) with its required bits. Every adopt / retire / revoke /
# forget / room rows publish or retire / swap park or unpark moves the epoch (life::changed); a hit also needs each
# plan info in the model's list and info_current() true for its row now. Everything else (model and info modifiers,
# ModelData header, shapes, gxCsScale, frame owner, registry model / runs, source materials, plan materials,
# capability) is evaluated every time. coarse_actor_material.inc has the audit. The decisions are the =0 decisions.
#   =2: compare build: the whole certificate also runs and decides; "AMR" lines (every 600 frames) count evaluations,
#   hits, stores and hits whose result differed (bad must be 0).
ACTOR_MATERIAL_RECORD ?= 0
ifeq ($(filter $(ACTOR_MATERIAL_RECORD),0 1 2),)
$(error ACTOR_MATERIAL_RECORD must be 0, 1 or 2)
endif
ifneq ($(ACTOR_MATERIAL_RECORD),0)
ifneq ($(ACTOR_PROOF_LEAN),1)
$(error ACTOR_MATERIAL_RECORD extends the ACTOR_PROOF_LEAN=1 certificate (ACTOR_PROOF_LEAN=1))
endif
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_MATERIAL_RECORD=$(ACTOR_MATERIAL_RECORD)
endif

# LEON_NATIVE_PIPE (default 0; lane ln 2026-10-05 experiment; needs ACTOR_TRANSACTION=1 and COARSE_ONE_SUBMIT=1; render
# only, exact): Leon (pl00) through the owner transaction with what it repeats done once (coarse_actor_leon_pipe.inc,
# platform/include/native_actor_leon_pipe.inc): one owner_leon_bind per pass-1 call with its finite test as one exponent
# sweep; the plan and the record's fixed parts kept per binding; actor_semantics' fixed terms (immutable chunk proofs,
# counts, bytes, run order) proved once per plan, its per-frame terms and the live certificate in every pass; the
# palette finite scan replaced by a sufficient bound on the bone matrices (outside it the scan decides); the run
# preflight's fixed terms proved once per plan by the full preflight, then its per-frame terms per material (pass 1's
# submission does not repeat acquisition's); one_chunk takes the lease's registry entry instead of one_qualifies; the
# hair's material changes inside one store-queue window (native_ui.cpp re4dc_leon_direct_switch: the same header
# words and counters as closing and reopening). Same leases, allocations, ledger choices, kernels, inputs and order:
# the TA receives the same words. Not with the transaction diagnostic / census / compare builds.
LEON_NATIVE_PIPE ?= 0
ifeq ($(filter $(LEON_NATIVE_PIPE),0 1),)
$(error LEON_NATIVE_PIPE must be 0 or 1)
endif
ifneq ($(LEON_NATIVE_PIPE),0)
ifneq ($(ACTOR_TRANSACTION)$(COARSE_ONE_SUBMIT),11)
$(error LEON_NATIVE_PIPE acts on the ACTOR_TRANSACTION owner path with COARSE_ONE_SUBMIT=1)
endif
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_LEON_NATIVE_PIPE=$(LEON_NATIVE_PIPE)
$(OBJDIR)/platform/native_actor_fast.o $(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_LEON_NATIVE_PIPE=$(LEON_NATIVE_PIPE)
endif
