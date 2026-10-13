# Stage 1 PS2 effect recipes

`PS2_FX_STAGE1=1` extends the existing render-only haze/streak path. It defaults
to 0 and requires `PS2_FX_ROOMS=1`, `EFFECT_PS2_HAZE=1` and
`EFFECT_PS2_STREAK=1` or `2` (which already require native effect sprites).
The initial group covers r102, r104, r105 and r107; the next group below adds
qualified room-SST recipes through r11f and r200 sheet omissions. It preserves the existing
r106, r10a and WATER45_NATIVE r10b recipes.

## First group

| Room | GC haze emissions -> PS2 recipe | Additional draw omissions |
| --- | --- | --- |
| r102 | 59 x 1099.956 mm -> 10 x 1700 mm | One window streak; the other two signatures remain |
| r104 | 21 x 1887.222 mm -> 11 x 2500 mm | Its one window streak |
| r105 | Two area sets, each 51 x 1283.056 mm -> 10 x 2100 mm | Two Esp48/d0 mist generators |
| r107 | Global 40 x 1283.056 mm -> 11 x 2000 mm; area 3 has 71 x 1374.622 mm -> 9 x 2100 mm | Its one window streak and two Esp48/d0 mist generators |

Sizes in the table are source base sizes. Runtime scaling uses the ratio of
steady sizes from `Size_base * (1 + Size_plus / (1 - D_size_plus))`, along with
the source PS2 colour, alpha, box and near-fade parameters. The existing final
30 percent far fade is valid for all six PS2 records in this group.

The GC generators still emit and move every sprite. The existing pool-slot
stride and camera-box rejection approximate PS2 draw counts; they do not create
an exact PS2 live-sprite population. A PS2 box larger than the GC box does not
repopulate the missing outer volume. Expected subset counts for the six rows
are approximately 9.83, 10.50, 9.67, 9.67, 9.48 and 8.85 per source emission,
against PS2 source counts 10, 11, 10, 10, 11 and 9. These are static estimates,
not measured in-game counts or timing evidence.

r105 has two source haze generators with the same box. Its immutable start RGB
selects the recipe; current alpha and indoor fade state are not used as identity.
The SST path supplies no sequence colour override, and Espgen00's optional
colour multiplier changes alpha only. Streak copies are matched by room,
owner 0xd0, id 0, infinite life, additive blend, texture and delete distances.
The source audit rejects a cut signature that also belongs to another GC SST
record or remains in the PS2 records.

All added runtime fields, rows and predicates are guarded by
`RE4DC_PS2_FX_STAGE1`. There are no changes to effect creation, RNG, motion,
pool allocation, lighting, PS2 EFF loading or texture selection. The Makefile
integration belongs to the coordinating lane.

## Source audit

`tools/audit_ps2_fx_recipes.py` reads original extracted GC and PS2 EFF files,
checks both byte orders, sequence table counts and record spans, and pins file
and selected-record SHA-256 values. It reproduces the six haze recipes and
checks the three streak and two room-sheet omissions directly from binary
records. It does not decode effect textures.

```sh
python3 tools/audit_ps2_fx_recipes.py --cache /path/to/private/worldfx-cache --output /path/to/new-evidence.json
python3 -m unittest discover -s tools -p test_audit_ps2_fx_recipes.py
```

The twelve host tests cover endian-independent record decoding, populated lists
with missing data, truncated/invalid sequence tables, unsupported effect
semantics, convergent size recurrences, and the count estimate with smaller or
larger PS2 boxes. Private source archives and generated evidence stay outside Git.

## Remaining scope and validation

The apparent r109/r10f/r11e/r200 record-layout variants are resolved by the
source audit below. The second runtime group is listed below. Existing
r10b comments quote 80/30 haze sprites; the extracted generator fields instead
encode 21/10 per emission. Its behavior is preserved pending a separate
lifecycle/look audit.

