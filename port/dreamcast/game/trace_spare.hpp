#pragma once
// LOGIC_TRACE_SWAPPED (diagnostic only): bounded layout of the trace's share of the sub screen backing store.
// The store's bytes below `saved_end` are the saved window and are never written here. Above it, inside the store's
// existing capacity (never grown):
//   raw bytes   [begin, end)   appended upward from saved_end (TraceRegionView spans' data, 4-byte padded);
//   span index  [low, top)     8-byte entries pushed downward from the top; entry i sits at top - 8 * (i + 1).
// Neither side may cross the other: every request that would is refused (fail-closed), nothing is evicted.
// Pure position arithmetic: platform/subscreen_backing.cpp moves the words, the host tests drive the same code.
struct TraceSpare {
    unsigned begin = 0, end = 0, low = 0, top = 0;
    bool open = false;
    // saved_end: first byte after the saved window (4-aligned); capacity: the store's current byte size.
    bool start(unsigned saved_end, unsigned capacity) {
        *this = TraceSpare{};
        if ((saved_end & 3U) || saved_end > capacity) return false;
        begin = end = saved_end;
        top = capacity & ~7U;
        if (top < saved_end) top = saved_end;  // no index room: every push is refused
        low = top;
        open = true;
        return true;
    }
    // `padded` (a multiple of 4) raw bytes at `end`; *at receives their store offset.
    bool data(unsigned padded, unsigned* at) {
        if (!open || (padded & 3U) || padded > low - end) return false;
        *at = end;
        end += padded;
        return true;
    }
    // One more index entry; *at receives its store offset.
    bool push(unsigned* at) {
        if (!open || low - end < 8) return false;
        low -= 8;
        *at = low;
        return true;
    }
    unsigned entries() const { return open ? (top - low) / 8 : 0; }
    bool entry(unsigned i, unsigned* at) const {
        if (!open || i >= entries()) return false;
        *at = top - 8 * (i + 1);
        return true;
    }
    // [offset, offset + bytes) lies in the raw bytes.
    bool data_span(unsigned offset, unsigned bytes) const {
        return open && offset >= begin && offset <= end && bytes <= end - offset;
    }
    unsigned spare_left() const { return open ? low - end : 0; }
};
