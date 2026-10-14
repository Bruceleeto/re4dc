// Included beside the owning Pool/Chunk/work_at implementation. No copied pool
// layout, second registry, allocation, construction or retained object pointer.
#include "source_world_memory.inc"
namespace {
template<class T> bool sourceWorldPoolSlot(cManager<T>* manager,const void* value) {
    const auto address=reinterpret_cast<unsigned long>(value);
    if(!address || address%alignof(T) || !manager || !manager->pArray ||
       manager->pArrayPush || frozen(manager) || !manager->nArray ||
       manager->nArray>65536 || manager->size<sizeof(T))return false;
    if(!sparse(manager)) {
        if(manager->size>~0U/manager->nArray ||
           !sourceWorldAllocated(manager->pArray,manager->size*manager->nArray,true))return false;
        const auto base=reinterpret_cast<unsigned long>(manager->pArray);
        return address>=base && address-base<manager->size*manager->nArray &&
            (address-base)%manager->size==0;
    }
    auto* published=pool(manager);
    if(!sourceWorldAllocated(published,sizeof(Pool<T>),true))return false;
    if(published->capacity!=manager->nArray || published->heap<0 || published->heap>=MEM_HEAP_NUM ||
       Heap[published->heap].handle!=published->handle ||
       !sourceWorldAllocated(published,sizeof(Pool<T>)+published->capacity*sizeof(T*),true,published->heap))return false;
    unsigned slot=published->capacity;
    for(unsigned i=0;i<published->capacity;++i)if(published->slots()[i]==value) {
        if(slot!=published->capacity)return false;
        slot=i;
    }
    if(slot==published->capacity)return false;
    unsigned visited=0;
    for(auto* chunk=published->chunks;chunk;) {
        if(++visited>published->capacity ||
           !sourceWorldAllocated(chunk,sizeof(Chunk<T>),false,published->heap))return false;
        if(!chunk->count || chunk->first>=published->capacity ||
           chunk->count>published->capacity-chunk->first || chunk->count>~0U/sizeof(T) ||
           !sourceWorldAllocated(chunk->parts(),chunk->count*sizeof(T),false,published->heap))return false;
        if(slot>=chunk->first && slot-chunk->first<chunk->count)
            return chunk->parts()+(slot-chunk->first)==value && work_at(manager,slot)==value;
        chunk=chunk->next;
    }
    return false;
}
}
extern "C" int re4dc_source_world_pool(const void* value,unsigned type) {
    switch(type) {
    case 0:return sourceWorldPoolSlot<cObj>(&ObjMgr,value);
    case 1:return sourceWorldPoolSlot<cEm>(&EmMgr,value);
    case 2:return cModel::mm==&ModInfoMgr && sourceWorldPoolSlot<cModelInfo>(&ModInfoMgr,value);
    case 3:return cModel::pm==&PartsMgr && sourceWorldPoolSlot<cParts>(&PartsMgr,value);
    default:return 0;
    }
}
