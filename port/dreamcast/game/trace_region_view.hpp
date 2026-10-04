#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdlib>

// Diagnostic projection over storage owned by the existing sub-screen backing store.
// Backend::append/read preserve exact raw bytes; this class retains only a bounded index.
template<unsigned SpanCapacity,class Backend>
struct TraceRegionView {
    struct Span { std::uintptr_t start; unsigned bytes, offset; };
    Span spans[SpanCapacity];
    Backend backing;
    std::uintptr_t lo=0,hi=0;
    unsigned used=0,count=0;
    bool capturing=false,active=false;
    bool begin(const void* base,unsigned bytes) {
        if(active || capturing)return false;
        lo=reinterpret_cast<std::uintptr_t>(base);hi=lo+bytes;
        if(hi<lo)return false;
        used=count=0;capturing=true;return true;
    }
    bool capture(const void* ptr,unsigned bytes) {
        if(!capturing)return true;
        const auto a=reinterpret_cast<std::uintptr_t>(ptr);
        if(a+bytes<a)return false;
        const auto start=a<lo?lo:a,end=a+bytes>hi?hi:a+bytes;
        if(start>=end)return true;
        const unsigned n=unsigned(end-start);
        if(count==SpanCapacity || n>~0u-used)return false;
        unsigned offset;
        if(!backing.append(reinterpret_cast<const void*>(start),n,&offset))return false;
        spans[count++]={start,n,offset};used+=n;return true;
    }
    static int compare(const void* av,const void* bv) {
        const auto& a=*static_cast<const Span*>(av);
        const auto& b=*static_cast<const Span*>(bv);
        if(a.start!=b.start)return a.start<b.start?-1:1;
        return a.bytes<b.bytes?-1:a.bytes>b.bytes?1:0;
    }
    bool seal() {
        if(!capturing || active)return false;
        std::qsort(spans,count,sizeof(Span),compare);
        capturing=false;active=true;return true;
    }
    const Span* find(std::uintptr_t at) const {
        unsigned a=0,b=count;
        while(a<b){const unsigned m=a+(b-a)/2;if(spans[m].start<=at)a=m+1;else b=m;}
        while(a){const Span& s=spans[--a];if(at-s.start<s.bytes)return &s;}
        return nullptr;
    }
    bool copy(void* dst,const void* src,unsigned bytes) const {
        auto at=reinterpret_cast<std::uintptr_t>(src);
        if(at+bytes<at)return false;
        if(!active){std::memcpy(dst,src,bytes);return true;}
        auto* out=static_cast<unsigned char*>(dst);
        while(bytes) {
            unsigned n=bytes;
            if(at<lo) {
                if(lo-at<n)n=unsigned(lo-at);
                std::memcpy(out,reinterpret_cast<const void*>(at),n);
            } else if(at>=hi)std::memcpy(out,reinterpret_cast<const void*>(at),n);
            else {
                const Span* s=find(at);if(!s)return false;
                if(s->start+s->bytes-at<n)n=unsigned(s->start+s->bytes-at);
                if(hi-at<n)n=unsigned(hi-at);
                if(!backing.read(out,s->offset+unsigned(at-s->start),n))return false;
            }
            out+=n;at+=n;bytes-=n;
        }
        return true;
    }
    bool restored() const {
        if(!active)return false;
        unsigned char buf[32];
        for(unsigned i=0;i<count;++i) {
            const Span& s=spans[i];
            for(unsigned off=0;off<s.bytes;) {
                const unsigned n=s.bytes-off<sizeof(buf)?s.bytes-off:sizeof(buf);
                if(!backing.read(buf,s.offset+off,n) ||
                   std::memcmp(reinterpret_cast<const void*>(s.start+off),buf,n))return false;
                off+=n;
            }
        }
        return true;
    }
    void end(){active=capturing=false;lo=hi=0;}
};
