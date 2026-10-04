# Combined native-scene experiment checkpoint, 2026-10-04

This branch preserves source work for review and recovery. It does not change the play recipe or certify a release. The retained remote play branch was ce39455fe04a6bf98227fe8d1da762a9192fd90a when checked on 2026-10-04.

## Frozen combined baseline

Base: 94197538. Applied source snapshot SHA256: 07df8d8e04a477d5fd7a6f88d02ac5b0fad74e6f1981074b25fa5cc648e9395a.

The checkpoint combines the previously reviewed model/material and world-loop changes with complete room/stage module builds, actor certificate preservation across inventory swaps, and the complete state observer. The observer records gameplay, decisions, effects, positions and explicit ownership/lifetime validity. Its large swapped-memory index uses the existing diagnostic backing bank. These diagnostics are disabled in performance builds.

The same two full-module images passed seven paired controlled scenarios (square, H2, r104 inventory/costume, r103 animals, r219, r40a, and scripted r40a/r40c lifetime transitions): 24,279 complete LT/LU/LX frames, 5,773 position samples and 35 rolling digests. The asynchronous sound-query bucket differs at 57 ticks and is reported separately. Source ELF: 789520d9d5d6d01d8eae2fee6117a99f889dfa8535c69be45ce9cc4c51a81709. Candidate ELF: e41492af9e4ff698d77020e73485440a646e9e491c8ad55c5d5241f7618d82b8.

Both sides use ACT_CAP=0 and PACE_MODE=off. The same schema-5 observer and codec-ready fixture are used on both sides. This is controlled-fixture evidence: enabling the ownership recorder changes asynchronous door timing compared with the older observer. It does not prove production timing, natural transitions, all-room coverage, or physical Dreamcast performance.

The observer-disabled performance image is allocated-byte/layout/overlay identical to measured candidate e1cbf4a4c937def4c034df5bd61bb0c4f9e78a273c4c6442a0122fa0310fe23b, except its verified build timestamp. The current complete candidate costs 82.6492 ms of SH-4-model CPU work in the uncapped square, ticks 1330:1389, 60 frames, trace stride 1, tail 3. Main/pacing/retrace waits are excluded. Model sensitivity is 71.2304 to 98.6795 ms. This is not 30 fps or hardware acceptance.

## Open visual and coverage issues

- Inventory captures in both source and candidate r104 controls show incomplete art and a cut-up player view. The same defect is present in the source control captured at 05:09 on 2026-10-04, before early actor admission. An older opening-r13 capture shows a complete inventory. The causal change has not been isolated. Game-state and swap restoration passes are not a visual pass.
- Six missing texture packages have been prepared privately with the existing converter. Adding them to r104 eliminates the missing-texture rejection count and preserves recorded state, but does not resolve the inventory image. Two packages use VQ; the large fence texture has visible detail loss and is not an approved default.
- Existing GX-immediate effect/cloth/shadow omissions, later-room wrap failures, and some actor/animal appearance differences remain. Neither baseline image is a claim of complete original-game rendering.
- Disc 2, other rooms, natural doors, physical hardware, and real gameplay through the complete route remain unqualified.

Detailed immutable measurements, hashes, captures and failing runs remain in the private supervisor evidence directory, under tools/supervisor-20261003/scene-baseline-v4 and h2-matrix. Private models, textures, discs, binaries and captures are not included in this commit.
