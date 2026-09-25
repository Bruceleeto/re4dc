# Dreamcast button glyphs and VMU presentation — implementation plan

Date: 25 September 2026

## Objective

Replace player-facing GameCube button artwork with a consistent generated Dreamcast set, replace GameCube memory-card illustrations and terminology with VMU presentation, and supply a proper Dreamcast save-file icon. Include an optional VMU LCD emblem as a separate deliverable.

Preserve RE4's input behavior, gameplay, menu actions, QTE timing and save compatibility. This task delivers the plan; image generation, runtime changes and game validation are the implementation phases below.

## Isolated workspace

- Worktree: `/root/probe/re4-dreamcast-ui-vmu-plan-20260925` in WSL Ubuntu-24.04.
- Branch: `plan/dreamcast-ui-vmu`.
- Base: `4594c518b77ab9e002bde59551cd7a1008fb2a2d`, the active checkout's committed HEAD when this worktree was created.
- Authoritative plan: `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/docs/DREAMCAST_UI_VMU_PLAN.md`.
- Windows reading copy: `C:\Game Dev\Emulators\re4-research\dreamcast-ui-vmu-plan-20260925\DREAMCAST_UI_VMU_PLAN.md`.

The active checkout is `/root/work/re4-dreamcast`, currently on `cgate` with inherited edits. Its dirty overlay was not copied into this worktree. A clean HEAD checkout is sufficient for planning but does not reproduce the currently running game. Before implementation testing, snapshot the required runtime overlay into a separate owned build tree and record its provenance; never stage or alter the shared overlay.

Use a private sibling output directory, `/root/probe/re4-dreamcast-ui-vmu-assets-20260925`, for extracted sheets, generated art, converted textures, contact sheets and candidate staging. Use separate object, disc and evidence directories. The final promotion is an explicit UI-only patch plus asset manifest. The current gameplay/performance build remains independent throughout development.

## 1. Findings from the existing code

All source locations below were inspected in the isolated worktree at the stated base.

| Finding | Evidence and consequence |
|---|---|
| Standard Dreamcast A/B/X/Y, Start and triggers produce the corresponding GameCube inputs | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/pad.cpp:147`. Replace their visual identities while retaining the input mapping. |
| Standard-pad D-pad behavior depends on game context | The same file, lines 56–68 and 169–195: LOOK uses the D-pad as C-stick, a clean down tap/release produces Z; ZOOM uses up/down for zoom; NATIVE preserves ordinary D-pad input. Z/C-stick artwork needs context-specific prompts. |
| Other controllers can expose a second stick and C/Z | The same file, lines 51–55 and 160–168. Resolve prompts against the active controller profile; do not show unsupported controls on a stock pad. |
| Action prompts use cockpit sprites | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/src/game/act_btn.cpp:101` and `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/src/game/cockpit.cpp:468`: `ActionButton::move` selects sprite IDs. These are a separate route from text glyphs. |
| Text has its own font and native glyph-cache path | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/src/game/mes.cpp:195,467,477,1131` and `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/native_ui.cpp:1644`. CI4 source font cells populate a native PAL4 atlas; a normal texture-package override alone may not affect them. |
| Save-screen assets have a distinct archive/layout | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/src/game/card.cpp:71,207,3428`: `ss/cmn/save_?.dat`, CardID textures and save/load layouts. The declared initial path is `save_j.dat`; verify language selection before inventorying variants. |
| A safe image-override pipeline already exists | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tools/ui_overrides.py:1` and `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tools/d367/README.md:50`. It replaces native texture packages under their original source identities, checks dimensions and re-encodes the original for provenance. Reuse it. |
| Native VMU saves already contain a placeholder icon | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/vmu_store.cpp:45,225` and `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tools/vmusave.py:192,205`. Both writers currently generate the same placeholder. Replace both through one asset definition. |
| The adapter selects a real VMU, preferring A1 | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/vmu_store.cpp:66`. It can fall back to other ports/slots. Avoid hard-coded A1 labels once another VMU is selected. |
| The game refuses to format a VMU | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/card.cpp:577`. Presentation must agree with that behavior. |
| Reported GameCube capacity is synthetic | The same file, line 585: `CARDFreeBlocks` converts estimated save capacity into virtual GC units. These values must not simply be relabeled as VMU blocks. |
| VMU LCD status already has a writer | `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/dbgslot_bridge.cpp:126`. An optional emblem must share ownership with diagnostics/status and respect orientation and Maple retry behavior. |

