# Test 11 item D: black world faces (lane t11-bk, 2026-10-14)

**Cause (CH1 audit 10-14).** Every black world face of chapters 1 and 2-1 lies in a PS2 scenario BIN whose header light
flag (u32 little-endian at 0x24) is 0xa0000000. Both the GameCube and the PS2 draw those BINs with the GX channel's
ambient register (trans_lit.cpp LightSetModel: flag 0x40000000 clear -> amb_src REG, mat_src REG). The DC package
drew only their vertex colour, which carries no ambient, so every corner without light was black.

## Light sources (ps2_room_r4im.py, all default off)

| option | 0xa0 piece colour | source |
|---|---|---|
| `--a0-light ps2 --a0-light-json ps2-light.json` (**default test 11 data: blackps2**) | (VC + (PS2 amb_scr + 1) / 256) x SMX x scale; no clamp at 1 on any COLOR vertex colour | PCSX2 measurement (CH1-AUDIT-20261014\ps2-light.md: GS dumps, 17 rooms, median error <= 0.5 GS units). The PS2 adds no dynamic scenery light. scale = recipe GC TEV (or PS2 W with `--a0-ps2-w`) |
| `--a0-light gc` with a `gc_room_lit.py --all` json (**blackgc**) | clamp01(LIT ambient + the static LIT lights the model selects, N.L, GX attenuation) x SMX x TEV; VC not used | the GameCube's own static result: setModel2 selection, every scenery light type of trans_lit.cpp, the LIT cut of the camera area (switchCamera -> update(area_no)); lights with a parent (lanterns, torches, carried lights) left out |
| `--a0-light ambient` (= `--a0-ambient`) | min(VC + GC ambient, vc_clamp) x SMX x TEV | first pass (ccb8ede9) |

`--a0-light-json` with `gc` merges a measured light set (`env`, `lights_cut`, `ambient_gain`, `light_gain`) over the
LIT json. `--a0-light-own` lights each copy of an instanced BIN where it stands (default: the copies' mean, so
they keep sharing one mesh; own costs r106 +438 KB of heap-4 mesh).

Off = the staged packages byte for byte (control rebuilds of r103, r106, r109, r10b, r117, r119).

## Data sets (`/root/probe/lanes-20261014/t11/data/<set>/<room>/ps2-world.{re4mesh,r4pw,ids}` + `newtex/`)

Rooms r102 r103 r104 r105 r106 r107 r108 r109 r10a r10b r117 r118 r119 r11a r11b, each staged as
`dc/native/<room>/ps2-world.*`; `newtex/*.re4tex` = the texture keys the gain step re-keyed that are not in the
test 10 tex.pak (staged loose as `dc/tex/<c>/<name>`). r10b is built with --cutout-max-alpha 224 (supersedes item
A r10bcut), r103 with Codex's SMX-only rule (supersedes smx103). r100 is left out (its interior cell checks the
package CRCs in game code) and r101 is the legacy wrapper package.

| set | mesh bytes vs staged | new loose textures |
|---|---|---|
| blackps2 | -6,272 .. +9,632 B per room | 295 |
| blackgc | -42,016 .. +184,832 B (r119 +185 KB, r109 +154 KB, r103 +113 KB) | 424 |

## Black share (read_scene prelit colour, black = mean corner < 0.03, opaque corners)

| room | test 10 | PS2 formula | GC bake |
|---|---|---|---|
| r109 | 40.1% | 0.0% | 0.0% |
| r117 | 20.0% | 0.1% | 5.8% |
| r106 | 17.3% | 0.0% | 0.0% |
| r105 | 17.2% | 0.0% | 0.0% |
| r119 | 16.3% | 0.0% | 0.0% |
| r118 | 16.1% | 0.0% | 0.0% |
| r108 | 15.8% | 0.1% | 0.1% |
| r102 | 14.7% | 0.0% | 0.0% |
| r107 | 10.6% | 2.5% | 6.1% |
| r10b | 7.9% | 0.0% | 0.0% |
| r104 | 3.5% | 0.3% | 0.3% |
| r10a | 2.1% | 0.0% | 0.0% |
| r103 | 1.9% | 0.0% | 0.2% |
| r11b | 1.4% | 0.0% | 0.0% |
| r11a | 0.9% | 0.0% | 0.0% |

What stays dark: r107 0xe0 faces whose PS2 vertex colour is 0 (both sets); in the GC bake also the faces the GC
leaves at its own low cut ambient (r117 camera area 1: ambient 3/255; r107: 7/255).

## Gates (Flycast, arm t11bkkmW = test 10 recipe + MCHECK_LEONGC TEX_CHECK=2 MCHECK_PT; data only, the play ELF is
test 10's; evidence C:\Flycast-Evidence\re4-dreamcast\t11-20261014\bk-*-p2, bks-*-p2, bks-*-gc, bk-ch12-gc)

blackps2: segments r106 (r103 -> r106), r109 (r108 -> r109), ch12 (r105), ch21 (r117), g3 (r11a -> r119 El
Gigante + both movies -> r118), lake (r10b boat, Del Lago -> r11b) and the four still views: TEXCHK PASS except
the known r105 results picture eaf5d457 fragmentation refusal (same in test 10); LEON-GC PASS everywhere; PT-BLEND
PASS in r103 r105 r106 r109 r119 r11a; r117 NODATA (no PT parts); r108 / r118 coverage only (segment edges, same in
test 10); r10b "incomplete packet decoding" also in the test 10 data runs (a-klake, a-mlake). No halt, no missing
symbol, no log overrun. The r11b first package open "missing or no heap" during the r10b -> r11b change happens in
test 10 too (opens on the retry). blackgc: the four still views + ch12 only (same results); its larger r119 / r109
meshes were not run through g3 / r109 segments.

Comparison sheet: `C:\Game Dev\Emulators\CH1-AUDIT-20261014\t11-black-sheet.png` (test 10 | PS2 formula | GC bake |
PS2 reference | GC reference; rows r106, r109, r105, r117). Changes the look: the user picks.
