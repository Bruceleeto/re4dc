#pragma once
// Root-owned recipe selector; no installed default is changed by this source.
#ifndef RE4DC_ACTOR_LEON_NATIVE_LOOK
#define RE4DC_ACTOR_LEON_NATIVE_LOOK 0
#endif
#if RE4DC_ACTOR_LEON_NATIVE_LOOK != 0 && RE4DC_ACTOR_LEON_NATIVE_LOOK != 1
#error ACTOR_LEON_NATIVE_LOOK must be0(source policy) or1(review candidate)
#endif
struct Re4dcActorPlan;
enum Re4dcActorRunCapability : unsigned {
    RE4DC_ACTOR_RUN_LEASES=1, // exact atlas + two source-colour/mask pairs
    RE4DC_ACTOR_RUN_ORDER=2,  // fourteen runs, original role7 second OT group
    RE4DC_ACTOR_RUN_HAIR_TR_NOWRITE=4 // explicit DC candidate approximation
};
// Implemented by hair-adapter-r2. These are concrete plan/backend checks,
// not a user-supplied bitmap that can make a missing backend appear ready.
extern "C" unsigned re4dc_actor_material_runs_capability(const Re4dcActorPlan*);