This commit has source-audit and host-test evidence only. Integration still
requires knob-off image identity, H2 with the agreed allocation-field treatment
and identical decisions outside changed rooms, s30 trace heap/headroom, New Game,
GDI boot, TEX, LEON-GC/MCHECK, and requested stills from the changed rooms. All
logic traces must use `trace_lock.sh` with `TRACE_LOCK_OWNER=codex`. No runtime,
performance, visual, STRICT or hardware acceptance is implied by the static audit.
## Remaining source inventory and parser correction

All 47 cached PS2 EFF files pass the bounded v0xB sequence decoder. The original
survey's r109/r10f/r11e/r200 failures occur in texture parsing: `ofsTexId`,
`ofsTpl` and `ofsAnm` are zero, so the old dump reads the version word 0xB as an
11-entry texture table. Returning an empty table for a null optional-table
offset repairs those files without changing a sequence or record field.

An independent comparison against the original dump, with only that null-table
fix for the four recovered files, checked 10,055 records across 87 GC/PS2 EFF
files. Integer/byte fields match exactly and float fields match the original
dump's rounding. r109 has 3 records, r10f 180, r11e main EFF 78 (plus 2 in its
second EFF), and r200 101. The runtime does not load these PS2 files.

```sh
python3 tools/audit_ps2_fx_recipes.py --cache /path/to/private/worldfx-cache --scope inventory --output /path/to/new-inventory.json
```

The inventory preserves source order, byte offsets, record hashes, table
ownership, sequence number/area, and the separate SST/EST counts. A source count
is emissions per generator step, not proof of simultaneous particles.

| Room | Decoded PS2 haze | Qualified next mapping or unresolved difference |
| --- | --- | --- |
| r108 | None | Six GC SST Esp48 sheets, zero PS2 Esp48 |
| r109 | 10 x 2100 mm, global | Map GC 28 x 2900; 28 GC SST sheets removed; **not effect-free** |
| r10c | 7 x 2200 mm, global | Map GC 46 x 1283.056 |
| r10d | None | GC haze is EST; existing room-SST owner gate does not cover it |
| r10e | 12 x 2000 mm, global | Map GC 66 x 1283.056 |
| r10f | 10 x 1900 mm, global | Haze held: texture changes from GC 0x1e to PS2 0x1f; 15 GC SST streaks share one exclusive removed signature |
| r111 | 10 x 1900 mm, global | Map GC 53 x 1299.956; 53 SST sheets removed; four removed streaks are EST |
| r112 | 10 x 1900 mm, area 5 | GC haze was global; require source area qualification; only one removed streak is SST |
| r113 | 10 x 1900 mm, global | Map GC 51 x 1283.056; 53 SST sheets removed |
| r117 | None | PS2 retains three streak records; no blanket streak cut |
| r118 | 10 x 2000 mm, area 6 | No GC haze generator to reuse; five SST sheets removed |
| r119 | 10 x 2100 mm, global | Map GC 20 x 2700; 46 SST sheets removed |
| r11a | 10 x 2000 mm, global | Map GC 66 x 1283.056 |
| r11b | 10 x 2000 mm, global | GC source box admits only about 2.47 particles into PS2 box; stride cannot meet count |
| r11c | Global 10 x 2000; EST 10 x 2100 | Map global GC 21 x 2400.041; extra haze and 45 removed sheets are EST; seven removed sheets are SST |
| r11d | Global 10 x 2000; area 4 has 10 x 2100 | GC sets share range/RGB; stable source indoor-fade duration distinguishes them |
| r11e | 10 x 2000 mm, global | Map GC 66 x 1283.056 after the null-table parser correction |
| r11f | 11 x 1900 mm, global | Map GC 59 x 1299.956 |
| r200 | EST 12 x 2400 mm | Haze needs owner/call qualification; 14 SST sheets qualify for the second runtime group |

