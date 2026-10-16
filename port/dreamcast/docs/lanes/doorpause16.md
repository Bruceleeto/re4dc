# Lane doorpause16 (2026-10-16): the door pause, chapter 1

KNOWN_ISSUES "Pauses when entering rooms". Full report with the per-door table, the PS2 comparison and the levers:
workspace `DOOR-PAUSE-CH1-20261016.md` (C:\Game Dev\Emulators). Branch lane/doorpause16 from t15/int 2293175b.
Evidence C:\Flycast-Evidence\re4-dreamcast\doorpause-20261016. All times are emulated (console-like Flycast with
the GDEMU profile, a 2 MB/s + 1.5 ms/command drive model, PCSX2 for the PS2), not console.

## Knobs (default 0, knob-off image identical to t15/int)

- `DOOR_PROBE=1` (needs DISC_READ_METER=1, PHASE_METER=1, GAME_TICK_LOG=N): log-only door phase meter
  (platform/door_probe.cpp). Marks in game.cpp / stage.cpp / sce_at.cpp / ui_bridge.cpp / main.cpp through the
  forced header platform/include/door_probe.h. Lines `DOORPH:`, `DOORFILE:`, `DOORTHD:`.
- `SND_PAD_SKIP=1`: the source queue skips the disc reads of a sound part's zero padding after a build-time
  converted bank (platform/include/snd_pad_skip.h forced into dvd.o; audio_aica.cpp re4dc_audio_pad_skip). AICA RAM,
  ARAM addresses, UseAramSize and the queue steps are unchanged. 0.85 to 2.1 MB less read per door (17 %).

## Results (short)

- Fast drive (GDEMU profile): 1.6 to 2.7 s per door; half is waiting on sounds (door sound fade 0.5 s on 11 of 13
  doors; old music slot 0.9 to 1.3 s on the 5 music-change doors). SND_PAD_SKIP saves ~0 here.
- 2 MB/s model: 4.0 to 9.9 s per door (route mean 7.39 s), drive busy 2.6 to 7.3 s; texture preload 55 to 1,015
  small tex.pak reads per door. SND_PAD_SKIP: mean 6.58 s (-0.8 s).
- PS2 (PCSX2, its DVD timing): 3.7 to 9.7 s for the same room changes (mean 6.56 s).
- Top levers: texture preload in large reads (proposed), SND_PAD_SKIP (built), reading the next room during the
  sound hand-over (proposed).

## Gates for SND_PAD_SKIP=1 (on the T15REC release recipe, commit cfa76c2e)

- Knob-off identity: kP 12dddcac and rP e4eba3fe byte-identical to t15/int 2293175b (all 6 overlays the same).
- Release recipe + knob (out-dkrP): image f2269982, missing 0, _end +288 B; fp_twin IDENTITY OK.
- STRICT / decisions door103 (harness Flycast, stop tick 2000): the knob-on arm loads the warp's first room 3 ticks
  sooner (placed tick 181 vs 184); the fixture's presses count from room entry including loading ticks, so the inputs
  are moved 3 frames earlier for that arm (door103-warp-m3.txt, same room frames). Logic trace STRICT room aligned in
  r101 (1,820 ticks) and r103 (828 ticks). Decisions MUST-IDENTICAL except lq (line query answers, with info sl/lp/sq):
  the sound system's own occlusion queries (+2 queries every other tick) run one tick out of phase with audio timing.
  RNG, flags, room, player / enemy / object state, damage, collisions and effects are identical.
- KOS squeeze 48 KiB (twin fpdpkW, 10 runs): KOS SQUEEZE GATE PASS (min headroom fight 13,024, call 43,288,
  door103 19,624, leave 13,224 B; 0 OOM).
- GDEMU race gate (twin fpdpgW, gdemu profile, 10 seeds): PASS 0/10, 0 bad reads.
- Not run: full play, weak-profile gate.

Evidence C:\Flycast-Evidence\re4-dreamcast\doorpause-20261016 (st-off / st-on / st-on3, strict\, kos\, gdemu\).
