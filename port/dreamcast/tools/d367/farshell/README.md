# Far shell tools (FAR_SHELL, lane farshell16, 2026-10-16)

Offline build of `dc/native/rXXX/far-shell.fsh`: what the game draws beyond the View distance cut (Short
12.5 m; Near keeps its plain cut) instead of the PS2 world's opaque pass, so the horizon keeps its landmarks. Runtime:
`game/platform/far_shell.inc` (knob FAR_SHELL, game30.mk). Lane doc: `docs/lanes/farshell16.md`.

Windows (Git Bash) with Python 3 + numpy + Pillow and Blender 5.2. One room:

    bash build.sh r101 <pkg dir with ps2-world.re4mesh/.r4pw> <tex.pak> <r101_016.RTP> <work dir> <out .fsh> [eyes...]

| Step | Tool | What it does |
|---|---|---|
| 1 | fs_extract.py | PS2 world package (level 0) -> world.npz (triangles, UV, prelit colour, texture key, pass) + textures as PNG |
| 2 | fs_eyes.py | reachable eyes: PS2 enemy route graph (PTR2) + 1.6 m, densified every 3 m to the 4 nearest nodes under 25 m, plus warp points; `--lake` / params lake box adds open-water boat eyes |
| 3 | fs_blender.py build | far-seen faces (BVH rays from every eye hit at depth >= cut - 2 m, <= Full 25 m), planar dissolve 4 deg, parts under 1.5 m dropped, collapse decimation to `tris`, triangles farther than `max_dev` from the source dropped, 12 m XZ cells; material mode: every shell corner takes the UV of the source triangle under it (extended along its plane) and its prelit colour |
| 4 | fs_pack.py | shell.npz -> FSH1 (format in its docstring): groups = (material, cell) <= 256 vertices, i16 positions, RGB565 colour, u8 strips; each triangle's UVs move by whole tiles (repeat-wrapped textures: same pixels) so neighbours share corners (`--no-uvshift` off) |
| 5 | fs_vram.py | texture bytes by closest approach: textures only ever seen beyond the cut (what a shell proxy could reclaim) |
| - | fs_preview.py | Blender preview of Full / Short / Short + shell at given views (guidance only, not Flycast pictures) |
| - | fs_sheet.py | contact sheet |
| - | fs_final_sheet.py | FARSHELL-SHEET.png from the Flycast still runs (Full / Short / Short + shell per view) |

No new textures: the shell uses the world's own texture keys, so it costs 0 B of VRAM. A baked atlas was tried
first and rejected: a 512 x 512 atlas over the far-seen surface gives ~1.6 texels/m where 12.5-25 m needs 16-33, and
r101 has ~196 KB of VRAM free with a 12 KB largest block (no room for a larger one).

params/<room>.json (v6, 10-16, user "short shell + half vertices"): r101 3,200 triangles (6,634 vertices), r100
2,900 (7,044), weld 150 mm, collapse weighted by `protect_by: border` (border vertices weight 0.3: the shell is open
sheets of far-seen faces, and plain collapse erodes their borders first, so cliffs and roofs shrink into planes), cut
12500, full 25000, cell 12000, max_dev 1500, min_part 1500, rays 20000. v3 (6,000 triangles, weld 20 mm: 13,457 /
14,177 vertices) was the first approved look; r10b keeps v3 params (not shipped: the lake is never cut).
Thin parts under ~15 cm (fence slats, posts) weld away at 150 mm. Lower `tris` (2600, v1) leaves holes where decimation folds big rock faces and the
spike filter removes them (r100 rope bridge cliffs).