This inventory qualifies record layout and identifies bounded draw changes; it
does not accept PS2 area relocation, newly added effects, texture substitutions,
or a universal removal of GC particles. Runtime adoption remains separately
guarded and subject to the full integration gates above.

## Second runtime group

The same default-off knob adds twelve more room-SST haze rows and two removed
streak signatures. Sheet omissions now cover 25 room/texture selectors and 216
GC SST source records across r105/r107/r108/r109/r111/r113/r118/r119/r11c/r200.
Only owner 0xd0 Esp48 draws with the listed texture are omitted; EST effects
remain distinct. The source audit proves zero PS2 Esp48 records in those rooms.
The r10f streak signature removes all fifteen GC SST sources; r112 removes its
single matching SST source and leaves its separate EST source untouched.

r11d's global and area-4 haze share GC range and RGB. Immutable source
`Room_del_frame` values 30 and 0 distinguish those recipes. Runtime stores that
selector plus one, reserving zero as a wildcard for earlier rows. The existing
indoor fade counter remains unchanged.

| Room / source | PS2 emissions | Static expected draw subset |
| --- | ---: | ---: |
| r109 SST 01/0 | 10 | 12.83 |
| r10c SST 01/0 | 7 | 7.27 |
| r10e SST 06/0 | 12 | 10.68 |
| r111 SST 01/0 | 10 | 9.08 |
| r113 SST 00/0 | 10 | 12.67 |
| r119 SST 01/0 | 10 | 9.17 |
| r11a SST 04/0 | 10 | 10.43 |
| r11c SST 01/0 | 10 | 9.63 |
| r11d SST 01/0 | 10 | 11.92 |
| r11d SST 09/0 | 10 | 11.92 |
| r11e SST 00/0 | 10 | 10.43 |
| r11f SST 01/0 | 11 | 11.70 |

These retain the original integer pool-slot stride and box rejection; the
counts are approximations, not proof of PS2 population parity. Finer count
selection, r11b's underpopulated clipped box, r112's area relocation, new r118
and r11c haze, EST-owned changes and r10f's texture substitution remain separate
qualification work. In particular, this group does not treat r109/r113/r11d's
stride-one overpopulation as an exact match, or r11b's 2.47 admitted sprites as
a ten-sprite PS2 recipe.

```sh
python3 tools/audit_ps2_fx_recipes.py --cache /path/to/private/worldfx-cache --scope stage1-recipes --output /path/to/new-stage1-recipes.json
```

The twelve host tests include source duration disambiguation and rejection of
ambiguous/unrepresentable identities. No integration gates or in-game look,
performance, boot or heap acceptance are established by this commit.

## Qualified room-EST draws

Room setup installs main EFF 0 under owner 1 (`game.cpp`); `EstSet` and its
particles preserve that stamp, while `SstSet` explicitly stamps owner 0xd0.
The stage-1 knob now handles these owner-1 cases separately:

- r200 EST 2 haze: GC 53 emissions -> PS2 12, 2400 mm base, range 6000 mm,
  white alpha 60 and near fade 3500/500 mm. `R200Init` starts that exact EST with
  no model, position, rotation or optional colour override. Existing stride
  three estimates 11.82 particles; it does not establish population equality.
- r111 four and r112 one removed EST streak sources: the frozen copies have
  life one and are selected by texture/delete distances plus immutable start
  RGB. The source audit rejects matching direct sprites and retained PS2 rows.
- r11c EST 0a's 45 removed sheets: twelve cb, four 34, ten 33 and nineteen f6.
- r10d's two special EST15 records: exact texture/range pairs c6/500 and
  1e/1500. They are not camera fog recipes. Both are absent from the PS2 source.

No owner-1 source outside those signatures is omitted or retuned. In
particular, r11c's new PS2 EST 6 haze is a gate-opening effect with its own
lifecycle, and remains unimplemented rather than being made globally active.
The room scripts, source effect controllers, call counters and particles are
unchanged. Runtime/visual/heap/cost gates remain required.

