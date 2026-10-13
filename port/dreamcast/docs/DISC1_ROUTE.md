# RE4 GameCube disc 1: required room route and port coverage (2026-10-13)

Analysis only: no code or recipe change. Tool: `tools/d367/stage_route.py` (AEV type-1 door records + ITA items from
the GameCube debug disc via the assetpipe `GcIso` + `room_smd.decode_das` readers, plus source door gates). Stage 2
support was added on 2026-10-13: `--stage 2 --start r200 --exit r300`, the stage-2 `GATES`/`KEYS`/`JUMPS`, and
chapter waypoints (`WAYPOINTS`): a room is required when removing it cuts the exit or any chapter-end room. The
stage-1 output is unchanged (re-run diff identical). Outputs: `/root/probe/stage2-route-20261013/`
(`stage2_route.{txt,json}`, `stage1_recheck.{txt,json}`, `iso_rooms.txt`).

## Where disc 1 ends

- The disc-1 room set (`iso_rooms.txt`) is r100-r120, r200-r22c, and r400-r411 (stage 4 rooms, off the main route).
  It contains no r3xx room.
- The only main-line exit off the disc is **r22a door 1 -> r300**, after `SceSetChapterEnd(CHAPTER_4_4, 1)` (the rope
  down the mine shaft). That is the end of chapter 4-4 and the disc change. Disc 2 is retail and holds r3xx only
  (stage 3, the island).
- The shooting range r22c also has doors to r305 / r31d. They are its exits in stage 3 (each range exit returns to the
  room it was entered from), so they are not a route.

## Stage 2 (the castle, chapters 3-1 to 4-4)

| Chapter | Rooms (in order) | Gates, keys, events |
|---|---|---|
| 2-3 end | r10f -> r200 | the False Eye door; r200 s00 (Leon and Ashley reach the castle), `SceSetChapterEnd(CHAPTER_2_3, 9)` |
| 3-1 | r200 -> r202 -> r207 -> r203 -> r201 -> r208 -> r204 | r202 catapults + wall crank; r207 swords (items 0x80 / 0xC4); r203 key 0xA7 (found there) unlocks its door; r201 main hall; r208 water mill; r204 s00 (Ashley falls) ends 3-1 |
| 3-2 | r204 -> r205 -> r204 (part 1) -> r209 -> r20a -> r20b | r205 pendulums lead to r204's far side (inferred from AEV parts); r209 salon key 0xA3; r20a shoulder-carry door; r20b great hall s00 ends 3-2 |
| 3-3 | r20b -> r20c -> r20f -> r206 | r20c cage trap; r20f lever platform; r206 sniper sequence, Luis dies (`r206_die_event`) ends 3-3 |
| 3-4 | r206 -> r20d -> r20e -> r20d -> r206 | Ashley's section (pl_type 1): Salazar crest 0x0F at the r20d switch, r20e maze; the reunion `r206_gouryuu_event` ends 3-4 |
| 4-1 | r206 -> r210 -> r222 -> r210 -> r201 -> r219 -> r211 -> r216, r212 -> r211 -> r213 -> r214 -> r217 -> r214 -> r218 -> r215 -> r229 -> r221 -> r22b | r210 mine lift; r222 dragon hall (altar gem 0x1E); r201 altar needs gems 0x1E (r222), 0x1F (r209), 0x39 (r20e) (door inferred); r211 needs cups 0x6E (r216, armor knights) + 0x6F (r212, roof trap); r213 drawbridge (em2d shown in s00); r217 timber puzzle drops r214's scaffold; r218 chainsaw sisters; r215 event; r229 sewer; r221 boss arena (ESL 0x8C) and elevator, first descent jumps to r22b (s00) which ends 4-1 |
| 4-2 | r22b -> r220 -> r223 -> r224 -> r21d | r220 elevator; r223 dynamite 0x8D; r224 water hall lever; r21d laser switches, the grave lift ends 4-2 |
| 4-3 | r21d -> r225 -> r21b -> r225 | r225 crank / graveyard; its door needs key 0x82 (ITA r21b; door inferred); r21b cart ride; the r225 -> r226 lift ends 4-3 |
| 4-4 | r226 -> r227 -> r228 -> r22a -> r300 (disc 2) | r226 giant Salazar statue chase; r227 cargo lift waves; r228 Salazar boss; r22a rope down ends 4-4 |

Required: **40 rooms** (r200 plus the 39 the tool lists: r201-r20f, r210-r216, r217, r218, r219, r21b, r21d, r220-r22b
except r21a and r22c).
Optional: r21a (storage house, key 0x7B used inside it), r22c (shooting range). Every stage-2 room is reachable.

Bosses and set pieces:
- r221: the insect boss (ESL 0x8C).
- r228: Salazar.
- r226: the giant statue chase.
- r21b: the cart ride.
- r20d / r20e: Ashley's section.
- r213 s00: em2d appears in the cutscene.