Exact texture indices, glyph codes, UV rectangles and localized message IDs remain to be inventoried. No unverified replacement indices are prescribed by this plan.

## 2. Deliverables and formats

| Deliverable | Contents | Output contract |
|---|---|---|
| Dreamcast control set | A, B, X, Y, L, R, Start; analog stick and directions; D-pad and directions; press/hold/tap/repeated-press and combination decorations | Transparent editable masters, individual PNGs and a labeled review sheet; final sprites/cells retain the discovered source dimensions, baseline and layout bounds |
| On-screen VMU artwork | Recognizable VMU silhouette for save/load dialogs, plus inserted/missing, busy and error treatments where the existing UI uses them | Exact-size replacements for the relevant UI textures; retain state timing and alpha behavior |
| Native save-file icon | A small RE4/Dreamcast emblem visible in the Dreamcast file browser | One static 32×32, 4-bit indexed frame: 512 pixel bytes plus a 16-entry ARGB4444 palette, packed into the existing VMS header/package |
| Optional VMU LCD emblem | A separately designed readable RE4 mark for the physical VMU display | 48×32, 1-bit image: 192 bytes; correct bit order and physical orientation |
| UI wording | VMU terminology and accurate instructions for save/load/error states | Targeted localized message replacements preserving control codes and menu return behavior |
| Reproducibility package | Source mapping, prompts, selected artwork hashes, packing settings, review captures and test results | Versioned manifests/specifications and a narrowly scoped patch; private extracted/derived game art remains outside Git |

