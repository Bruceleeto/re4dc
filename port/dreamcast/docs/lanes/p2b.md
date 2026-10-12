# Lane B room packages: PT cutout rebuild (2026-10-12)

Built by lane A (p2c5 agent) for test 8 while lane B is on the letterbox clip. Only the part records below changed; no
other package content was touched.

Tool: `tools/ps2_room_r4im.py --cutout-max-alpha 224` (default 0 keeps the historical packages: a flag-off rebuild of
r10b and r100 reproduces the staged `ps2-world.re4mesh` and `ps2-world.r4pw` byte for byte). Each room was rebuilt
with the args recorded in its staged `ps2-world.json`. A texture whose alpha set is exactly {0, max} with max >= 224
(the PS2 cutouts store opaque as 239) becomes an ARGB1555 cutout and its blend parts move from the translucent list
(pass 2) to the punch-through list (pass 1). Per room the R4PW sidecar differs only in those parts' `pass` byte and
texture key; `ps2-world.re4mesh` and the placements are byte-identical.

| Room | Parts changed (2 -> 1) | PT triangles | TR triangles before -> after | New cutout textures |
|---|---|---|---|---|
| r100 | 11 | 4,740 | 22,881 -> 18,141 | 3 |
| r102 | 1 | 32 | 702 -> 670 | 1 |
| r103 | 32 | 7,004 | 8,712 -> 1,708 | 6 |
| r104 | 2 | 372 | 3,365 -> 2,993 | 1 |
| r105 | 4 | 3,192 | 8,448 -> 5,256 | 2 |
| r106 | 29 | 11,182 | 17,129 -> 5,947 | 5 |
| r107 | 2 | 396 | 2,239 -> 1,843 | 1 |
| r108 | 5 | 1,008 | 9,280 -> 8,272 | 1 |
| r109 | 9 | 68 | 28,379 -> 28,311 | 1 |
| r10a | 4 | 264 | 4,530 -> 4,266 | 1 |
| r10b | 13 | 2,228 | 10,058 -> 7,830 | 3 |
| r118 | 5 | 937 | 9,069 -> 8,132 | 1 |
| r119 | 9 | 68 | 13,442 -> 13,374 | 1 |
| r11a | 4 | 264 | 4,207 -> 3,943 | 1 |
| r11b | 14 | 2,260 | 9,982 -> 7,722 | 4 |

Unchanged: r117 (no {0, max} cutouts). Not rebuilt: r101 (the world-mesh-r21 package comes from another tool).

Store: `re4-assets-private/p2pt-cutout-20261012/<room>/` (ps2-world.r4pw, .ids, .json, tex/ = the new cutout
textures only). Disc: replace `dc/native/<room>/ps2-world.{r4pw,ids}`, add tex/ to `dc/tex.pak` (texel-keyed: a key
another room already added keeps the first copy), and for r100 `dc/native/r100/interior.cell` = the store's
`r100/interior.cell` (sidecar CRC 0x8c31fa61) with game knob `PS2_PT_CUTOUT=1` (the r100 interior cell checks the
sidecar CRC; without the pair the cell is refused, heap 4 shifts and gameplay diverges).
