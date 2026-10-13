# Native Ganado texture preparation

`ACTOR_TEX_PREP=1` prepares the exact native atlas keys of reviewed Ganados after
the ordinary native texture preload and model registration, before opening the
scene. It defaults to zero. `ACTOR_TEX_PREP_DIAG=1` adds bounded diagnostics.
The original source preparation, owner binding and on-demand texture paths remain
in place. The change does not suppress the loaded enemy texture tables.

The completed source ledger grants read-only metadata inspection separately from
the original Render callback's authority. The bounded walk validates frame, room,
room generation, primitive owner, manager generations and model serials. It rechecks
membership and lifetime/variant identity before returning at most five value-only
atlas descriptors. It cannot choose a native presentation or acquire actor storage.

The material reader uses current owned Info records and exact source role order,
archive/TPL ownership, source aliases, descriptors and live material modifiers.
With the existing `CROWD_READOPT` policy enabled, a missing Info can be proved into
a stack object using the same load-time asset/template/TPL closure. No Info is
retired, inserted, repaired or memoized. An existing stale record is rejected.
Four/five-role actors retain their source-selected hands and accessory materials.
Only a currently visible native-atlas role nominates an atlas.

The bundle helper reads the selected charbake key directly without initializing
its lazy cache. A compatible far bundle can nominate another atlas already in the
bounded near table. Far mismatch retains the normal near fallback. The helper
does not evaluate the crowd policy, bind bones or initialize skin streams.

The pre-scene hook uses the existing fenced package loader with an ordinary
current-frame pin. It checks successful upload, exact key, one non-paletted native
texture, dimensions and PVR address. It does not create a texture lease. The later
normal actor transaction still proves all ownership, materials, skeleton and draw
conditions. A preparation failure stays visible; it does not grant fallback or
native success. No current-frame pin is evicted specially for this feature.

The diagnostic reason numbers follow `Re4dcActorTexReason` in `actor_tex_prep.h`.
`ATEXP_PLAN`, `ATEXP_DECLINE`, `ATEXP_KEY` and `ATEXP_DONE` describe nomination and
upload. `ATEXP_LOAD_FAIL` records failure. `ATEXP_ACQUIRE` and `ATEXP_USED` correlate
prepared keys with the later ordinary texture lease acquisition. They do not prove
that a draw completed or that a framebuffer pixel was visible; use the original
actor/TA trace and framebuffer evidence for those claims.

Host verification:

```sh
python3 port/dreamcast/tests/test_actor_tex_prep.py
```

The harness compiles the actual lifetime/material readers, source enumeration,
immutable key mapper and pre-scene hook against synthetic source owners. It checks
retirement, reused serials, cyclic/missing roles, stale/pending assets, revoked or
ambiguous TPL owners, changed descriptor/sampler state, hidden roles, source hands
and accessories, variant/far differences and pre-scene guards. Memory snapshots
verify that pure proofs preserve lifetime records and source presentation entries;
loader tests verify no actor texture lease is acquired by preparation.

These host checks do not establish target ABI, performance or first-frame texture
acceptance. Required target checks are the disabled program identity, an enabled
cold first-frame run using the same assets and ordinary slab size, full TEX/TA and
native-owner checks, source-state continuity and original framebuffer review.
Physical Dreamcast timing remains separate from a Flycast run.
