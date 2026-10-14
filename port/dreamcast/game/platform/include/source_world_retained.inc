// Source heap 1 keeps its allocated prefix when 1 -> 2 retires only the
// allocator descriptor. Publish that exact lifetime for OT buckets only.
// Included by main_mem beside the actual descriptor/checker-list owners.
namespace {
struct SourceWorldRetainedPrefix {
    OSHeapCell* head=nullptr;
    unsigned long begin=0,end=0;
    unsigned epoch=1;
    bool live=false;
} sourceWorldRetained;
unsigned sourceWorldHeapMutation=1;
unsigned sourceWorldNextEpoch(unsigned value) { return ++value ? value : 1; }
void sourceWorldHeapTouched() { sourceWorldHeapMutation=sourceWorldNextEpoch(sourceWorldHeapMutation); }
void sourceWorldRetainedRevoke() {
    sourceWorldRetained.epoch=sourceWorldNextEpoch(sourceWorldRetained.epoch);
    sourceWorldRetained.live=false;sourceWorldRetained.head=nullptr;
    sourceWorldRetained.begin=sourceWorldRetained.end=0;
}
bool sourceWorldRetainedOverlap(unsigned long begin,unsigned long end) {
    return sourceWorldRetained.live && begin<sourceWorldRetained.end && sourceWorldRetained.begin<end;
}
void sourceWorldRetainedReset() { sourceWorldHeapTouched();sourceWorldRetainedRevoke(); }
void sourceWorldRetainedSuspend(int no) {
    sourceWorldHeapTouched();if(no==1)sourceWorldRetainedRevoke();
}
void sourceWorldRetainedDestroy(int no) {
    sourceWorldHeapTouched();if(no==1)sourceWorldRetainedRevoke();
}
void sourceWorldRetainedCreate(int no,unsigned long begin,unsigned long end) {
    sourceWorldHeapTouched();
    if(no==1 || begin>=end || sourceWorldRetainedOverlap(begin,end))sourceWorldRetainedRevoke();
}
void sourceWorldRetainedRestore(int no) {
    sourceWorldHeapTouched();
    if(no==1 || sourceWorldRetainedOverlap(Heap[no].start,Heap[no].end))sourceWorldRetainedRevoke();
}
void sourceWorldRetainedFree(const void* value) {
    sourceWorldHeapTouched();const auto address=reinterpret_cast<unsigned long>(value);
    // Revoke before even the source debug-free header read/payload wipe.
    if(sourceWorldRetained.live && address>=sourceWorldRetained.begin &&
       (address<=sourceWorldRetained.end || address-sourceWorldRetained.end<32))sourceWorldRetainedRevoke();
}
bool sourceWorldRetainedArena() {
    const auto begin=(re4dc_mem.heap+31UL)&~31UL;
    return re4dc_mem.heap && begin>=re4dc_mem.heap && begin<re4dc_mem.heap_end &&
        MEM_HEAP_NUM*sizeof(OSHeapDescriptor)<=re4dc_mem.heap_end-begin &&
        reinterpret_cast<unsigned long>(HeapHead)==begin;
}
bool sourceWorldRetainedOwners(unsigned long begin,unsigned long end,int ignored=-1) {
    for(int i=0;i<MEM_HEAP_NUM;++i) {
        const auto& h=Heap[i];if(i==ignored || h.handle<0)continue;
        // Suspended descriptors still own their entire range.
        if(h.handle>=MEM_HEAP_NUM || h.start>=h.end ||
           h.start<re4dc_mem.heap || h.end>re4dc_mem.heap_end ||
           (begin<h.end && h.start<end))return false;
    }
    return true;
}
// Validate the complete source allocation chain before its first unbounded
// source traversal. Each next pointer is checked before any field is read.
bool sourceWorldRetainedChain(OSHeapCell* head,unsigned long begin,unsigned long end,
                              unsigned long* highest,const void* value=nullptr,unsigned bytes=0) {
    if(!sourceWorldRetainedArena() || begin>=end || (begin&31UL) || (end&31UL) ||
       begin<re4dc_mem.heap || end>re4dc_mem.heap_end)return false;
    unsigned visited=0;unsigned long maximum=begin;
    OSHeapCell* previous=nullptr;bool found=false;
    const auto address=reinterpret_cast<unsigned long>(value);
    for(auto* cell=head;cell;) {
        const auto start=reinterpret_cast<unsigned long>(cell);
        if(++visited>65536 || (start&31UL) || start<begin || start>=end ||
           sizeof(OSHeapCell)>end-start)return false;
        const auto size=cell->size;
        if(size<64 || (unsigned(size)&31U) || unsigned(size)>end-start || cell->prev!=previous)return false;
        const auto finish=start+unsigned(size),payload=start+32UL;
        if(finish>maximum)maximum=finish;
        if(value && address==payload) {
            // MEM_ALLOC places MAD after the rounded request. OSAlloc may
            // donate an unsplit 32-byte tail; neither MAD nor that tail is OT.
            if(found || !bytes || bytes>~0U-31U)return false;
            const unsigned rounded=(bytes+31U)&~31U;
            if(unsigned(size)<64 || rounded>unsigned(size)-64 || unsigned(size)-64-rounded>32)return false;
            const auto* tag=reinterpret_cast<const unsigned char*>(payload+rounded);
            if(tag[0] || tag[1]!='M' || tag[2]!='A' || tag[3]!='D')return false;
            found=true;
        }
        previous=cell;cell=cell->next;
    }
    if(highest)*highest=maximum;
    return value ? found : true;
}
struct SourceWorldRetainedTransfer {
    OSHeapCell* head=nullptr;
    unsigned long begin=0,end=0;
    unsigned mutation=0,expected=0;
    bool valid=false;
};
bool sourceWorldRetainedCapture(int from,int to,SourceWorldRetainedTransfer* out) {
    if(from!=1 || to!=2 || Heap[1].handle<0)return true;
    const auto& h=Heap[1];
    if(!sourceWorldRetainedArena() || h.handle>=MEM_HEAP_NUM || h.status ||
       HeapHead[h.handle].size<=0)return false;
    auto* head=HeapHead[h.handle].allocated;
    if(!head)return true;
    unsigned long end=0;
    if(!sourceWorldRetainedChain(head,h.start,h.end,&end) ||
       !sourceWorldRetainedOwners(h.start,end,1))return false;
    out->head=head;out->begin=h.start;out->end=end;out->mutation=sourceWorldHeapMutation;
    // Exactly the ordinary Destroy(from), Create(to), and its optional
    // Destroy(to) may occur before publication. Any reentry invalidates it.
    out->expected=2+(Heap[to].handle>=0);out->valid=true;return true;
}
void sourceWorldRetainedPublish(const SourceWorldRetainedTransfer& transfer,int success) {
    if(!transfer.valid)return;
    unsigned expected=transfer.mutation;
    for(unsigned i=0;i<transfer.expected;++i)expected=sourceWorldNextEpoch(expected);
    unsigned long highest=0;
    if(!success || sourceWorldHeapMutation!=expected || Heap[1].handle!=-1 || Heap[1].status ||
       Heap[2].handle<0 || Heap[2].start!=transfer.end ||
       !sourceWorldRetainedOwners(transfer.begin,transfer.end) ||
       !sourceWorldRetainedChain(transfer.head,transfer.begin,transfer.end,&highest) || highest!=transfer.end)return;
    sourceWorldRetained.head=transfer.head;sourceWorldRetained.begin=transfer.begin;sourceWorldRetained.end=transfer.end;
    sourceWorldRetained.epoch=sourceWorldNextEpoch(sourceWorldRetained.epoch);sourceWorldRetained.live=true;
}
}
extern "C" unsigned re4dc_source_world_ot_epoch() { return sourceWorldRetained.epoch; }
extern "C" void re4dc_source_world_ot_memory(Re4dcSourceWorldOtMemory* out) {
    *out={sourceWorldRetained.begin,sourceWorldRetained.end,sourceWorldRetained.epoch,unsigned(sourceWorldRetained.live)};
}
extern "C" int re4dc_source_world_ot_retained(const void* value,unsigned bytes) {
    const auto& p=sourceWorldRetained;
    if(!p.live || Heap[1].handle!=-1 || Heap[1].status || Heap[1].start!=p.begin ||
       !sourceWorldRetainedOwners(p.begin,p.end))return 0;
    unsigned long highest=0;
    return sourceWorldRetainedChain(p.head,p.begin,p.end,&highest,value,bytes) && highest==p.end;
}
