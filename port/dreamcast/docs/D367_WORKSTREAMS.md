# D367 workstreams (started 2026-09-30)

The user's 2026-09-30 direction:
- Ganados must be optimized, and fewer of them drawn on screen.
- The remaining character models and the remaining stage-1 worlds are to be built from the PS2 version.
- We learn whether the r101 square encounter (67.7 hw ms) is an anomaly.
- Run this work "in a way not to lose work or progress like we've done before".

## What went wrong before (2026-09-22..29)

- **Work lived in local trees.** 186 local clones and worktrees built up, holding unpushed commits and uncommitted
  diffs. Finding what was unlanded took a machine-wide sweep, and 156 trees were deleted only after archiving
  (unlanded-archive-20260929).
- **Lane patches waited on a coordinator that forgot them.** Examples: MOTION_RESERVE (ambush crash), the r100/r103
  PS2 worlds, and door loading.
- **Outputs went to /tmp.** WSL shutdowns and restarts cleared them. A WSL shutdown also killed every run in flight.
- **Private assets had no record.** re4-assets-private (17 GB) had no history. The play build read its character
  bundle from a scratch folder, /root/probe/.../world-kernel-r20/private.

## Rules (every lane, every session)

1. **Branch, not tree.** Each lane works in a git worktree `/root/work/lanes/<lane>` on branch `lane/<lane>`. The
   branch starts at origin/dreamcast-port and is **pushed to origin** from its first commit.
2. **Commit and push as you go.** Commit after every verified step, and before any run longer than ~30 minutes.
   `wip:` commits are fine. Include tools, fixtures, recipes and the lane doc. Nothing stays uncommitted across a
   run, a break or the end of a session.
3. **Lane doc.** `port/dreamcast/docs/lanes/<lane>.md` on the lane branch holds:
   - goal, current state and next step;
   - every number with its image, build and evidence path;
   - "Ready to land" entries (commit, gates passed, knob default).

   Update it in the same commit as the work.
4. **No /tmp.**
   - Evidence goes under `/root/probe/lanes/<lane>/` or the Flycast evidence roots.
   - Private assets go to `re4-assets-private/<lane>-<yyyymmdd>/` with `SHA256SUMS` and `HANDOFF.md`.
   - After adding assets, run `python manifest.py` in the store and commit the store's local git (`git add -A;
     git commit`).
5. **Landing.** Lanes never push to dreamcast-port. The coordinator (main session) lands each "Ready to land" entry
   on the landing tree with the usual gates:
   - knob-off identity;
   - STRICT for render-only changes;
   - a clean-objdir build.

   It then commits, pushes, and merges dreamcast-port back into the lane branches.
6. **Check.** `bash port/dreamcast/tools/d367/work-check.sh` reports uncommitted or unpushed work in every lane tree
   and the landing tree, lane commits not yet landed, and unrecorded changes in the private store. Run it at the
   start and end of every session and before deleting anything. It must end `WORK-CHECK CLEAN`.
6b. **Autosave** (user OK 2026-09-30, after two usage-limit stops killed agents mid-edit). Root cron runs
   `tools/d367/autosave.sh` every 15 minutes. It pushes each lane tree's uncommitted state to
   `origin/autosave/<lane>` and never touches the lane branch. After a lost session, fetch that ref, review
   `git diff HEAD FETCH_HEAD`, and check out the paths you want. The log is `/root/probe/lanes/autosave.log`.
6c. **Detached runs.** Launch any run longer than a few minutes so it outlives the agent:
   `setsid nohup <cmd> > <evidence>/<name>.log 2>&1 < /dev/null &`. Write its PID and log path into the lane doc
   before waiting. On resume, check that log and PID before re-running anything.
6d. **Run areas in the store.** `playability-r11-r1/scenarios/`, `programs/` and `programs-*.json` are run output,
   not assets, and are outside the store's manifest and git. Delete your own discs there after each run.
7. **Deletion.** Delete only a lane's own rebuildable outputs (discs, objdirs), never another lane's tree. Lane trees
   are removed only after their branch is merged or archived on origin.
8. **Host.**
   - Keep D: at or above 10 GB and C: at or above 16 GB free.
   - Use `-j4` builds and asset `--jobs 4`.
   - Stop only your own PIDs, and never `wsl --shutdown`.

## Lanes

| Lane | Branch / tree | Owns | Does not touch |
|---|---|---|---|
| enc: encounter census | lane/enc | Answers whether the square is an anomaly. Hardware-model ms and Ganados drawn per view for every combat or crowd view reachable on the route (r100 s20 ambush, after the radio call, bridge; r101 entry square, bell fight, post-bell; r103 entry), on the r21k recipe. Warp presets and fixtures for them. | game code |
| crowd: Ganado cost + draw fewer | lane/crowd | Two parts. (a) Exact per-Ganado cost: the actors bucket (12.7 ms at the square) and the skin kernels. (b) A crowd draw policy (render-only, STRICT): how many full-detail Ganados, cheaper far levels or impostors, off-screen and behind-camera culling, with each option priced in hw ms and a look sheet for the user. | assets from ps2cast (consumes them) |
| ps2cast: PS2 characters | lane/ps2cast | Two parts. (a) A PS2 character converter (PS2 disc → the cast bundle format read by coarse_ganado_cast / cast_bundle.py), with cost and look against the external agent's v4-fit Ganados. (b) The rest of the stage-1 cast that the external cast does not cover, from PS2. | runtime character code (hands format needs to crowd / coordinator) |
| ps2rooms: PS2 worlds | lane/ps2rooms | PS2 room packages (`tools/ps2_room_r4im.py`) for the 20 stage-1 rooms still missing, in route order starting with r106 (R4_FIRST_STAGE_GAP_AUDIT.md "Full stage-1 route"), with look sheets and per-room heap and VRAM figures. | game code beyond room-package loading |

Sources:
- GC debug disc: `/root/work/re4-dreamcast/orig/G4BE08/re4_debug_disc1.iso`.
- PS2 disc: `C:\Game Dev\Emulators\re4_helpers\Resident Evil 4 (USA)\Resident Evil 4 (USA).iso`.
- r100/r101/r103 PS2 inputs: `re4-assets-private/world-agent-20260926/ps2-rooms-20260929`.
- External cast: `re4-assets-private/cast-20260925` (the 09-26 revision; v4-fit is in the play build).

The play build's actor bundle is `re4-assets-private/play-actor-bundle-20260928` (SHA256SUMS). Pass it as
`ASSETS` to `tools/d367/build-r21.sh`.

## Status

Each lane doc on its branch is the lane's status. The coordinator lists landed items here.