Native VMU package format: [KOS package reference](https://kos-docs.dreamcast.wiki/group__vmu__pkg.html), [package fields and ARGB4444 palette](https://kos-docs.dreamcast.wiki/structvmu__pkg__t.html). LCD format: [KOS VMU LCD API](https://cadcdev.sourceforge.net/docs/kos-2.0.0/vmu_8h.html).

Start with one static save icon and no eyecatch. The existing package already reserves one 512-byte icon, so replacing it should add no VMU blocks for an otherwise identical payload. Animation and eyecatch imagery can be considered later only with their storage cost shown. The on-screen VMU picture, VMS save icon and LCD bitmap are three distinct encodings.

## 3. Visual brief and generation workflow

### Art direction

Use a Dreamcast controller reference for physical button identity and RE4 screenshots for scale, contrast and visual tone. Face buttons should form one coherent family: consistent circular caps, bold readable letters, restrained depth, clean alpha edges and reference-matched color accents. L/R should read as triggers; Start should be visibly distinct. Letter/shape recognition must work without relying on color.

The VMU illustration should have a recognizable screen, directional pad and lower controls. Favor a simple silhouette that survives reduction. The 32×32 save icon should use a strong RE4 emblem or monogram, with a small Dreamcast identity cue if it remains legible; a detailed miniature VMU is an alternate concept for review. The LCD version should be designed for monochrome pixels independently.

### Production steps

1. Gather clean source crops and verify a physical Dreamcast reference. Record the actual display sizes before requesting artwork.
2. Use the image-generation tool to create two coherent style candidates for the control set and two VMU/emblem candidates, with actual transparent backgrounds. These are comparison candidates, not four separate shipped styles.
3. Review the family together and at the real in-game size. Select one style, then use that selected reference consistently for remaining glyphs and states.
4. Correct any malformed letter, duplicate/missing control, inconsistent outline or unreadable small feature. Produce individually named assets so atlas placement does not depend on the generator's sheet spacing.
5. Export through a deterministic asset-packaging step: exact dimensions, palette conversion, alpha treatment, format encoding and source-identity mapping. The accepted image bytes are fixed inputs to builds; builds never regenerate art from a prompt.
6. Deliver a contact sheet with original and candidate images at 1× and enlarged views, plus mockups of a HUD prompt, a combined QTE, a menu footer and a save dialog. Review in context before promoting the candidate.

### Generation brief — control artwork

> Create a coherent set of game UI button glyphs for a Dreamcast version of Resident Evil 4. Use the supplied Dreamcast controller reference for control identity and the supplied UI crop for scale and contrast. Include A, B, X, Y, L, R, START, analog stick and D-pad direction variants. Transparent background, front-facing symbols, bold exact lettering, consistent outlines and lighting, restrained depth, readable when reduced to the supplied display dimensions. Preserve the identity of each control; avoid GameCube button shapes, invented buttons and decorative text. Keep each glyph separated for individual export.

### Generation brief — VMU artwork

> Create a clean front-facing Dreamcast VMU UI illustration matching the selected button-glyph style. Preserve the recognizable screen, directional pad and lower-button layout. Transparent background, strong silhouette, restrained detail and readable shape at the supplied small display size. Also propose a simple RE4-themed save emblem suitable for a 32×32 icon with at most 16 colors. The tiny emblem must remain identifiable without small body text.

The generator provides artwork. Native 4-bit VMS packing and 1-bit LCD packing are performed and validated by the conversion tools.

## 4. Control mapping and coverage

Map logical actions to the input the current port actually accepts, then select the glyph. Avoid a global texture substitution that turns every Z or C-stick picture into the same misleading icon.

| Existing control reference | Standard Dreamcast presentation | Verification |
|---|---|---|
| A/B/X/Y | Corresponding Dreamcast face-button glyph | Check every supported control configuration, confirm/cancel convention and combined prompt |
| L/R | Dreamcast trigger glyph | Preserve any distinction between hold, press and combination cues |
| Start | Dreamcast Start glyph | Pause/options and title prompt follow the existing action |
| Main analog stick | Dreamcast analog-stick glyph and direction | Movement, rotation and any stick QTE |
| D-pad in menus/events | Dreamcast D-pad glyph | Ordinary NATIVE-context input |
| C-stick look in free movement | D-pad direction/look cue | LOOK-context mapping on a stock pad |
| C-stick zoom | D-pad up/down zoom cue | ZOOM context; preserve left/right fine-pan behavior |
| Z/map | D-pad-down tap/release cue in the applicable gameplay context | Verify the existing clean-tap rule and map close/back path before choosing text |
| Dual-stick or extra-button profile | A presentation matching that profile | Do not apply stock-pad Z/C-stick replacements indiscriminately |

Inventory and test title/options, inventory and item rotation, map/files, merchant, pickup/open/climb/kick interactions, reload/knife/aiming, scope/binoculars, escape and combination QTEs, death/retry, save/load confirmations and tutorials. Include controller diagrams and baked-in instruction artwork. If a controller diagram shares a texture with other UI art, replace its region while preserving unrelated pixels and UV layout.

The action dispatchers, button tests and QTE timing remain unchanged. If a requested instruction has no matching action on a stock pad, record that mapping issue explicitly before presenting a glyph as if it worked.

## 5. Memory-card to VMU wording

Audit message resources and baked texture labels by message ID/context, including every shipped language. Preserve control words, substitutions, waits, choices, return codes and menu selection order. When replacement text has a different length, preserve message-completion and input-enable timing where those drive state transitions; use a presentation substitution rather than altering the authoritative message progression when necessary. English is the first visual proof; coverage of remaining shipped locales stays explicit until completed.

Suggested wording, adjusted to each actual UI state:

| State | Proposed player-facing text |
|---|---|
| Device absent | No VMU was found. Insert a VMU to save your game. |
| During a write | Saving. Do not remove the VMU or turn off the console. |
| Insufficient capacity | There is not enough free space on the VMU. |
| Overwrite confirmation | Overwrite this saved game? |
| Read failure | This saved game could not be loaded. |
| Unusable/unformatted device | This VMU cannot be used. Check it in the Dreamcast system menu. |

Use the selected device's real port/slot when it is available; otherwise use the generic VMU label. The virtual GameCube channel is not an accurate physical port label. Distinguish storage-only cards from LCD-capable VMUs if the detected device supports memory but no display.

If a screen shows free/required blocks, obtain true VMU counts and appropriate compressed-save estimates through a read-only presentation interface. Do not relabel the adapter's synthetic GC capacity as native VMU capacity or promise an exact compressed size before it is known. Keep the existing save admission/error decisions intact. The game continues to refuse formatting; formatting instructions must direct users to the system menu without introducing a format action.

## 6. Integration design

### A. Sprite and image replacements

Use `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tools/extract_ui_images.py` to inventory relevant TPL images and write private contact sheets. For each replacement record archive path, entry/tag, TPL/texture index, pixel format, dimensions, used UV rectangles and original/native-package hashes.

Use `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tools/ui_overrides.py` and `UI_OVERRIDES` for the image paths it already supports. Keep source texture identities stable. Preserve existing title artwork by composing an isolated candidate override directory with verified copies of the accepted overrides plus the new UI replacements. Do not edit `/root/re4data/overrides/ui` during development. Report any competing replacement for the same source key instead of silently choosing one.

For small high-contrast glyphs, inspect the actual encoded result for ringing, blurred lettering and alpha fringes. Preserve the selected format initially; change compression or palette only for the affected package if visual evidence and the memory budget justify it. No global texture-quality change is required.

### B. Inline font glyphs

Determine which button references are actual font cells. The native message renderer decodes cells directly from the font's CI4 sheet; the ordinary native texture overlay may not intercept this path.

Preferred order: reuse a proven font-asset override if one exists; otherwise add a narrow Dreamcast-only substitution at the glyph preparation boundary. Key it by stable font/sheet identity and glyph code, not a transient pointer alone. Preserve glyph advances, bearings, cell limits, font-reload invalidation, palette-bank ownership and render fences. Keep ordinary letters unchanged.

A read-only presentation resolver may be needed for context-dependent prompts. It must choose a glyph/cue from the existing input profile and action context without changing controller state or consumption of input.

### C. Native VMS save icon

Generate one canonical palette/indexed-pixel artifact and derive the runtime and host-tool representations from it. Replace `build_icon` in `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/vmu_store.cpp` and `default_icon` in `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tools/vmusave.py` consistently.

Preserve file names, application ID, compression, payload layout, save versions, A/B update ordering and recovery behavior. Recompute the package CRC through the existing builders. Maintain one icon frame, the current payload offset and the same block allocation for an identical payload. Existing saves continue loading; the new icon appears on newly created or normally rewritten saves. Do not mass-rewrite users' saves just to refresh their icons.

### D. Optional LCD emblem

Use the existing LCD orientation and Maple retry conventions. Publish on a meaningful state change or at initialization, with bounded retries; avoid a new per-frame upload loop. Status/error/diagnostic output has priority and restores the idle emblem when appropriate. Handle no LCD, disconnection and multiple VMUs without changing save-device selection. Keep this optional phase independent of the TV glyph and native save-icon rollout.

## 7. Implementation phases and reviewable outputs

| Phase | Work | Exit artifact |
|---|---|---|
| 1 — Inventory | Trace all prompt paths, extract relevant images/fonts, map message IDs and controller contexts | Complete source-to-control/VMU manifest and current-state contact sheet |
| 2 — Generate | Produce style candidates, select the family, generate missing states, inspect actual-size readability | Chosen masters, per-glyph assets, palette specs, recorded prompts/hashes and UI mockups |
| 3 — Static UI integration | Encode sprite overrides, handle font cells, apply contextual prompt presentation and VMU wording | Candidate UI package and a coverage report identifying every replaced or still-unmapped item |
| 4 — Native save icon | Replace the existing placeholder in both package builders | Native icon bytes, decoded preview, matching host/runtime package fixtures |
| 5 — Validation | Visual/input coverage, save compatibility, resource and frame-time checks | Before/after captures, package results, gameplay trace and resource delta report |
| 6 — Optional LCD | Integrate the monochrome emblem with existing display ownership | Correctly oriented LCD captures and disconnect/status coexistence results |
| 7 — Delivery | Review intended changes and package only the qualified UI work | Separate commits for assets/tooling, UI substitutions/text, save icon and optional LCD; exact integration instructions |

All phases execute in the isolated worktree and private output tree. Serial build/test scheduling follows the existing project harness. Integration into the active game happens only after the candidate is concrete and reviewable.

## 8. Validation and acceptance

### Visual and input checks

- Compare screens at matching game/menu state. Verify real output size and interlaced-display readability, not only enlarged PNGs.
- Check letters, physical button identity, alpha fringes, aspect ratio, spacing, baseline, shadows, pressed/held states, animation frames and combination prompts.
- Exercise each prompt using the corresponding Dreamcast input, including D-pad look versus map tap, scope zoom, menus and QTEs. Include all supported control configurations and the separate extra-control profile.
- Reload fonts and enter/leave menus to catch stale glyph-cache entries. Ensure atlas capacity, palette banks and render fences remain correct.
- Require complete inventory coverage: no unidentified GameCube button/card artwork remains in the reviewed shipped UI paths. Record any untested language or route explicitly.

### Package and save checks

- For the native icon, validate exactly 32×32 pixels, 16 ARGB4444 entries, 512 indexed bytes, nibble order, one frame and correct package CRC.
- Run the relevant existing tests in `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tests/test_vmusave.py`. Add a fixture comparing host and runtime icon/palette bytes and checking an unchanged payload and block count.
- Use disposable VMU images for create/save/overwrite/load, missing/full/unformatted devices, unplug/reconnect and existing-save compatibility. Verify the icon in the Dreamcast/Flycast file browser, separately from in-game save artwork.
- Validate static package data before any physical-hardware save test; use a dedicated test VMU or backed-up disposable image through the project's normal testing workflow.
- For LCD, validate 192-byte encoding, orientation, no-display handling and coexistence with existing status/diagnostics.

### Gameplay and performance checks

- Run the relevant existing pad-mapping tests and a matched-input logic-trace comparison for UI-only runtime changes; gameplay decisions remain STRICT.
- Compare source-identical builds with only the UI candidate changed. Record ELF size, RAM/VRAM, texture/glyph cache pressure, draw calls and frame-time delta.
- No network, image generation, expensive conversion or new disk lookup occurs in the gameplay frame loop. Reuse current resident packages and bounded glyph caching.
- Keep glyph/image dimensions and atlas footprints unchanged where possible; a static icon replacement adds no VMS storage for the same payload. Any additional UI resident memory must be reported rather than hidden inside the 30 fps budget.

## 9. Proposed tracked files and private artifacts

Plan now:

- `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/docs/DREAMCAST_UI_VMU_PLAN.md`.

Likely implementation touch points, selected after inventory:

- Existing image tools, a small UI source-mapping manifest, generated-format specifications and narrowly targeted validation fixtures.
- `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/native_ui.cpp` and its interface only if font-cell substitution needs a hook.
- Dreamcast presentation/message bridging for contextual glyphs and VMU text, with recovered gameplay logic guarded and unchanged.
- `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/game/platform/vmu_store.cpp`, `/root/probe/re4-dreamcast-ui-vmu-plan-20260925/port/dreamcast/tools/vmusave.py` and a shared generated icon definition.
- Optional existing LCD integration point after ownership review.

Keep extracted source sheets, composite overrides, discs, saves and captures private. Record provenance for newly generated originals and their derived composites. Keep new save-icon packaging code separate from gameplay/performance changes so the work can be reviewed and integrated independently.

## Completion criteria

The work is complete when the generated Dreamcast control set and VMU presentation are integrated in a tested candidate, prompts match actual inputs, all selected UI states are covered, the native save icon is correctly displayed, existing saves still load, and the isolated branch contains a reproducible UI-only delivery. The optional LCD phase is reported separately. This plan itself does not claim implementation or visual acceptance.