Model limits. These gates are inferred and the room code doesn't name the door number:
- r204 door 4 (via r205);
- the r201 altar door (0x21 -> r219);
- r206 door 7 after the reunion;
- r214 door 1 after r217's scaffold;
- r225 door 1 after key 0x82.

AEV lockType 1 doors are treated as locked from that side, as in stage 1 (r201 0x19, r206 0x06). ESL- or
event-enabled doors are not modelled. The r205 and r217 requirement depends on those inferred gates.

## Disc 1 total

Stage 1: 23 required, plus one of r11a / (r10c + r10e) and one of r11d / r11e, so at least **25 rooms**. Stage 2: **40**.
Disc 1 needs at least **65 rooms**.

## Port coverage: test 9 recipe (2026-10-13)

The recipe is `/root/probe/lanes-20261012/test9/t9-build.sh` (ROUTE_CH13=1, ROUTE_CH21=1).
- A room is "on the disc" when `dc/native/rXXX/ps2-world.r4pw` is staged. `route_end.cpp`
  `re4dc_route_room_built` checks it, and any other door shows "Coming Soon" and holds.
- Every test 9 stage manifest (`/root/probe/lanes-20261012/test9/stage/*.json`) carries the same 17 rooms:
  r100-r10b, r11a, r11b, r119, r118, r117. r120 is the intro movie room jump.
- Status is from Flycast lane evidence. No console play exists past r100 for test 8/9: the console HEAPCRASH (KOS heap
  corruption in r100, test 8 photos) is open and blocks test 9 for every room.

| Room | Ch | Status | Evidence |
|---|---|---|---|
| r120 | 1-1 | playable | intro movie -> r100 (play discs since m1) |
| r100 | 1-1 | playable (Flycast); console crash open | test9 H2 runs; RE4DC-TEST9-HANDOVER-20261012.md HEAPCRASH |
| r101 | 1-1 | playable | bell gate STRICT runs (lanes/route.md r117 gates) |
| r103 | 1-1 | playable | D:\Flycast-Evidence\re4-dreamcast\bg-route-r103door / r103exit |
| r106 | 1-1 | playable | lanes/route.md "r106" (route-r106w1, HALT 0), 1-1 end |
| r104 | 1-2 | playable | lanes/route.md "r104" (QTE pass -> gameplay) |
| r107 | 1-2 | playable | lanes/route.md "r107" (r107b/c HALT 0) |
| r105 | 1-2 | playable | lanes/route.md "r105" (r105s00, chapter 1-2 end) |
| r102 | 1-3 | playable | ROUTE_CH13 (r102 s00 PS2 movie, merchant em18); no separate run log found |
| r108 | 1-3 | playable | r108 STRICT 1,100; door r108 -> r109 HALT 0 |
| r109 | 1-3 | playable | r109 crossed HALT 0 MISSING 0 |
| r10a | 1-3 | playable | r10a STRICT 2,925 ticks; door -> r10b |
| r10b | 1-3 | playable | D:\Flycast-Evidence\re4-dreamcast\r10b-20261009 (Del Lago to the 1-3 end, save) |
| r11b | 2-1 | playable | D:\Flycast-Evidence\re4-dreamcast\r11b-20261010 |
| r11a (pair) | 2-1 | playable | D:\Flycast-Evidence\re4-dreamcast\r11a-20261010 (STRICT 2,402) |
| r119 | 2-1 | playable | D:\Flycast-Evidence\re4-dreamcast\r119-20261010 (g3 STRICT 2,705, s00-s30) |
| r118 | 2-1 | playable | D:\Flycast-Evidence\re4-dreamcast\r118-20261010 (w1, d4) |
| r117 | 2-1 | playable (key 0x3C pickup not walked) | D:\Flycast-Evidence\re4-dreamcast\r117-20261010 (pk1/pa1/pd1/pr1b, 2-1 end + save) |
| r112, r111, r113, r11c | 2-2 | not reached | not on the disc: r118 -> r112 shows "Coming Soon" |
| r11d or r11e, r10f, r11f | 2-3 | not reached | not on the disc |
| r200 | 2-3 end | not reached | not on the disc |
| stage 2 (39 rooms, r201..r22b) | 3-1..4-4 | not reached | no st2 room package, PS2 world or route knob |

Optional rooms not on the disc: r10c, r10e (the other 2-1 pair), r10d.

Summary: 18 of the 65 room minimum play in Flycast (17 required + r11a). That is chapters 1-1 to 2-1, to the 2-1 end
save in r117. None are entered-but-broken in Flycast; r100 is broken on the console (HEAPCRASH).

Remaining 47 rooms by chapter:
- 2-2: 4
- 2-3: 4 (with r200)
- 3-1: 6
- 3-2: 4
- 3-3: 3
- 3-4: 2
- 4-1: 14
- 4-2: 4
- 4-3: 2
- 4-4: 4
