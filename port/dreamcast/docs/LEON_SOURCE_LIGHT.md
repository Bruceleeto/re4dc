# Leon source lighting

`LEON_SOURCE_LIGHT=1` lights the native Leon owner with the GX light set selected
by `LightSetModel`. The default is 0. `ACTOR_TRANSACTION=1` and
`LEON_NATIVE_PIPE=0` are required. The lean acquisition path currently keeps the
constant lighting record, so the unsupported combination is rejected by Make.

## Per-part normal transforms

Leon roles have different modelview rotations. The capture marks
`SourceLighting::normal_matrix[3]` with `1.0e30f`; this is an unused normal-matrix
translation component. Each role uses the inverse transpose of its own
modelview 3x3, after the existing skin normal transform.

`native_actor_fast.cpp::leon_part_normal` serves both the up-to-three-direction
fold in `build_lights` and the exact evaluator in `pass_lights_exact`.
`PreparedSourceLights` contains the selected lamps; it does not transform
normals. Both `ACTOR_EXACT_FAST=0` and `=1` pass the corrected normal basis to
`world_of`. The source lighting record, source matrices, palettes and gameplay
state are never changed.

The exact evaluator adds a 12-float (48-byte) matrix and one pointer on the
stack per meshlet lighting pass. It performs one matrix inversion per pass,
not per vertex. It adds no fields to actor records or caches and allocates no
heap or primitive-buffer data. The existing fast fold already had the same
12-float local matrix. A singular or non-finite normal basis keeps native
ownership with constant material color instead of using a stale normal matrix
or emitting non-finite colors. Such a fallback is not source-lighting parity.

## Material color proof for the admitted owner

The current admitted Leon scope has one proved material color: opaque white.
This is an existing source and certificate property, not an inference from the
r101 screenshot or a new restriction introduced by the lighting option.

- `include/model.h`: `cModelInfo::color[4]` and `colorWord` are the same RGBA
  union at offset 0x8c.
- `src/game/trans_lit.cpp::LightSetModel`: loads GX material from the first
  info's color before the owner transaction is reached.
- `src/game/trans.cpp::commonModelTrans`: an info with `be_flag & 0x20` loads
  its own color; after an override, an ordinary info restores the first info's
  color. Visibility filtering does not change these color rules.
- `coarse_actor_transaction.inc::actor_semantics` and its diagnostic twin
  require every info's `colorWord == 0xffffffff`, `invisible_factor == 1`, and
  the existing ordinary blend state. Model invisibility factors must also be
  1 and `alpha_omit` must be 255.
- `coarse_actor_material.inc::info` and `hand_info` independently require white
  RGBA and exact supported flags. Their flag certificate does not admit the
  per-info color-override bit 0x20. The existing checks also reject secondary
  colors and other unproved live material modifiers.

Consequently the captured white material is the correct source material for
every currently admitted role, including the certified hands. No per-part
material field, copy or broader certificate is needed for this lighting
change. The host test's colored-material cases verify evaluator arithmetic;
they do not extend the native owner's admission to tinted source infos.

If tinted roles are intentionally admitted later, the source-order color
selection, alpha/fade behavior, per-pass snapshot lifetime and material
certificate must be extended together. A single shared color cannot represent
that broader scope. That extension is not part of this change.

## Validation and acceptance

`python3 port/dreamcast/tests/test_leon_source_light.py` compiles the actual
actor implementation with host PVR stubs and runs all four combinations of
`LEON_SOURCE_LIGHT=0/1` and `ACTOR_EXACT_FAST=0/1`. It checks 3, 4 and 8 lamps;
rigid and skinned normals; rotation, nonuniform scale, shear and reflection;
material colors and TEV scale; and source-record immutability. Its normal
oracle uses independent double-precision elimination. It also checks the
fast-fold directions and unusable-matrix behavior. The unpatched prototype
fails the marked-role exact-lighting case. A separate Make parse test rejects
the conflicting lean acquisition option without compiling a game build.

These host checks do not establish runtime acceptance. Required gates remain:
knob-off image identity; STRICT and decision identity; LEON-GC/MCHECK; s30
heap-4; matched r100 house, r101 fight and r103 stills; and matched cost evidence.
Keep the same hand package, camera/window and enemy count in both cost arms.
Flycast/modelled hardware costs and fresh physical-console timings are distinct.

The standing villager baseline remains `CROWD_FLAT=1`. Leon lighting does not
change its policy. Villager per-vertex and one-direction candidates require a
separate default-0 comparison and the user's visual/cost decision.

## Landed hand-pack and reservation compatibility

The lighting path can be combined with the landed async `LEON_HAND_PACK`
implementation and `LEON_SKIN_SLOTS=1` (80 registry entries). Neither lighting
nor reservation changes hand loading, cache lifetime, or skin-acquisition
diagnostics. `ACTOR_SKIN_RESERVE=1` reserves at most 64 distinct source keys
atomically within the existing 64- or 80-entry registry; each actor retains its
existing 8/9-role lease limit. Defaults remain 0.

`test_actor_skin_reserve.py` runs the actual reservation, acquisition, readers
and source planner with both registry sizes and `MCHECK_LEONGC=0/1`, including
saturation, inert placeholders, rollback, source order and stale ownership.
The 65th distinct source-plan key is rejected with either registry size. These
host checks do not establish runtime compatibility or supersede frozen D5
evidence. Fresh matched runtime, trace, texture, movie and cost gates remain.
