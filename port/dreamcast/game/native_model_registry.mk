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
NATIVE_MODEL_REGISTRY ?= 0
NATIVE_MODEL_REGISTRY_CENSUS ?= 0
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
ifndef NATIVE_MODEL_REGISTRY_DIR
$(error NATIVE_MODEL_REGISTRY_DIR must point at a private bundle from tools/d367/model_registry.py)
endif
ifeq ($(NATIVE_MODEL_REGISTRY)$(NATIVE_MODEL_REGISTRY_CENSUS),20)
$(error NATIVE_MODEL_REGISTRY=2 reports only through the census (NATIVE_MODEL_REGISTRY_CENSUS=1))
endif
NATIVE_MODEL_REGISTRY_FILES := $(addprefix $(NATIVE_MODEL_REGISTRY_DIR)/,native_model_registry.h \
  native_model_registry_facts.inc native_model_registry_roles.inc native_model_registry_blobs.inc)
$(OBJDIR)/coarse_actor.o: $(NATIVE_MODEL_REGISTRY_FILES)
# The entry gate: trans.cpp's re4dc_actor_transaction_candidate (platform/include/source_actor_owner_hooks.inc)
# also nominates registry ids, so their OT callbacks leave the FRONT_NATIVE fast return for the transaction.
$(OBJDIR)/src/game/trans.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY=$(NATIVE_MODEL_REGISTRY)
$(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_NATIVE_MODEL_REGISTRY=$(NATIVE_MODEL_REGISTRY)   -DRE4DC_NATIVE_MODEL_REGISTRY_CENSUS=$(NATIVE_MODEL_REGISTRY_CENSUS) -I$(NATIVE_MODEL_REGISTRY_DIR)
endif
