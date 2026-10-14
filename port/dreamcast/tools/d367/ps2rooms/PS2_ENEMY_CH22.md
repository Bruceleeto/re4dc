# Qualified PS2 chapter 2-2 enemy lists

The default-off ROUTE_CH22 plus existing PS2_ENEMY_RULES settings select a
fresh-list full32 adapter. It covers r111/r112/r113/r11c, r11a, and the
remaining r100/r104 weapon flags. Every selected record retains all fields,
including HP, set/Character, emset number, positions/rotations, Guard_r and
reserved bytes. The helper allocates nothing and is never called on restored
save state or once per frame.

`ps2_enemy_ch22.py` shares only byte-layout, hashing and header emission
utilities with the CH23 extractor. Its room selection and qualification are
independent. A private per-room manifest must identify the source REL,
implementation and supporting evidence by path and SHA256, with status
`source-qualified`. Required `changed_indices`, `activation_indices` and
`populated_indices` must exactly match the full-record audit. Missing, stale,
pending or incomplete evidence refuses header output and preserves any prior
header. This establishes source qualification; target gameplay acceptance
still requires room and route testing.

The seven r11c additions are deliberately narrow: only list 1 rows 153..159
may change room identity, only from an all-zero 32-byte record to held id13
in r11c. No nonzero slot may be overwritten as a population change. Authored
held entries with no source activation must be documented as such in the
source evidence; no arbitrary spawn is invented for them.

The runtime checks every selected baseline byte and buffer extent before
copying any replacement. A mismatched or previously modified source is a
fatal caller error, not permission to use a partial table. Other list rows
remain untouched, including earlier PS2_ENEMY_LIST changes. The generator's
audit is private game data; do not commit or publish it or the generated
`ps2_enemy_ch22_data.inc`.

Synthetic validation:

```
python3 port/dreamcast/tools/d367/ps2rooms/test_ps2_enemy_ch22.py
```

The host test compiles the actual C++98 helper, checks the full copy and
seven additions, every-byte failure at the last selected record, short/null
buffers, repeat application and independent default-off guards. It also
checks source identity changes and per-room evidence rejection.

Remaining gates: final default-off loaded-image identity, target compilation,
all relevant enemy activations/room transitions, H2 STRICT with af blanked,
decisions outside changed rooms, s30 heap on the trace image, New Game, GDI,
TEX_CHECK, LEON-GC/MCHECK and stills. No target PASS follows from host tests.
