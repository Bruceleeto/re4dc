# Options row lettering, 2026-10-12

Candidate in an isolated worktree based on `cf89ee249409307050076a1288ee8e4764633749`. Not committed or published.

## Change

With `RENDER_OPTION=1 OPTION_ROW_STYLE=1`, Frame Pacing and Rendering use letter
crops from the original English Options archive. The existing native UI submits
these as textured quads alongside AUDIO SETUP. Cap height, shadow, row spacing,
column alignment, fade, and yellow selection tint follow the original menu.
The larger QUICK KNIFE Q is scaled to match the other capitals. Half-texel crop
insets and glyph advances prevent neighbouring letters and padded shadows from
appearing in the composed labels.

This adds coordinates and drawing code only. No extracted pixels, new texture
package, game data, or changes to input/settings persistence are included. The
switch defaults to 0. Source message rendering remains as a 22-by-22 fallback
when the English texture bank is unavailable or fails its dimensions/format
checks. Only the English path was exercised in the runtime captures.

## Files

- `port/dreamcast/game/game30.mk`: default-off, validated build switch.
- `port/dreamcast/game/option_rows.cpp`: choose original-asset lettering or fallback.
- `port/dreamcast/game/option_rows_art.inc`: letter metadata, spacing, and quads.
- `port/dreamcast/game/ui_bridge.cpp`: bounded Options AUDIO SETUP drawing hook.

## Verification

- Fresh builds with `OPTION_ROW_STYLE=0` and `1`; no unresolved symbols.
- Off: program plus all six overlays match the control byte for byte. The control
  base d4bc5f45 differs from this worktree base only in README and Test 8 docs.
- On: ELF SHA-256 `8ed7d1f5d5151f9088a682028a077ad4ad50d1aafd6ebfce6507c4ee9fe17d81`.
- Ordinary boot/title/Options button fixture in Flycast, `ACT_CAP=0`, television
  480i. Pacing Smooth/Fast/Off and Rendering Standard/Fast/Quality all traversed;
  resolution requests were applied and returned to Quality. Captured original
  labels beside the new rows, including selection tint and help text.
- Private test image: both ISO namespaces, an independent raw reader, every
  staged payload, and preserved boot area checked successfully.
- Code size: +1,676 text bytes; data and BSS unchanged. Linked `_end` advances
  1,664 bytes. This is not a gameplay-memory or timing acceptance claim.

## Integration and limits

Enable `OPTION_ROW_STYLE=1` with the existing `RENDER_OPTION=1` recipe; use fresh
object/output directories. Apply the source-only patch after checking the target
tree for overlapping menu edits. There are no new disc payloads to convert.

The visuals and menu controls were checked in Flycast. Physical Dreamcast display
quality, non-English fallback, and a gameplay STRICT comparison remain untested.
The existing maintainer STRICT gate is still required before including this in
a test release. No frame-time or gameplay improvement is claimed.

The final work-check still reports the inherited private store (149 uncommitted
files; manifest missing 3, changed 6, new 55), as it did before this work. These
files were preserved. No source integration, commit, push, release, or SD install
of this menu candidate was performed.

## Local evidence and handoff

- Worktree: `/root/probe/codex-options-text-20261012/tree` in Ubuntu-24.04.
- Build: sibling `out/build-reviewed`; off identity: `out/off-identity-final.json`.
- Runtime: `D:/Flycast-Evidence/re4-dreamcast/codex-options-text-20261012/reviewed`.
- Handoff: `C:/Game Dev/Emulators/re4-options-text-20261012`.

The separate SD task installed the exact published Test 8 in E:/155. That release
does not contain this menu candidate.
