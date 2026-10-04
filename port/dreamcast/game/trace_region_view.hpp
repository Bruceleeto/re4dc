#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <type_traits>

// Trace-only compact index. Source offsets are relative to the saved window. The backing
// store is at most 8 MiB VRAM; a checked 24-bit offset leaves 8 bits for length minus one.
// Requests over 256 bytes split into independent spans, preserving exact byte reads.
struct TraceSpan {
    std::uint32_t start, encoded;
    unsigned bytes() const { return (encoded >> 24) + 1; }
    unsigned offset() const { return encoded & 0xffffffU; }
};
static_assert(sizeof(TraceSpan)==8,"trace index budget");

// Backend::kIndexInBacking (optional, default false): the backend also keeps the span index, as 8-byte
// entries behind index_push/index_read/index_write, inside its own bounded store.
template<class B,class=void> struct TraceIndexInBacking : std::false_type {};
template<class B> struct TraceIndexInBacking<B,std::void_t<decltype(B::kIndexInBacking)>>
    : std::bool_constant<B::kIndexInBacking> {};

// Index in this object: SpanCapacity entries.
template<unsigned SpanCapacity,bool InBacking> struct TraceSpanIndex {
    TraceSpan spans[SpanCapacity];
};
// Index in the backend: only the start of every kFenceStride-th sorted entry (narrows each lookup to one
// stride of backend entries) and the last lookup's answer.
template<unsigned SpanCapacity> struct TraceSpanIndex<SpanCapacity,true> {
    static constexpr unsigned kFenceStride=32;
    std::uint32_t fences[SpanCapacity/kFenceStride+1];
    mutable TraceSpan hit{};
    mutable std::uint32_t hit_next=0;  // start of the entry after `hit`, unless hit_last
    mutable bool hit_valid=false,hit_last=false;
};

