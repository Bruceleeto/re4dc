# D367 diagnostics

`OTHER_PROFILE` is a trace diagnostic with a default value of zero. Its disabled
form emits no diagnostic compiler definition, marker instructions or snapshot
storage. It is not added to a play or release recipe.

With `OTHER_PROFILE=1`, the existing main, Trans/Render and coarse draw boundaries
emit trace-visible NOP markers. Actor membership uses guarded Trans snapshots;
render callbacks compare saved addresses without walking the live actor list.
The marker consumer accounts instrumentation separately. Enabling this option
changes code layout and storage and requires its own runtime qualification.

The associated tools are:

- [OTHER accounting](../tools/d367/other/README.md): disjoint function self-cost
  accounting, replay export validation, and explicit benchmark-phase ownership.
- [Actor switch-pair verifier](../tools/d367/actorplan/verify_pair.py): compares
  resolved knobs, compiler definitions, affected object code and relocations,
  and loadable image bytes. It rejects unchanged affected code even if an
  unrelated image change exists. Other resolved differences are reported for
  review; this tool does not establish timing or asset/source equivalence.
- [World atlas census](../tools/d367/ps2world/atlas/README.md): material, texture
  payload, VQ and UV-repeat accounting from explicit converted inputs.
- [World part coalescing diagnostics](../tools/d367/ps2world/coalesce/README.md):
  read-only candidate census and independent package invariants.

For the actor verifier, put SH-4 binutils on PATH or pass
`--tool-prefix /path/to/bin/sh-elf-`. Use fresh build directories with
`resolved-knobs.txt`, complete `build.log`, affected object files and the ELF.

For a diagnostics landing, compare fresh builds of the intended base and the
diagnostics branch under the same unmodified recipe. Confirm the effective
default is zero, compare `objcopy -R .stack -O binary` output, `_end`, and every
overlay, and check for missing symbols. Full ELF bytes can differ because of
debug paths. Preserve the build inputs and evidence separately.

The 2026-10-16 extraction was checked against base
`58cbad284c3d5c3de02f9c94f94354aeafd0a9e1` with fresh full `test15/t15-build.sh rP`
builds and `SOURCE_DATE_EPOCH=1760000000`. The loadable image was byte-identical
(3,352,720 bytes, SHA-256
`137aa57403b8600801a617639426af095a4acf7472799445923247a314acfa0b`), all six
overlays matched, `_end` remained `0x8c4210d8`, and neither build had missing
symbols. No diagnostic compiler definition or symbol was present. After
normalizing only build and checkout paths, the sole resolved-knob difference
was the newly declared `OTHER_PROFILE=0`. The recipe adaptation changed only
where its post-build checks find the private output directory.

This is current default-off build evidence. Earlier enabled-marker runtime
checks used a preceding stack; they do not qualify `OTHER_PROFILE=1` on this
base. Retained-input host checks establish tool portability and arithmetic,
not fresh game, emulator or console acceptance.

Raw traces, converted packages, plans, source arrays and generated measured
reports are inputs or local outputs; none are included with these tools.
Model estimates, host invariants, emulator captures and console measurements
establish different results and must be labeled accordingly.
