# Stage 1 PS2 effect recipes

`PS2_FX_STAGE1=1` extends the existing render-only haze/streak path. It defaults
to 0 and requires `PS2_FX_ROOMS=1`, `EFFECT_PS2_HAZE=1` and
`EFFECT_PS2_STREAK=1` or `2` (which already require native effect sprites).
The first group covers r102, r104, r105 and r107. It preserves the existing
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

The eight host tests cover endian-independent record decoding, populated lists
with missing data, truncated/invalid sequence tables, unsupported effect
semantics, convergent size recurrences, and the count estimate with smaller or
larger PS2 boxes. Private source archives and generated evidence stay outside Git.

## Remaining scope and validation

r109, r10f, r11e and r200 main PS2 EFF files remain explicitly held for variant
decoding. A parser failure is not evidence that a room has no effects. Later
decoded stage-1 rooms are outside this first group. Existing r10b comments quote
80/30 haze sprites; the extracted generator fields instead encode 21/10 per
emission. Its behavior is preserved pending a separate lifecycle/look audit.

This commit has source-audit and host-test evidence only. Integration still
requires knob-off image identity, H2 with the agreed allocation-field treatment
and identical decisions outside changed rooms, s30 trace heap/headroom, New Game,
GDI boot, TEX, LEON-GC/MCHECK, and requested stills from the changed rooms. All
logic traces must use `trace_lock.sh` with `TRACE_LOCK_OWNER=codex`. No runtime,
performance, visual, STRICT or hardware acceptance is implied by the static audit.