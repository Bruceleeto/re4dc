# Lane route (coordinator): make r106 playable

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/route, tree /root/work/lanes/route, evidence /root/probe/lanes/route.

## Goal
The play build continues past r103: r103 -> r106 (chapter 1-1 end), following R4_FIRST_STAGE_GAP_AUDIT.md "Full stage-1 route".

## State and next step
`assets.sh discover r106` (2026-10-01):
- em29 / em2e: lint value-init (`new (em) cEmXX();`), not in MODULES / modules.cpp / the ENEMY_DEMAND audit list.
- The room container st1/r106 is not prepared.
- Event r106s00 (4,268,192 B, 165 assets) has no route movie and no prepared evd.
- Heap 4: 4 enemy archives, worst case 1,524,352 B, no measured budget yet.

## Numbers (image, build, evidence)

## Ready to land
