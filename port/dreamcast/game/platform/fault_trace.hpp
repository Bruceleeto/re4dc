#pragma once
#include <cstdint>

namespace re4dc::fault_trace {
// Stack words are candidates, not an unwound call chain. Both stack reads and
// instruction reads are bounded before the caller's readers are invoked.
template<class ReadWord, class ReadHalf>
unsigned collect(std::uint32_t sp, std::uint32_t stack_lo, std::uint32_t stack_hi,
                 std::uint32_t code_lo, std::uint32_t code_hi,
                 std::uint32_t* out, unsigned capacity, ReadWord word, ReadHalf half) {
    if ((sp & 3U) || stack_lo >= stack_hi || sp < stack_lo || sp >= stack_hi ||
        code_hi <= code_lo || code_hi - code_lo < 4) return 0;
    unsigned count = 0;
    for (unsigned i = 0; i < 512 && count < capacity; ++i) {
        if (stack_hi - sp < 4) break;
        const std::uint32_t value = word(sp);
        sp += 4;
        if ((value & 1U) || value < code_lo + 4 || value >= code_hi) continue;
        const unsigned op = half(value - 4);
        if ((op & 0xf0ffU) != 0x400bU && (op & 0xf000U) != 0xb000U && (op & 0xf0ffU) != 0x0003U) continue;
        out[count++] = value;
    }
    return count;
}
}
