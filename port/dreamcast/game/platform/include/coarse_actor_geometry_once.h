#pragma once
#include "coarse_actor_preflight.h"

// These IDs are assigned ONLY by the compiled private asset plan factories.
// 1..8: Leon roles; 9..28: five Ganado appearances x four roles;
// 29..42: the fourteen source-ordered Leon hair material runs.
// 43..46: exact source em15 hands451/456, hood467 and sack484.
// Every referenced byte array must be const, linked into the executable and
// live for the entire process. This API must never be used for source archive,
// streamed, relocated, mutable, or frame-allocated bytes.
extern "C" re4dc_source::BlobError re4dc_actor_immutable_chunk_proof(
    unsigned asset_id, const re4dc_source::ChunkInput&,
    re4dc_source::ChunkProof&);