// Diagnostic projection over storage owned by the existing sub-screen backing store.
// Backend::append/read preserve exact raw bytes; this class retains only a bounded index, or with
// kIndexInBacking a fence table, sorting the backend's entries in place through its read/write calls.
template<unsigned SpanCapacity,class Backend>
struct TraceRegionView : TraceSpanIndex<SpanCapacity,TraceIndexInBacking<Backend>::value> {
    using Span=TraceSpan;
    static constexpr bool kIndexInBacking=TraceIndexInBacking<Backend>::value;
    Backend backing;
    std::uintptr_t lo=0,hi=0;
    unsigned used=0,count=0;
    bool capturing=false,active=false;
    bool begin(const void* base,unsigned bytes) {
        if(active || capturing)return false;
        lo=reinterpret_cast<std::uintptr_t>(base);hi=lo+bytes;
        if(hi<lo)return false;
        used=count=0;forget();capturing=true;return true;
    }
    bool capture(const void* ptr,unsigned bytes) {
        if(!capturing)return true;
        const auto a=reinterpret_cast<std::uintptr_t>(ptr);
        if(a+bytes<a)return false;
        const auto start=a<lo?lo:a,end=a+bytes>hi?hi:a+bytes;
        if(start>=end)return true;
        auto at=start;
        while(at<end) {
            const unsigned n=end-at>256?256:unsigned(end-at);
            if(count==SpanCapacity || n>~0u-used || at-lo>0xffffffffULL)return false;
            unsigned offset;
            if(!backing.append(reinterpret_cast<const void*>(at),n,&offset) || offset>0xffffffU)return false;
            const Span s{std::uint32_t(at-lo),offset|((n-1)<<24)};
            if constexpr(kIndexInBacking) {
                if(!backing.index_push(&s))return false;
            } else this->spans[count]=s;
            ++count;
            used+=n;at+=n;
        }
        return true;
    }
    static int compare(const void* av,const void* bv) {
        const auto& a=*static_cast<const Span*>(av);
        const auto& b=*static_cast<const Span*>(bv);
        if(a.start!=b.start)return a.start<b.start?-1:1;
        return a.bytes()<b.bytes()?-1:a.bytes()>b.bytes()?1:0;
    }
    // The same order, completed by the backing offset (distinct for every span), so the in-place sort's
    // result is unique. Entries equal under compare() hold bytes captured from one unchanged source range.
    static bool less(const Span& a,const Span& b) {
        if(const int c=compare(&a,&b))return c<0;
        return a.offset()<b.offset();
    }
    bool seal() {
        if(!capturing || active)return false;
        if constexpr(kIndexInBacking) {
            if(!sort_backing())return false;
        } else std::qsort(this->spans,count,sizeof(Span),compare);
        capturing=false;active=true;return true;
    }
    const Span* find(std::uintptr_t at) const {
        if(at<lo || at>=hi)return nullptr;
        const auto relative=at-lo;
        if constexpr(kIndexInBacking) {
            // Exact: `hit` covers relative and the next entry starts after it, so the search below
            // would end at the same entry.
            if(this->hit_valid && relative-this->hit.start<this->hit.bytes() &&
               (this->hit_last || this->hit_next>relative))return &this->hit;
            const unsigned fences=(count+this->kFenceStride-1)/this->kFenceStride;
            unsigned a=0,b=fences;
            while(a<b){const unsigned m=a+(b-a)/2;if(this->fences[m]<=relative)a=m+1;else b=m;}
            if(!a)return nullptr;
            // The first entry starting after relative lies in ((a-1)*stride, min(a*stride,count)].
            b=a*this->kFenceStride<count?a*this->kFenceStride:count;
            a=(a-1)*this->kFenceStride+1;
            Span s;
            while(a<b){const unsigned m=a+(b-a)/2;if(!entry(m,s))return nullptr;if(s.start<=relative)a=m+1;else b=m;}
            while(a) {
                if(!entry(--a,s))return nullptr;
                if(relative-s.start<s.bytes()) {
                    Span next{};
                    const bool last=a+1==count;
                    if(!last && !entry(a+1,next))return nullptr;
                    this->hit=s;this->hit_next=next.start;this->hit_last=last;this->hit_valid=true;
                    return &this->hit;
                }
            }
            return nullptr;
        } else {
            unsigned a=0,b=count;
            while(a<b){const unsigned m=a+(b-a)/2;if(this->spans[m].start<=relative)a=m+1;else b=m;}
            while(a){const Span& s=this->spans[--a];if(relative-s.start<s.bytes())return &s;}
            return nullptr;
        }
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
                if(lo+s->start+s->bytes()-at<n)n=unsigned(lo+s->start+s->bytes()-at);
                if(hi-at<n)n=unsigned(hi-at);
                if(!backing.read(out,s->offset()+unsigned(at-lo-s->start),n))return false;
            }
            out+=n;at+=n;bytes-=n;
        }
        return true;
    }
    bool restored() const {
        if(!active)return false;
        unsigned char buf[32];
        for(unsigned i=0;i<count;++i) {
            Span s;
            if(!entry(i,s))return false;
            for(unsigned off=0;off<s.bytes();) {
                const unsigned n=s.bytes()-off<sizeof(buf)?s.bytes()-off:sizeof(buf);
                if(!backing.read(buf,s.offset()+off,n) ||
                   std::memcmp(reinterpret_cast<const void*>(lo+s.start+off),buf,n))return false;
                off+=n;
            }
        }
        return true;
    }
    void end(){active=capturing=false;lo=hi=0;forget();}
private:
    bool entry(unsigned i,Span& s) const {
        if constexpr(kIndexInBacking)return i<count && backing.index_read(i,&s);
        else {if(i>=count)return false;s=this->spans[i];return true;}
    }
    void forget() {
        if constexpr(kIndexInBacking)this->hit_valid=false;
    }
    // Heapsort of the backend's entries by less(), one entry moved per heap level (the sifted entry is
    // held here and written once), then one pass that checks the order and records the fences.
    // Any refused backend access fails the seal.
    bool sift(unsigned i,unsigned n,const Span& v) {
        for(;;) {
            unsigned c=2*i+1;
            if(c>=n)break;
            Span cv,r;
            if(!backing.index_read(c,&cv))return false;
            if(c+1<n) {
                if(!backing.index_read(c+1,&r))return false;
                if(less(cv,r)){cv=r;++c;}
            }
            if(!less(v,cv))break;
            if(!backing.index_write(i,&cv))return false;
            i=c;
        }
        return backing.index_write(i,&v);
    }
    bool sort_backing() {
        Span v,top;
        for(unsigned i=count/2;i--;)
            if(!backing.index_read(i,&v) || !sift(i,count,v))return false;
        for(unsigned n=count;n>1;) {
            --n;
            if(!backing.index_read(0,&top) || !backing.index_read(n,&v) ||
               !backing.index_write(n,&top) || !sift(0,n,v))return false;
        }
        Span prev{};
        for(unsigned i=0;i<count;++i) {
            if(!backing.index_read(i,&v) || (i && less(v,prev)))return false;
            if(i%this->kFenceStride==0)this->fences[i/this->kFenceStride]=v.start;
            prev=v;
        }
        return true;
    }
};