## Guarded population selection

`PS2_FX_POPULATION=1` is a separate default-off render knob requiring
`PS2_FX_STAGE1=1`. It applies to the nineteen newly adopted haze sources plus
r11b; earlier r100/r101/r103/r106/r10a/r10b recipes retain their prior path.
The source audit proves generator 00 runs once (life 1, wait/random wait 0),
with permanent free-world particles. It rejects changed lifecycle, area,
texture or attachment assumptions.

The renderer scans the pool once per sprite pass, or lazily on the first haze
draw of a frame. It groups particles by recipe and immutable owner/core/call
identity, then evenly selects exactly the PS2 count from each complete,
unambiguous source group. Undersupplied groups select at most their live
count and report `PartialSource`; an overfull group reports `AmbiguousSource`
and keeps the prior draw path. Bounds are 2048 pool slots, 32 groups and 256
candidates. Overflow or unsupported runtime fields report a fallback. The
portable helper uses 2328 bytes of fixed state and performs no allocation,
RNG call, pool write or simulation update.

Selected centres scale locally by `PS2 range / GC range` about the camera;
the renderer leaves each source position, matrix, colour and effect work
unchanged. This fills larger PS2 boxes and avoids r11b's former 2.47-particle
clipped-volume limit. Source alpha rejection is deferred for selected haze
until the existing PS2 near/far/indoor/final-colour fades run at the remapped
depth. Frustum, projection and alpha can still reduce visible quads: the
selection count is a camera-box population, not an on-screen sprite promise.

`PS2FXPOP` logs initial/changed room counts and issue flags:
1 slot overflow, 2 group overflow, 4 candidate overflow, 8 unsupported counts
or runtime instance, 16 ambiguous overfull source group, 32 incomplete source
group. A nonzero issue is not a qualified full-population result.

Count selection does not claim complete PS2 trajectory or size-distribution
parity. Source motion and random-size samples remain GC, including r109's
random-size range 40 versus PS2 30. r10e/r113 retain the GC floor behavior
(-15200/900 versus PS2 zero); source indoor fade durations also remain GC
(r11b has zero versus PS2 30). These are explicit look residuals for stills
and any later narrowly scoped render work. r112's relocated area, newly
added r118/r11c EST haze and r10f's texture replacement remain separate.

```sh
python3 tools/audit_ps2_fx_recipes.py --cache /path/to/private/worldfx-cache --scope population --output /path/to/new-population-recipes.json
g++ -std=c++11 -O2 -Wall -Wextra -Werror tools/test_ps2_fx_population.cpp -o /tmp/test_ps2_fx_population
/tmp/test_ps2_fx_population
```

Host validation covers exhaustive source/target counts through 256, sparse
and interleaved pools, independent immutable identities, partial/ambiguous
groups, every bound, repeated builds and byte-identical source inputs.
Thirteen source-audit tests also reject lifecycle/trigger changes. No game
build, replay, still, heap or device-cost gate is established by those tests.

## Qualified area and texture changes

The population knob additionally covers r112 and r10f (22 haze recipes total):

- r112 keeps its 59 GC particles alive but selects ten haze draws only inside
  PS2 EAR area 5. This polygon is absent from the GC EAR. The renderer uses the
  exact PS2 float coordinates and the existing read-only `areaHitCheck_xz4`,
  player/camera selection, player Y offset, forced area bit and stopped-area
  behavior. It does not modify either EAR or the simulation area state. The
  PS2 source has zero indoor-fade duration, so this recipe omits GC indoor fade.
  `PS2FXPOP area=0/1` records activation changes as well as population changes.
- r10f selects ten of 48 source haze particles and remaps their range to
  4000 mm. Its selected native draw reads resident core texture 0x1f while the
  source remains texture 0x1e. Both GC textures and their PS2 counterparts have
  identical 128x128, centered, one-frame animation contracts. Source Tool_flg
  0x80 (GC RGB x4) is explicitly qualified; PS2 haze draws use their supplied
  RGBA without that multiplication. No texture upload or PS2 effect load is
  added, and source texture/flags/motion remain unchanged.

