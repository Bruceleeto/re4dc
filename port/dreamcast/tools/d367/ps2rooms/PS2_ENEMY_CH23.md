# CH23 PS2 enemy-list adoption

`ps2_enemy_ch23.py` audits complete 32-byte enemy records for r10f, r11d,
r11e, r11f and r200 in emleon01, plus r200 in emleon02. It converts the GC
big-endian input with the same field layout as `le_mirror.py`, then compares
every field against PS2 little-endian records. This includes HP, all position
and rotation components, `emset_no`, and the four reserved bytes. Zero-ID
records are retained. Rows outside the selected rooms are never patched.

The private generated header holds baseline bytes for every selected row and
replacement bytes for changed rows. No extracted data belongs in Git.

## Generation

```sh
python3 -B port/dreamcast/tools/d367/ps2rooms/ps2_enemy_ch23.py \
  --gc-dir /private/gc/etc --ps2-dir /private/ps2 \
  --ps2-rel /private/ps2/ps2_st1_3.rel \
  --qualification /private/ch23-activation.json \
  --audit-json /private/ch23-enemy-audit.json \
  --header /private/include/ps2_enemy_ch23_data.inc
```

Omit `--header` for an audit before room activation is qualified. A requested
header is refused with exit 2 when qualification is incomplete. An existing
header is left intact on refusal; callers must honor the nonzero exit status
and must not mistake that old artifact for newly qualified output.

The qualification JSON uses schema `re4dc-ps2-enemy-activation-v1`:

```json
{
  "schema": "re4dc-ps2-enemy-activation-v1",
  "source_rel": {"path": "/private/ps2/ps2_st1_3.rel", "sha256": "..."},
  "rooms": {
    "r10f": {
      "status": "source-qualified",
      "held_indices": [46, 47, 48],
      "implementation": {"path": "/tree/src/st1/r10f.cpp", "sha256": "..."},
      "evidence": [{"path": "/private/activation-evidence.json", "sha256": "..."}]
    },
    "r11d": {
      "status": "source-qualified",
      "held_indices": [221, 226, 229, 231, 232, 245],
      "implementation": {"path": "/tree/src/st1/r11d.cpp", "sha256": "..."},
      "evidence": [{"path": "/private/activation-evidence.json", "sha256": "..."}]
    }
  }
}
```

Qualification is an explicit source-review result. The generator checks file
hashes and exact changed-alive index coverage; it cannot establish that room
code implements source behavior. Evidence must establish the callbacks,
trigger areas, save bits, cohort behavior, and activation conditions. Changed
implementation or evidence files require renewed qualification. Runtime and
route acceptance remain separate from source qualification.

## Integration contract

Build `game/platform/ps2_enemy_ch23.cpp` only with both
`RE4DC_ROUTE_CH23=1` and `RE4DC_PS2_ENEMY_RULES=1`, and add the private generated
header's directory to that translation unit's include path. Either guard off
produces no helper implementation and requires no private header. There is
no additional gameplay knob.

Include `platform/include/ps2_enemy_ch23.h` in `stage.cpp`. Call
`re4dc_ps2EnemyListCh23(pG->em_list_no, pG->Em_list, sizeof(pG->Em_list))`
inside the existing successful fresh `DvdReadN` branch of `readEmList`, next
to the existing `RE4DC_PS2_ENEMY_LIST` hook, under the same two guards.
Never call it during per-room initialization, restored/save-state processing,
or room re-entry that reuses a loaded list.

Return values are 1 for validated/adopted selected rows, 0 for a list outside
the CH23 set, -1 for invalid buffer, and -2 for baseline mismatch. A negative
result includes exact diagnostics and leaves the entire buffer unchanged.
The caller must explicitly reject the failed required adoption. It must not
silently continue with GC rules after the room code starts using PS2 rules.

The helper validates every selected baseline row before any copy, then copies
complete changed records. It performs no allocation, disc reads, or per-frame
work. Existing list caching owns restored/death/save state, unchanged.

## Verification

```sh
python3 -B port/dreamcast/tools/d367/ps2rooms/test_ps2_enemy_ch23.py
```

The tests use synthetic records only. The host C++98 harness verifies complete
copies, preservation of other rows, unchanged r200 handling, rejection of all
32 byte offsets in the last validated row without partial mutation, invalid
buffers, repeated/adopted-state refusal, and both default-off guards. Python
checks layout/endian conversion, every semantic field, zero-ID preservation,
source alignment, size constraints, and stale/incomplete qualification.
These checks do not establish Dreamcast execution or route completion.
