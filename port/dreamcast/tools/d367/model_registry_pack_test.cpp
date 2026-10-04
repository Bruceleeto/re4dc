// model_registry_pack_test.cpp (host; built and driven by model_registry_pack_test.py): runs the target's own room
// package validation (game/coarse_actor_registry_pack_check.inc, NATIVE_MODEL_REGISTRY_PACK=1) on package files.
// The record types are the target's (extracted from game/coarse_actor_material.inc and coarse_actor_owner_registry.inc
// by the driver into pack_test_types.h); the reviewed base identity rows are game/actor_material_records.inc, so the
// room row capacities (kRoomRoles / kRoomBlobs) are the target's too.
//   model_registry_pack_test <room hex> <package>...   prints "<file> <why> <detail>" per package
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#define RE4DC_NATIVE_MODEL_REGISTRY 1
#define RE4DC_NATIVE_MODEL_REGISTRY_PACK 1
#include "coarse_skin.h"
#include "pack_test_types.h"
#include "coarse_actor_registry_pack_check.inc"
int main(int argc,char** argv) {
    if(argc<3){std::fprintf(stderr,"usage: %s <room hex> <package>...\n",argv[0]);return 2;}
    const unsigned room=unsigned(std::strtoul(argv[1],nullptr,16));
    for(int a=2;a<argc;++a) {
        FILE* f=std::fopen(argv[a],"rb");
        if(!f){std::printf("%s missing 0\n",argv[a]);continue;}
        std::vector<unsigned char> raw;unsigned char buf[4096];size_t n;
        while((n=std::fread(buf,1,sizeof(buf),f))>0)raw.insert(raw.end(),buf,buf+n);
        std::fclose(f);
        // The target reads into a 32-byte aligned cell.
        void* mem=nullptr;
        if(posix_memalign(&mem,32,raw.size()+32)){std::printf("%s alloc 0\n",argv[a]);continue;}
        std::memcpy(mem,raw.data(),raw.size());
        unsigned detail=0;
        const PackWhy why=raw.size()>kPackMaxBytes?kPwSize:pack_validate(static_cast<unsigned char*>(mem),unsigned(raw.size()),room,detail);
        std::printf("%s %s %u\n",argv[a],kPackWhy[why],detail);
        std::free(mem);
    }
    return 0;
}