The source audit checks room-archive/EAR bounds, exact r112 polygon constants,
core texture table counts and all four animation contracts. Fifteen host tests
include truncated EAR, invalid table offsets and changed texture anchors.

```sh
python3 tools/audit_ps2_fx_recipes.py --cache /path/to/private/worldfx-cache --scope structural --gc-core /path/to/private/gc-core.EFF --ps2-core /path/to/private/ps2-core.EFF --output /path/to/new-structural-recipes.json
```

These are source qualifications. Runtime area transitions, missing-texture
fallback, projected sprite appearance, all gates and device cost still require
integration validation. r118's new haze and r11c's extra EST haze use the separately guarded addition path below.


## Separately guarded render additions

`PS2_FX_ADDITIONS=0` is the default. Value 1 requires `PS2_FX_POPULATION=1`,
`ESP_SPRITE_FAST=1`, and `COARSE_FX_SPRITES=1`. It adds ten private haze particles
for r118 area 6 and ten during r11c's gate EST 6. It runs only in the existing
coarse sprite render pass. No effect/controller pool, RNG, game script, archive,
texture registration, allocator, or source object is written.

The private state is 388 bytes. Its source-qualified recipe preserves the PS2
position/random-position ranges, velocity/random-velocity, random size, rotation,
rotation rate, growth recurrence, camera wrapping, near/far/indoor fades and RGBA.
Both use already resident GC core texture 0x1f. r11c's source seed is fixed
`0x1234567f`; r118 intentionally uses private seed `0x118c0def` because copying its
PS2 engine RNG state would cross the simulation boundary. This does not claim
that r118's particle arrangement or the complete EST6 effect group matches PS2.

The r118 GC and PS2 EAR geometry is identical. Activation reads the existing
area-6 state. Exit clears the private particles; reentry restarts their private
seed. The r11c activation reads at most 512 controller slots (the source CNS uses
256), requires the four immutable GC EST6 generator-2 record pointers, one
owner/core/call identity, expected 110/130-frame lives and equal ages. Missing,
duplicate, mixed-identity or divergent-age groups suppress the addition. The
source gate script deletes that group after 82 task sleeps; no task state or
controller counter is modified.

Private state resets on room/pool/controller-pool changes, the read-only
`re4dc_room4_state` generation (including same-room heap rebuild), area/gate exit,
clock rollback, or gate identity change. Repeated passes in one source frame do
not advance particles. r118 follows the source pause/stop/one-in-three slow-mode
rules; r11c follows the retained controller clock. Catch-up is bounded to eight
steps. Missing camera/indoor history is explicitly diagnostic; it is never
reported as trajectory parity. A nonzero diagnostic still needs review before
visual acceptance.

`PS2FXADD` logs activation/issue changes with private particle count, age and
submitted visible quads. Issue bits are `0x1` missing camera history, `0x2` clock
rollback, `0x4` catch-up limit, `0x100` controller bounds, `0x200` missing source
sequence/record, `0x400` duplicate or incompatible trigger identity, `0x800`
partial trigger group, `0x1000` invalid camera axes, `0x2000` unavailable texture
contract and `0x4000` invalid projection/viewport. Initial/changed submitted
counts are diagnostic examples, not persistent on-screen sprite counts.

The audit now reads generator wait randomness from the actual `0x128` field;
`0x10f` is unrelated. Existing population qualifications still pass after this
correction. Seventeen Python tests cover bounded source decoding, contract
changes and trigger/motion rejection. The C++ helper tests cover private seed
repeatability, exact population counts, source immutability, area exit/reentry,
positive/negative gate evidence, pause/slow mode, indoor fades, wrapping,
repeated passes, clock rollback/overflow and bounded catch-up.

