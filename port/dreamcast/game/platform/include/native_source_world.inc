// Read-only access to the already adopted r200 world. Package publication and
// retirement advance a token; a same-address reload never revives an old frame.
extern "C" int re4dc_ps2_source_package(unsigned* generation) {
    if(!generation || !sourceWorldPackageGeneration || sourceWorldPackageGeneration==~0U ||
       !ps2w.storage || !ps2w.parts || !ps2w.placements || !ps2w.lut || !ps2w.gather ||
       ps2w.room!=0x200 || ps2w.want!=0x200 || ps2w.nplacements!=90 ||
       sourceWorldSidecarCrc!=4040448078U || !dyn::ids || dyn::nids!=90)return 0;
    const auto& h=ps2w.package.header();
    if(h.version!=3 || h.bytes!=510048U || h.crc!=3459209119U || h.mesh_count!=63 || h.part_count!=152)return 0;
    *generation=sourceWorldPackageGeneration;return 1;
}
extern "C" int re4dc_ps2_source_texture(unsigned generation,Re4dcSourceWorldTexture* out) {
    unsigned current=0;
    if(!out || !re4dc_ps2_source_package(&current) || current!=generation)return 0;
    const auto& q=ps2w.parts[13];
    if(q.crc!=0xfa6fe38cU || q.fnv!=0x1a02365fU || q.width!=256 || q.height!=256 ||
       q.pass!=2 || q.texture!=17 || q.reserved)return 0;
    *out={current,q.crc,q.fnv,q.width,q.height,131072U};return 1;
}
namespace {
unsigned sourceWorldImageFrame=~0U,sourceWorldImageGeneration;
int sourceWorldImageResult;
}
extern "C" int re4dc_ps2_source_draw(unsigned generation) {
    unsigned current=0;const unsigned frame=re4dc_ui_frame();
    if(!re4dc_ps2_source_package(&current) || current!=generation)return 0;
    if(sourceWorldImageFrame==frame)return sourceWorldImageGeneration==generation?sourceWorldImageResult:0;
    float view[12],projection[7],viewport[6];
    if(!re4dc_coarse_source_camera(view,projection,viewport))return 0;
    sourceWorldImageFrame=frame;sourceWorldImageGeneration=generation;
    re4dc_ps2_mesh_camera(view,projection,viewport);
    const int drawn=re4dc_ps2_world_source_draw();
    const auto& c=ps2w.count[0];
    // A partial draw cannot fall back to GC geometry. Fail the scene explicitly.
    sourceWorldImageResult=drawn && !c.fallback && !c.aborts?1:-1;
    if(sourceWorldImageResult<0)re4dc_model_packet_abort();
    re4dc_log("PS2SOURCE_DRAW f=%u gen=%u result=%d native=%u fallback=%u abort=%u\n",
        frame,generation,sourceWorldImageResult,c.native,c.fallback,c.aborts);
    return sourceWorldImageResult;
}
extern "C" int re4dc_ps2_source_passes_complete() {
    for(const auto& count:ps2w.count)if(count.fallback || count.aborts)return 0;
    return 1;
}
