# Lane look: r100 PS2 vertex colours and the r119 dark block (2026-10-13)

Worktree /root/probe/lanes-20261013/look (branch lane/look), work dir /root/probe/lanes-20261013/look-work, evidence
D:\Flycast-Evidence\re4-dreamcast\look-20261013, private outputs re4-assets-private\look-20261013. Base: the test 9
release recipe (rel9 r9-build.sh knobs, arms r9tW / r9tT / r9tP at db351823; lane arms lk*, same knobs, from d9bb69da).

## 1. r100 PS2 vertex colours (PS2_R100_SMX, default 0)

**The PS2 rule.** A COLOR group's shade on the PS2 is the vertex colour (GS 0x80 = 1.0, up to 255/128 = 1.99) times the
group's SMX ColorRGB / 255. Evidence (look-work vcstudy.py over the extracted PS2 scenarios, D:\...\vcstudy.json):
r100's saturated corners sit exactly on the low-SMX groups (SMX 84: 65,208 corners, median 1.992 = the GS maximum;
SMX 123 / 148: 1.992), while its SMX 255 groups have median 0.72. r104 (SMX 131: 1.992; SMX 255: 0.37), r10c (SMX
38 / 51: 1.992; 255: 0.27) and r117 (SMX 75: 1.06; 255: 0.15) show the same pattern: the artists pushed the vertex
colour to the GS limit where the material colour darkens it. The landed r100 package (`--color-light authored`)
dropped the SMX colour, so those groups drew at ~2x texel (clamped at the texture gain): the flat bright hedge and the
silver-white birch trunks. GC reference: GX gives min(vc, 1) x SMX x TEV x2 = 0.66 on SMX 84 groups; the PS2 rule gives
1.99 x 84 / 255 = 0.66: the two consoles agree where the landed package was wrong. No PS2 frame was captured (no
PCSX2 on this machine); the GameCube Dolphin frames are the reference.

**Conversion step that changes.** ps2_room_r4im.py `read_scene` COLOR-group colour: `--color-light authored`
(rgb = vertex colour) -> `--color-light ps2 --tev-scale 1 --vc-clamp 2.0` (rgb = min(vertex colour, 2) x SMX
ColorRGB / 255; NORMAL groups x1 = unchanged). Everything else is the staged package's recorded args (out/r100-uvg
ps2-world.json) plus `--cutout-max-alpha 224` (PS2_PT_CUTOUT). No converter code change. The per-texture gain then
re-keys 19 of the 55 textures; 2 of 106 instanced groups (BINs 14 / 108 with a different SMX colour per placement) get
their own mesh. Control rebuilt the same way reproduces the staged package byte for byte (re4mesh 508e5ba2 = uvg,
r4pw / ids = p2pt cutout).

**Package** (re4-assets-private\look-20261013\r100-smx): ps2-world.re4mesh 1,536,992 B (crc 6122bba4; staged
1,531,936), r4pw sidecar crc d888094f, ids, 19 new tex keys (loose dc/tex entries in the fixtures), interior.cell =
the cutout cell with the new header CRCs / bytes (geometry unchanged, so the same sub-cells and portals). Corners
clipped 132,962 -> 12,637. Heap 4 at r100 open -5,120 B.

**Code.** PS2_R100_SMX=1 (game30.mk, needs PS2_PT_CUTOUT=1): only the interior cell's expected mesh CRC / sidecar CRC /
mesh bytes (native_static.cpp pc::kPc*Use). Without it the new package draws but PCCULL says "not this package".
Knob off: objcopy image and all six overlays byte-identical to HEAD (lkbtP vs lk0tP). Knob on: `_end` unchanged.

## 2. r119 dark block (r119.dar PS2 objects package)

Reproduced on test 9 (fixture = test 9 house fixture with the st-r119 warp, arm r9tW): a dark flat block left of Leon
after the El Gigante knock-down, in every run with the p2b r119b package (test 8 r9-str119-t8, look r119full-a,
-c, and the payload-padded r119fullpad-d), never with the test 7 dar (r119gc-a). The package replaces two objects:
room BIN 0x22 (the tree El Gigante swings; 2 parts, 2 bones) and ETM et1100.bin. Rebuilt with each alone: BIN 0x22
only (r119bin-a, -c) and et1100 only (r119etm-a): no block. Padding the full package to the source size keeps the
block, so it is the data, not heap 4. Both objects' rebuilt geometry lies inside the GC bounding boxes per bone
(objchk.py); the cause of the interaction is not found. Fix (disc data only): the r119 objects package with the BIN
0x22 pair only (`ps2_objects.py room --pairs 22:22`, no `--etm`): re4-assets-private\look-20261013\r119c\r119.dar
(sha256 0a603a90..., payload 1,298,208 B, saves 7,968 of the 9,888 B).

## Gates and numbers

H2 (r9tT + test 9 packages vs lk1tT + both look packages, h2b warp, 480 s): STRICT 7276 ticks raw and af blanked, decisions MUST-IDENTICAL, s30 340/340 frames, heap_before 186,656 -> 181,536 (-5,120, the package). TEX_CHECK=2 (lk2tW): PASS on house, post-radio, r119. GDI boot (lk1tP + rel9 pkg fixture + look packages): title, HALT 0. hw model (house fight 1450:1569; r119 boss 900:979; drawn frames): house 39.97 -> 39.30 ms, r119 72.49 -> 73.63 ms (3 traced frames each: noise).
