#include "aica_bank_v2_sha256.h"
#if RE4DC_AICA_BANK_V2
#include <string.h>
namespace re4dc_aic2 {
namespace {
const uint32_t K[64]={
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
uint32_t rr(uint32_t n,uint32_t b){return (n>>b)|(n<<(32-b));}
void be(uint8_t* p,uint32_t x){p[0]=x>>24;p[1]=x>>16;p[2]=x>>8;p[3]=x;}
}
void Sha256::reset(){
    const uint32_t initial[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    memcpy(state,initial,32);bytes_lo=bytes_hi=used=reserved=0;memset(block,0,64);
}
void Sha256::transform(){
    uint32_t w[16];
    for(uint32_t i=0;i<16;++i){const uint8_t* p=block+4*i;w[i]=(uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3];}
    uint32_t a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
    for(uint32_t i=0;i<64;++i){
        if(i>=16){uint32_t x=w[(i-15)&15],y=w[(i-2)&15];w[i&15]+=(rr(x,7)^rr(x,18)^(x>>3))+w[(i-7)&15]+(rr(y,17)^rr(y,19)^(y>>10));}
        uint32_t t1=h+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^((~e)&g))+K[i]+w[i&15];
        uint32_t t2=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b)^(a&c)^(b&c));
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
}
void Sha256::update(const void* data,uint32_t n){
    const uint8_t* p=static_cast<const uint8_t*>(data);uint32_t old=bytes_lo;bytes_lo+=n;if(bytes_lo<old)++bytes_hi;
    while(n){uint32_t take=n<64-used?n:64-used;memcpy(block+used,p,take);used+=take;p+=take;n-=take;if(used==64){transform();used=0;}}
}
void Sha256::finish(uint8_t out[32]){
    uint32_t hi=(bytes_hi<<3)|(bytes_lo>>29),lo=bytes_lo<<3;
    block[used++]=0x80;if(used>56){memset(block+used,0,64-used);transform();used=0;}
    memset(block+used,0,56-used);be(block+56,hi);be(block+60,lo);transform();
    for(uint32_t i=0;i<8;++i)be(out+4*i,state[i]);
    used=0;
}
}
#endif
