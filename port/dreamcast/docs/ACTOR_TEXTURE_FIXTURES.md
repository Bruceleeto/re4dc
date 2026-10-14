# Source actor texture fixtures

`tools/prepare_actor_texture_fixture.py` prepares the source model TPL images
needed by the existing registry-owner texture identity check. A generic
little-endian DRS has raw texels and does not satisfy that check, even when its
BIN geometry and its registry package match. This tool makes R4NREF records and
an NTR index with the existing `prepare_native_ui` converter helpers.

The input is the original big-endian source DRS **and** the currently staged
little-endian DRS. Their entire native payload must match after the existing
`le_mirror` normalization, before any edit. This intentionally refuses a staged
archive with a different source, changed motions, previous compaction, or a
previous NTR table. It does not replace the staged audio with the source audio.

Audited contracts:

| Archive | Model TPL ARC slots | Source consumers |
| --- | --- | --- |
| em18 | 6, 8, 0xF | `em18.cpp` modelInit / ModInfoMgr.create, including robe, hands and weapon |
| em3b | 5, 0xC | `em3b.cpp` two modelInit variants |
| em35 | 5, 0x9C | `em35.cpp` body/limbs and weak-point SetObj00 |
| em14 | Explicit top-level TPL list in the tool | Existing shared Ganado em10.cpp/em10_tmpl.cpp consumers; em14_set.cpp chooses model families |

The archive count grows by one NTR slot, original ordinal numbers remain stable,
and the embedded REL moves behind the index without modification. Every
nonselected ordinal is checked byte for byte, including all FCV, SEQ, EFF, BIN,
and all unselected TPL data. The full embedded REL is checked, not just its
header. The resulting container keeps every previously staged byte except the
first payload-table entry, and appends the new body. Nested sound bytes therefore
remain exactly those of the staged input. No motion streaming, effect compaction,
static-module stripping, source model edit, or actor simulation change is made.

Example (private inputs and outputs stay outside the source tree):

```sh
python3 port/dreamcast/tools/prepare_actor_texture_fixture.py \
  --source /private/source/em/em18.drs \
  --staged /private/staged/em/em18.drs \
  --output /private/new-fixture/em18
```

Stage the output DRS at `em/<name>.drs`. Stage each selected native texture at
`dc/tex/<first key character>/<key>.re4tex`; `fixture-report.json` contains source
and native hashes. Reuse an already staged package only after checking its
identity and native format. The output directory must be new. Original inputs
are never written.

2026-10-13 offline checks: em18 and em3b had 8 and 7 prepared model images,
respectively, with no retained model image. em35 had 10 images and retained all
83 FCV ordinals. Identity-table CRCs, all TPL-to-pixel offsets, native-record keys,
and emitted native package hashes were independently read back. Unknown actors,
wrong staged filenames, a changed FCV byte, a reused destination, and an already
prepared body were rejected. Fixture generation alone does not establish runtime
admission, visual acceptance, gameplay behavior, or physical-console performance.
