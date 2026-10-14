// Read only queries of the source allocator's current publication. A RAM
// address alone is never permission to borrow an OT node or source pool.
#ifndef RE4DC_SOURCE_WORLD_MEMORY_INC
#define RE4DC_SOURCE_WORLD_MEMORY_INC
namespace {
bool sourceWorldAllocated(const void* value,unsigned bytes,bool exact,int only=-1) {
    const auto address=reinterpret_cast<unsigned long>(value);
    if(!address || !bytes || !re4dc_mem.heap || re4dc_mem.heap>=re4dc_mem.heap_end)return false;
    const auto head=(re4dc_mem.heap+31UL)&~31UL;
    if(head<re4dc_mem.heap || head>re4dc_mem.heap_end ||
       MEM_HEAP_NUM*sizeof(OSHeapDescriptor)>re4dc_mem.heap_end-head)return false;
    const auto* descriptors=reinterpret_cast<const OSHeapDescriptor*>(head);
    for(int h=0;h<MEM_HEAP_NUM;++h) {
        if(only>=0 && h!=only)continue;
        const auto& owner=Heap[h];
        if(owner.handle<0 || owner.handle>=MEM_HEAP_NUM || owner.status ||
           owner.start>=owner.end || address<owner.start || address>=owner.end ||
           bytes>owner.end-address)continue;
        const auto& descriptor=descriptors[owner.handle];
        if(descriptor.size<=0)continue;
        unsigned visited=0;
        for(const OSHeapCell* cell=descriptor.allocated;cell;) {
            const auto start=reinterpret_cast<unsigned long>(cell);
            if(++visited>65536 || (start&31UL) || start<owner.start || start>=owner.end ||
               sizeof(OSHeapCell)>owner.end-start)return false;
            const auto size=cell->size;
            if(size<int(sizeof(OSHeapCell)) || unsigned(size)>owner.end-start)return false;
            const auto payload=start+sizeof(OSHeapCell),end=start+unsigned(size);
            if(address>=payload && address<=end && bytes<=end-address && (!exact || address==payload))return true;
            cell=cell->next;
        }
    }
    return false;
}
}
#endif
