#pragma once
#include "ps2_source_package.hpp"

namespace re4dc { namespace room { namespace ps2 {
// Adapters use existing KOS file, native_static allocator and room4 hooks.
// No filesystem/allocator global is introduced; the existing room owner embeds
// this small object. A caller must retire it before that owner's heap rebuild.
struct SourceIo {
    void* context=nullptr;
    int (*open)(void*,const char*)=nullptr;
    std::int64_t (*size)(void*,int)=nullptr;
    std::ptrdiff_t (*read)(void*,int,void*,std::size_t)=nullptr;
    void (*close)(void*,int)=nullptr;
    void* (*allocate)(void*,std::size_t)=nullptr;
    void (*release)(void*,void*)=nullptr;
    bool (*current)(void*,Owner&)=nullptr;
};
#if defined(RE4DC_PS2_SOURCE_SPANS) && RE4DC_PS2_SOURCE_SPANS
SourceIo native_source_io();
#endif
enum class LoadError {ok,hooks,open,size,read,allocate,stale,package};
class SourceOwner {
    friend class WorldDraw; // private package access only during current-owner draw
    SourceIo io_{};
    SpanPackage package_{};
    std::uint8_t* storage_=nullptr;
    Owner owner_{};
    std::uint32_t bytes_=0,stale_drops_=0;
    PackageError package_error_=PackageError::ok;
    bool read_all(int file,void* destination,std::size_t bytes) {
        auto* out=static_cast<std::uint8_t*>(destination);
        while(bytes) {
            const auto got=io_.read(io_.context,file,out,bytes);
            if(got<=0 || std::size_t(got)>bytes)return false;
            out+=got;bytes-=std::size_t(got);
        }
        return true;
    }
    bool current_owner() const {
        Owner current{};return io_.current && io_.current(io_.context,current) && same_owner(current,owner_);
    }
public:
    explicit SourceOwner(SourceIo io):io_(io) {}
    SourceOwner(const SourceOwner&)=delete;
    SourceOwner& operator=(const SourceOwner&)=delete;
    ~SourceOwner(){retire();}
    void retire() {
        // Invalidate all package access before returning the one allocation.
        package_.retire();
        auto* old=storage_;storage_=nullptr;bytes_=0;
        if(old) {
            if(current_owner())io_.release(io_.context,old);
            else ++stale_drops_; // old heap was retired/replaced; never free into its successor
        }
        owner_={};
    }
    bool live() const {return storage_ && current_owner() && package_.live(owner_);}
    std::uint32_t resident_bytes() const {return live()?bytes_:0;}
    std::uint32_t stale_drops() const {return stale_drops_;}
    PackageError package_error() const {return package_error_;}
    LoadError load(const char* path,const ExpectedPackage& expected) {
        retire();package_error_=PackageError::ok;
        if(!io_.open || !io_.size || !io_.read || !io_.close || !io_.allocate || !io_.release || !io_.current)return LoadError::hooks;
        if(!io_.current(io_.context,owner_) || owner_.room!=expected.room || !owner_.generation)return LoadError::stale;
        const int file=io_.open(io_.context,path);if(file<0)return LoadError::open;
        const auto total=io_.size(io_.context,file);
        if(total<std::int64_t(sizeof(SpanHeader)) || total>UINT32_MAX-31U) {io_.close(io_.context,file);return LoadError::size;}
        SpanHeader header{};
        if(!read_all(file,&header,sizeof(header))) {io_.close(io_.context,file);return LoadError::read;}
        package_error_=SpanPackage::check_header(header,std::size_t(total),expected);
        if(package_error_!=PackageError::ok) {io_.close(io_.context,file);return LoadError::package;}
        if(!current_owner()){io_.close(io_.context,file);return LoadError::stale;}
        const auto allocation=(std::uint32_t(total)+31U)&~31U;
        storage_=static_cast<std::uint8_t*>(io_.allocate(io_.context,allocation));
        if(!storage_){io_.close(io_.context,file);return LoadError::allocate;}
        bytes_=allocation;std::memcpy(storage_,&header,sizeof(header));
        const bool read=read_all(file,storage_+sizeof(header),header.payload_bytes);
        io_.close(io_.context,file);
        if(!current_owner()){retire();return LoadError::stale;}
        if(!read){retire();return LoadError::read;}
        package_error_=package_.adopt({storage_,std::size_t(total)},expected,owner_);
        if(package_error_!=PackageError::ok){retire();return LoadError::package;}
        if(!current_owner()){retire();return LoadError::stale;}
        return LoadError::ok;
    }
};
}}}
