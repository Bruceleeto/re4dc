#!/usr/bin/env python3
"""Exercise the real target-list body and Luis caller with an expanding priority.

The shared function's argument is a priority count, not an output capacity: hit
boxes with flag 0x20 expand it to at most 20. No game logic is copied here; the
current C++ function bodies and WepTarget declaration are extracted at test time.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


def body(path, signature):
    text = (ROOT / path).read_text()
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


class LuisTargetCapacity(unittest.TestCase):
    def test_real_bodies_and_canaries(self):
        target = body("include/em_sub.h", "struct WepTarget {") + ";"
        scan = body("src/game/em_sub.cpp", "u32 GetWepTargetList2(")
        caller = body("src/pl14/pl14.cpp", "int isTarget(cSubLuis* luis, cEm* em)")
        self.assertIn("WepTarget list[20];", caller)
        self.assertIn("WepTarget list[2];", caller)  # original PPC/default path stays intact
        self.assertIn("list, 2, &hit, &nrm, &attr, 2, 0", caller)
        setup = r"""
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
using u32 = std::uint32_t;
using f32 = float;
struct Vec { float x, y, z; };
using Mtx = float[3][4];
struct YARARE_INFO { u32 flags; float rad; };
struct cModel { Vec world; };
struct cEm {
    u32 be_flag = 0x21; unsigned id = 0x10; int hp = 100;
    cModel storage{}; cModel* pParts = &storage;
    YARARE_INFO part{}; bool lockoff = false;
    cModel* getPartsPtr(int) { return pParts; }
    bool checkStatus(int) { return lockoff; }
};
struct cSubLuis : cEm {};
struct { unsigned nArray; } EmMgr;
static cEm* works[25];
static cEm* emWork(unsigned i) { return works[i]; }
static bool EmIsDead(cEm*) { return false; }
static YARARE_INFO* emLineAtCk(cEm* e, Vec*, Vec*, float, int) { return &e->part; }
struct Eat { u32 hitCheck(Vec*, Vec*, Vec*, Vec*, int, u32) { return 0; } } EatMgr;
struct Global { u32 Debug_flg[1]{}; } global;
static Global* pG = &global;
static void Draw_line3d(Vec*, Vec*, u32, int) {}
static void PSVECSubtract(Vec* a, Vec* b, Vec* d) { *d = {a->x-b->x,a->y-b->y,a->z-b->z}; }
static void PSMTXIdentity(Mtx) {}
static void PSMTXRotRad(Mtx, char, float) {}
static void TransMatrix(Mtx, Vec*) {}
static int PSMTXInverse(Mtx, Mtx) { return 1; }
static void PSMTXMultVec(Mtx, Vec* a, Vec* d) { *d = *a; }
static bool doorHitCheck(Vec*, Vec*) { return false; }
struct Log { void err(int, int, const char*, cEm*) {} } logger;
static Log* pLog = &logger;
#define EM_STATUS_LOCKOFF 1
#define VALID_PTR(p) ((p) != nullptr)
#define RE4DC_GAME 1
#define RE4DC_ROUTE_CH22 1
"""
        checks = r"""
struct Guarded {
    unsigned char before[64]; WepTarget list[20]; unsigned char after[64];
    Guarded() { std::memset(this, 0xa5, sizeof(*this)); }
    void intact() const {
        for (auto v : before) assert(v == 0xa5);
        for (auto v : after) assert(v == 0xa5);
    }
};
int main() {
    cSubLuis luis; luis.id = 4;
    cEm enemies[24]; works[0] = &luis;
    for (unsigned i = 0; i != 24; ++i) works[i+1] = &enemies[i];
    Vec p{}, q{}, hit{}, nrm{}; u32 attr = 0;
    unsigned cases = 0;
    for (unsigned n = 1; n <= 25; ++n) {
        for (unsigned flagged = 0; flagged <= n; ++flagged) {
            EmMgr.nArray = n;
            for (unsigned i = 0; i != n; ++i) {
                works[i]->id = i ? 0x10 : 4;
                works[i]->part.flags = i < flagged ? 0x20 : 0;
                works[i]->part.rad = float(n-i);
            }
            Guarded g;
            u32 count = GetWepTargetList2(&p,&q,g.list,2,&hit,&nrm,&attr,2,0);
            g.intact(); assert(count <= 20);
            for (u32 i = 1; i < count; ++i) assert(g.list[i-1].part->rad <= g.list[i].part->rad);
            ++cases;
        }
    }
    // The real function overwrites the logical two-entry boundary in the old caller.
    // Twenty physically allocated entries make this a defined canary experiment.
    EmMgr.nArray = 25;
    for (unsigned i = 0; i != 25; ++i) {
        works[i]->part.flags = 0x20; works[i]->part.rad = float(i+1);
    }
    Guarded expanded;
    unsigned char old_boundary[sizeof(WepTarget)];
    std::memcpy(old_boundary, &expanded.list[2], sizeof(old_boundary));
    assert(GetWepTargetList2(&p,&q,expanded.list,2,&hit,&nrm,&attr,2,0) == 20);
    assert(std::memcmp(old_boundary, &expanded.list[2], sizeof(old_boundary)) != 0);
    assert(expanded.list[2].em == works[2]); expanded.intact();
    // Both flagged-door cap expansion and the final special-hit append use the same bound.
    for (unsigned doorId : {0x41u, 0x4eu}) {
        for (unsigned doorFlag : {0u, 0x20u}) {
            for (unsigned n = 1; n <= 25; ++n) {
                EmMgr.nArray = n;
                for (unsigned i = 0; i != n; ++i) {
                    works[i]->id = i == 0 ? doorId : 0x10;
                    works[i]->part.flags = i == 0 ? doorFlag : 0x20;
                    works[i]->part.rad = float(i+1);
                }
                Guarded g;
                assert(GetWepTargetList2(&p,&q,g.list,2,&hit,&nrm,&attr,2,0) <= 20);
                g.intact(); ++cases;
            }
        }
    }
    // Execute Luis's actual guarded caller on the expansion path and both decision outcomes.
    EmMgr.nArray = 25; works[0]->id = 4;
    for (unsigned i = 0; i != 25; ++i) {
        works[i]->part.flags = 0x20; works[i]->part.rad = float(i+1);
    }
    assert(isTarget(&luis, works[1]) == 1);
    assert(isTarget(&luis, works[2]) == 0);
    std::cout << "PASS: " << cases << " real-body cap/canary cases; old two-entry boundary overwritten; "
                 "20-entry guards intact; native Luis decisions preserved\n";
}
"""
        with tempfile.TemporaryDirectory(prefix="re4dc-luis-cap-") as td:
            source = Path(td) / "test.cpp"
            exe = Path(td) / "test"
            source.write_text(setup + target + scan + caller + checks)
            subprocess.run(["c++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-variable",  # legacy body retains an unused original local
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", str(source), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
