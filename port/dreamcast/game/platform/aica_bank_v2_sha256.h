#ifndef RE4DC_AICA_BANK_V2_SHA256_H
#define RE4DC_AICA_BANK_V2_SHA256_H
#include "aica_bank_v2_host.h"
#if RE4DC_AICA_BANK_V2
namespace re4dc_aic2 {
// No heap; the transform uses a 16-word rolling schedule.
struct Sha256 {
    uint32_t state[8], bytes_lo, bytes_hi, used, reserved;
    uint8_t block[64];
    void reset();
    void update(const void* bytes, uint32_t count);
    void finish(uint8_t digest[32]);
private:
    void transform();
};
static_assert(sizeof(Sha256)==112, "SHA context budget");
}
#endif
#endif
