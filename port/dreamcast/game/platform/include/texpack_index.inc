// texpack_index.inc - TEX_PACK index (included by native_ui.cpp inside `namespace {`, TEX_PACK=1 builds; compiled
// unchanged by the host test tests/test_texpack_index.py with a mock reader).
// Needs: Key {crc, fnv}, mutex_t / MUTEX_INITIALIZER / mutex_lock / mutex_unlock, re4dc_log,
// re4dc::texture::read_file_range (texture_package.hpp) and its RangeRead result.
//
// dc/tex.pak (tools/d367/texpack.py): every dc/tex/<n>/<crc>-<fnv>.re4tex of the disc in one file, so a load seeks
// inside one file instead of a lookup in a ~200-entry directory per texture (IO_PROBE, r100 entry: 130 opens = 3.9
// of 6.5 s, 234 directory-sector reads; on a GD-ROM each is a seek to the directory area and back). Layout: 2048-byte
// header {"RE4PAK1\0", version 1, count, index_offset, data_offset, index_crc32}, the index sorted by (crc, fnv) as
// {crc, fnv, offset, size} (128 per sector), then the packages at 2048-byte boundaries, byte for byte the .re4tex
// files. RAM: the first key of each index sector; a lookup reads one sector.
//
// Failure policy (architect review 2026-10-03, P1/P2):
// - Pack absent (fs_open fails): per-file loads, as before. A key not in a ready pack (texlow, a missing file)
//   also takes the per-file path.
// - A read error (header, index or a lookup's sector) is transient: find() returns kError, the caller loads
//   nothing this time and does not remember the key as missing. Init is retried kRetryNow times, then once per
//   room load (room_loaded()). Nothing is published until a complete init.
// - An invalid pack (header fields, count, extents, key order, index CRC) is terminal: one loud log line, then
//   per-file loads (a packed-only disc will miss its packed textures; that disc is broken media).
namespace texpack {
constexpr const char* kPath="/cd/dc/tex.pak";
constexpr unsigned kMaxSectors=64;               // 8,192 entries (texpack.py enforces the same cap)
constexpr unsigned kMaxCount=kMaxSectors*128;
constexpr unsigned kRetryNow=3;                  // attempts after a read error before waiting for a room load
enum State { kUntried, kReady, kAbsent, kInvalid, kRetry };
enum Result { kNotInPack, kFound, kError };      // kNotInPack: per-file path (no usable pack, or key not in it)
mutex_t lock=MUTEX_INITIALIZER;
State state=kUntried;
unsigned count=0,data_offset=0,sectors=0,cached=~0U,hits=0,misses=0,errors=0;
unsigned attempts=0,room_gen=0,attempt_gen=0;
unsigned long long pack_bytes=0;
Key first[kMaxSectors];
alignas(32) unsigned char sector[2048];    // read by re4dc::texture::read_file_range: its own handle per read
unsigned word(const unsigned char* p){return p[0]|p[1]<<8|p[2]<<16|unsigned(p[3])<<24;}
bool less(const Key& a,const Key& b){return a.crc<b.crc || (a.crc==b.crc && a.fnv<b.fnv);}
// zlib crc32 (texpack.py writes zlib.crc32 of the padded index): bitwise, init only (20-26 sectors).
unsigned crc_update(unsigned crc,const unsigned char* p,unsigned n){
    for(unsigned i=0;i<n;++i){crc^=p[i];for(unsigned b=0;b<8;++b)crc=(crc>>1)^(0xedb88320U&(0U-(crc&1U)));}
    return crc;
}
re4dc::texture::RangeRead read_sector(unsigned offset,unsigned long long* bytes=nullptr){
#if defined(RE4DC_TEX_PACK_FAULT) && RE4DC_TEX_PACK_FAULT
    // Test only (game30.mk TEX_PACK_FAULT=N, default 0): the first N pack reads fail as read errors.
    static unsigned faults=RE4DC_TEX_PACK_FAULT;
    if(faults){--faults;re4dc_log("tex pack: test fault: read at %u fails (%u left)\n",offset,faults);
        return re4dc::texture::RangeRead::io_error;}
#endif
    return re4dc::texture::read_file_range(kPath,offset,sector,2048,bytes);
}
bool invalid(const char* why,unsigned a,unsigned b){
    re4dc_log("tex pack: %s INVALID: %s (0x%x, 0x%x); the pack is not used, per-file loads\n",kPath,why,a,b);
    state=kInvalid;cached=~0U;return false;
}
bool read_failed(const char* what,unsigned offset){
    ++attempts;++errors;attempt_gen=room_gen;state=kRetry;cached=~0U;
    re4dc_log("tex pack: %s read error (%s at %u), attempt %u; %s\n",kPath,what,offset,attempts,
              attempts<kRetryNow?"retrying":"retrying at the next room load");
    return false;
}
// Complete init or nothing: header and every index sector validated, index CRC checked, then published.
bool open_locked(){
    if(state==kReady)return true;
    if(state==kAbsent || state==kInvalid)return false;
    if(state==kRetry && attempts>=kRetryNow && attempt_gen==room_gen)return false;
    unsigned long long total=0;
    const re4dc::texture::RangeRead h=read_sector(0,&total);
    if(h==re4dc::texture::RangeRead::absent){
        re4dc_log("tex pack: %s not on the disc, per-file loads\n",kPath);state=kAbsent;return false;
    }
    if(h!=re4dc::texture::RangeRead::ok)return read_failed("header",0);
    if(std::memcmp(sector,"RE4PAK1\0",8) || word(sector+8)!=1)return invalid("magic/version",word(sector+8),0);
    const unsigned n=word(sector+12),index_at=word(sector+16),data_at=word(sector+20),crc=word(sector+24);
    if(n<1 || n>kMaxCount)return invalid("count",n,kMaxCount);           // before any multiplication
    if(index_at!=2048)return invalid("index offset",index_at,2048);
    const unsigned nsec=(n*16U+2047U)/2048U;
    const unsigned long long index_end=2048ULL+2048ULL*nsec;
    if(data_at<index_end || data_at%2048U || data_at>total)return invalid("data offset",data_at,unsigned(index_end));
    Key keys[kMaxSectors];
    Key prev{};unsigned crc_run=0xffffffffU;
    for(unsigned s=0;s<nsec;++s){
        if(read_sector(2048U*(s+1))!=re4dc::texture::RangeRead::ok)return read_failed("index",2048U*(s+1));
        crc_run=crc_update(crc_run,sector,2048);
        const unsigned m=std::min(128U,n-128U*s);
        for(unsigned i=0;i<m;++i){
            const unsigned char* e=sector+16*i;
            const Key k{word(e),word(e+4)};const unsigned off=word(e+8),size=word(e+12);
            if((s|i) && !less(prev,k))return invalid("key order at entry",128*s+i,k.crc);
            if(!size || off%2048U || off<data_at || (unsigned long long)off+size>total)
                return invalid("entry extent",128*s+i,off);
            if(!i)keys[s]=k;
            prev=k;
        }
    }
    if(~crc_run!=crc)return invalid("index crc",~crc_run,crc);
    for(unsigned s=0;s<nsec;++s)first[s]=keys[s];
    count=n;data_offset=data_at;sectors=nsec;pack_bytes=total;cached=nsec-1;state=kReady;
    re4dc_log("tex pack: %s count=%u index_sectors=%u bytes=%llu%s\n",kPath,count,sectors,pack_bytes,
              attempts?" (after read errors)":"");
    return true;
}
// A room load re-arms one init attempt after kRetryNow failed ones (native_ui.cpp re4dc_ui_retire_room).
void room_loaded(){mutex_lock(&lock);++room_gen;mutex_unlock(&lock);}
// The key's package in the pack: kFound with its offset and size; kNotInPack for the per-file path; kError for a
// read error (load nothing now, do not remember the key as missing).
Result find(const Key& key,unsigned& offset,unsigned& size){
    mutex_lock(&lock);
    Result r=kNotInPack;
    if(open_locked()){
        unsigned s=0;
        while(s+1<sectors && !less(key,first[s+1]))++s;
        if(!less(key,first[s])){
            if(cached!=s){
                cached=~0U;
                if(read_sector(2048U*(s+1))!=re4dc::texture::RangeRead::ok || word(sector)!=first[s].crc ||
                   word(sector+4)!=first[s].fnv){
                    ++errors;r=kError;
                    re4dc_log("tex pack: %s index sector %u read error (lookup %08x-%08x); retried at the next use\n",
                              kPath,s,key.crc,key.fnv);
                } else cached=s;
            }
            if(cached==s){
                unsigned lo=0,hi=std::min(128U,count-128U*s);
                while(lo<hi){
                    const unsigned mid=(lo+hi)/2;const unsigned char* e=sector+16*mid;
                    const Key k{word(e),word(e+4)};
                    if(k==key){offset=word(e+8);size=word(e+12);r=kFound;break;}
                    if(less(k,key))lo=mid+1;else hi=mid;
                }
            }
        }
    } else if(state==kRetry) r=kError;
    if(r==kFound)++hits;else if(r==kNotInPack)++misses;
    mutex_unlock(&lock);
    return r;
}
}
