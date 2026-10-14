#!/bin/bash
# module_mem_free_test.sh: host test of read.cpp's RESET_HEAP_FIX ModuleMemFree (the function body is extracted
# from src/game/read.cpp and compiled against a mock heap table).
#   1. r11c: a pl11 archive in live heap 4 that also lies in a destroyed heap 0's stale range is freed (not dropped).
#   2. soft reset: every heap destroyed, a block in an old heap's range is dropped.
#   3. a block in no heap range is freed as before.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
W=$(mktemp -d); trap 'rm -rf $W' EXIT
awk '/^static void ModuleMemFree\(void\* p\)/{on=1} on{print} on&&/^}/{exit}' "$ROOT/src/game/read.cpp" > $W/fn.inc
grep -q 'Heap\[i\].handle >= 0' $W/fn.inc || { echo "FAIL: live-heap precedence missing"; exit 1; }
cat > $W/t.cpp <<'EOF'
#include <cstdio>
typedef unsigned int u32;
#define MEM_HEAP_NUM 8
struct H { int handle; u32 start, end; } Heap[MEM_HEAP_NUM];
static int freed, dropped;
static void Mem_free(void*) { ++freed; }
#define OSReport(...) (++dropped)
#include "fn.inc"
static int check(const char* n, u32 a, int f, int d) {
    freed = dropped = 0; ModuleMemFree((void*)(unsigned long)a);
    int ok = freed == f && dropped == d; printf("%s %s freed=%d dropped=%d\n", ok ? "PASS" : "FAIL", n, freed, dropped); return ok;
}
int main() {
    for (auto& h : Heap) h = {-1, 0, 0};
    Heap[0] = {-1, 0x8c400000u, 0x8cfd0000u};  // destroyed heap 0, stale range
    Heap[4] = {3, 0x8c89aca0u, 0x8cfcbbc0u};   // live room heap 4
    int ok = check("r11c-live-heap4-over-stale-heap0", 0x8cd752c0u, 1, 0);
    Heap[4].handle = -1;                          // soft reset: every heap destroyed
    ok &= check("reset-stale-pointer", 0x8cd752c0u, 0, 1);
    ok &= check("outside-every-heap", 0x8c010000u, 1, 0);
    return ok ? 0 : 1;
}
EOF
g++ -std=c++17 -w -fpermissive -o $W/t $W/t.cpp && $W/t && echo "MODULE_MEM_FREE_TEST PASS"