```sh
python3 tools/audit_ps2_fx_recipes.py --cache /path/to/private/worldfx-cache --scope additions --gc-core /path/to/private/gc-core.EFF --ps2-core /path/to/private/ps2-core.EFF --output /path/to/new-additions-recipes.json
```

These host results do not establish compilation of the game, trigger timing,
matching stills, heap safety, replay identity or device cost. Those remain the
coordinated integration gates, including positive/negative r118 area and r11c
gate observations, fresh load, reentry, New Game, and additions-off identity.

## Stationary r104 sprites

`PS2_FX_STAGE1=1` also maps three stationary common-sprite records while the
PS2 haze draw mask is active. GC SST 0/4 maps to PS2 SST 5/2 (texture 08,
18840.164 square to 34300 square, RGBA 255/255/205/140 to 255/255/195/50);
GC 0/5 maps to PS2 5/3 (texture 1f, unchanged 58542.766 square, alpha 225 to
200); GC 4/0 maps to PS2 4/1 (texture e9, height 5562.702 to 6262.702,
RGBA 135/135/125/165 to 195/195/185/70). The last pair retains area 1.

The `static` audit scope normalizes all numeric record lanes to little endian
and requires every byte outside dimensions and RGBA to match. It also proves
unique live signatures, stationary permanent lifetimes, unchanged near fades,
matching core animation contracts and no room texture overrides. Runtime
selection requires unchanged source dimensions, position, initial/current
colour, source owner, texture, type of common sprite and world parent.

Corners expand around the source texture anchor in view space before clipping,
including e9's noncentral Cy=1/128 anchor. The source matrix and sprite remain
unchanged. Coarse bounds use the target dimensions, and colour follows the
existing final-colour truncation then near-fade order. Core GC pixels remain
resident; this does not assert identical GC/PS2 texture pixels. Host tests cover
noncentral anchors and raw-field rejection. Fresh runtime stills, knob-off,
STRICT, heap, New Game and cost gates remain required.

## Surviving r117 puzzle trails

`PS2_FX_ADDITIONS=1` with the PS2 streak draw mask maps the three surviving
Esp0a EST 1/2/3 recipes. GC red/blue use Type1 rim-lit anchors; green generates
50 permanent Type0 copies. PS2 uses Type0 for all three, resident core texture
13, size 1400, local z step -500, growth 0.04999998957, colour alpha 60 with
0.90000003576 decay, and tool RGB/alpha scale 4. The first two copies retain
alpha 60 because source CommonMove skips decay at life zero. Exactly 27
private points remain before alpha falls below 4; those points then undergo
normal projection, near fades, final colour and visible-quad submission.

The read-only group scan requires one exact red/blue anchor or all 50 distinct
green source ranks with one call/core/model/parent identity and current model
serial. Missing, duplicated or merged groups keep their prior draw path and
report an issue. Source ghosts are omitted only after their group qualifies;
original Esp0a updates and any original render-time allocations are unchanged.
Each render pass rebuilds ownership; no trail state survives room changes or
reentry. Parent transforms remain live, so source puzzle-object rotation
controls beam direction. Native quads use the resident GC texture 13; PS2 pixel
identity is not claimed.

The `puzzle` audit scope pins both EFFs and core animations, validates every
interpreted recipe field and rejects any raw-byte difference outside the
explicit changed fields. It records PS2 Vec2.x=10 for red/green as unused by
current EspSeqSet/cEsp0a::SetFreeWork. GC EST1/2/3 index1 generator-1 effects
remain unchanged and are separately unresolved. Host tests cover exact trail
length, first-frame decay, ranks, partial/duplicate/identity failures and reset.
Runtime acceptance still needs puzzle activation, dial rotation, deactivation,
reentry, negative/paused state, comparison stills, STRICT and fill/cost evidence.
`PS2FXPUZZLE` logs source group counts, private point count, submitted quads and
qualification issues; these are not runtime performance measurements.
