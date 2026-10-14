# Vegetation punch-through candidates and measurement

The user requested test-9 measurements before converting foliage and rigid
cutouts, starting with r101 and r100. Candidate packages require matched stills
and user visual review. Mist, smoke, glass, water, fades and projected soft
shadows keep their authored translucent behavior.

## Submitted-area observer

`TA_MATERIAL_DIAG=0` is the default. Enabling it requires `TA_BIN_DIAG=1` and
`TA_HASH=1` and `PVR_STREAM=1`; use `MCHECK_PT=1` for the actual submitted-header blend check.
Test-9's diagnostic mode also uses `RENDER_OPTION=0`, because the tiler is fixed
to 640 by 480. The quality-only option is inactive inside that mode.

The observer reads the existing TA replay without changing packet bytes. It
accumulates each submitted triangle and complete 64-byte sprite, clipped to
640 by 480, by list, submission path and uploaded texture identity. Source 0
is unclassified, 1 is PS2 world, 2 source models, 3 UI and 4 effects. A model
path is not sufficient to identify a character; use source asset manifests.
Texture lookup uses the live uploaded Entry and TCW address. Unresolved atlas
or external textures remain explicitly unresolved. OP/TR/PT lists are 0/2/4.

`tamat:` rows end with `tamat total:` for each unique scene serial. Frame
numbers can repeat across scenes. Totals include zero-area scenes, overflow,
invalid-coordinate and orphan counts. The fixed 256-row capacity refuses
silent aliasing; any nonzero failure count invalidates that measurement.
Rows with no triangles are omitted; the total row count includes their headers.
Integer row area is floored from float accumulation. Current totals sum those
printed row integers exactly, with explicit range/overflow rejection. The
initial W1 diagnostic used independent float totals; its r100 run exceeded
the parser rounding allowance and is rejected as a quantitative report. This
fix changes only diagnostics; W1 raw evidence is retained. A truncated last scene
is incomplete and cannot be used. Preserve raw logs and explicitly document
any lossless reconstruction of an asynchronous serial-log interleave.

This is submitted screen area before hardware culling, depth/alpha rejection
and user-clip rejection. It measures potential translucent coverage, not
shaded pixels, actual PVR time or physical-console FPS. The diagnostic is
expensive and must not be used as a CPU timing build. Any conversion from
area to milliseconds must identify its calibration and limits; moving area
to PT does not establish that the PT rendering cost is zero.

Host verification: `g++ -std=c++17 -O2 -Wall -Wextra -Werror
 tools/test_ta_material_diag.cpp` covers clipping, winding-independent area,
invalid coordinates, full sprite bursts, attribution, overflow and resets.
The first actual r101 capture resolves world texture keys and emits PT audit
records with zero bad headers. The observer-off loaded BIN, all overlays and
symbols are byte-identical to the test-9 control at linked end `8c4143fc`.
Private measurement and identity manifests are retained separately; no
conversion, visual acceptance or performance improvement follows from that
observer smoke check.

## Candidate invariants

The existing `--cutout-max-alpha 224` option recognizes exact two-level alpha
sets; it is not a general pixel threshold. More complex foliage needs an
explicit per-material candidate and close-up review. Preserve world mesh,
placement and opaque geometry, and keep a source-key/material-change manifest.
For r100, update the real sidecar CRC and matching identity/cell references
without changing cell geometry. Keep the runtime's expected sidecar checksum
consistent so interior culling remains active. Never force a checksum collision.

The diagnostic rejects incomplete 64-byte vertices or headers at scene end.
Opaque letterbox bars use the UI source scope, including when stream opening
was triggered by a world draw. The initial W1 smoke inherited the caller
scope for those bars; its TR/PT attribution is unaffected.
