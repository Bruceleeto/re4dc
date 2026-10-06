// PS2_INTERIOR_CULL validation: from given eyes, cast K directions (Fibonacci sphere); each ray is followed to where it
// first leaves the hull union; an unoccluded ray's exit point is printed when it lies in none of the given portals
// (a sampling gap of cast_cell). Same occluder rules as cast_cell.cpp.
// args: tris hull portals.txt K tmin x,y,z ...    portals.txt: "axis plane u0 u1 v0 v1" per line
// env PROBE_MISS_OUT=<file> PROBE_CELL=<mm>: every miss is also appended to <file> as a cast_cell exit line
// ("box face iu iv"), which build_cell.py emit merges (exits_v_<i>.txt) to close the gap.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <cstdint>
#include <algorithm>
struct Tri { float a[3], b[3], c[3]; uint32_t two; };
struct Box { double lo[3], hi[3]; };
struct Portal { int axis; double plane, u0, u1, v0, v1; };
static void slab(const Box& b, const double o[3], const double d[3], double& t0, double& t1, int& f1) {
    t0 = -1e30; t1 = 1e30; f1 = -1;
    for (int a = 0; a < 3; ++a) {
        if (std::fabs(d[a]) < 1e-12) { if (o[a] < b.lo[a] || o[a] > b.hi[a]) { t0 = 1; t1 = 0; return; } continue; }
        double ta = (b.lo[a] - o[a]) / d[a], tb = (b.hi[a] - o[a]) / d[a]; int fb = 2*a+1;
        if (ta > tb) { std::swap(ta, tb); fb = 2*a; }
        if (ta > t0) t0 = ta;
        if (tb < t1) { t1 = tb; f1 = fb; }
    }
}
int main(int argc, char** argv) {
    if (argc < 7) return 1;
    FILE* f = fopen(argv[1], "rb"); uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2;
    std::vector<Tri> T(n); if (fread(T.data(), sizeof(Tri), n, f) != n) return 2; fclose(f);
    std::vector<Box> H; { FILE* h = fopen(argv[2], "r"); Box b; while (fscanf(h, "%lf %lf %lf %lf %lf %lf", &b.lo[0], &b.lo[1], &b.lo[2], &b.hi[0], &b.hi[1], &b.hi[2]) == 6) H.push_back(b); fclose(h); }
    std::vector<Portal> P; { FILE* h = fopen(argv[3], "r"); Portal p; while (fscanf(h, "%d %lf %lf %lf %lf %lf", &p.axis, &p.plane, &p.u0, &p.u1, &p.v0, &p.v1) == 6) P.push_back(p); fclose(h); }
    const int K = atoi(argv[4]); const double tmin = atof(argv[5]);
    std::vector<double> A(3*n), E1(3*n), E2(3*n), N(3*n);
    for (uint32_t i = 0; i < n; ++i) for (int a = 0; a < 3; ++a) { A[3*i+a] = T[i].a[a]; E1[3*i+a] = T[i].b[a] - T[i].a[a]; E2[3*i+a] = T[i].c[a] - T[i].a[a]; }
    for (uint32_t i = 0; i < n; ++i) { double* e1 = &E1[3*i]; double* e2 = &E2[3*i];
        N[3*i] = e1[1]*e2[2]-e1[2]*e2[1]; N[3*i+1] = e1[2]*e2[0]-e1[0]*e2[2]; N[3*i+2] = e1[0]*e2[1]-e1[1]*e2[0]; }
    const char* mo = getenv("PROBE_MISS_OUT"); const double mcell = getenv("PROBE_CELL") ? atof(getenv("PROBE_CELL")) : 100;
    FILE* mf = mo ? fopen(mo, "a") : nullptr;
    for (int ei = 6; ei < argc; ++ei) {
        double o[3]; if (sscanf(argv[ei], "%lf,%lf,%lf", &o[0], &o[1], &o[2]) != 3) return 3;
        long esc = 0, miss = 0;
        const double ga = M_PI * (3 - std::sqrt(5.0));
        #pragma omp parallel for reduction(+:esc,miss) schedule(dynamic, 4096)
        for (int di = 0; di < K; ++di) {
            double y = 1 - 2 * (di + 0.5) / K, r = std::sqrt(1 - y * y), t = ga * di;
            const double d[3] = {r * std::cos(t), y, r * std::sin(t)};
            double te = 0; int ef = -1, eb = -1; bool inside = false;
            for (bool grew = true; grew; ) { grew = false;
                for (size_t bi = 0; bi < H.size(); ++bi) { double t0, t1; int f1; slab(H[bi], o, d, t0, t1, f1); if (t0 <= te + 1e-6 && t1 > te + 1e-6) { te = t1; ef = f1; eb = int(bi); grew = inside = true; } } }
            if (!inside) continue;
            bool occ = false;
            for (uint32_t i = 0; i < n && !occ; ++i) {
                const double dn = d[0]*N[3*i]+d[1]*N[3*i+1]+d[2]*N[3*i+2];
                if (!T[i].two && dn >= 0) continue;
                const double* e1 = &E1[3*i]; const double* e2 = &E2[3*i];
                double p[3] = {d[1]*e2[2]-d[2]*e2[1], d[2]*e2[0]-d[0]*e2[2], d[0]*e2[1]-d[1]*e2[0]};
                double det = e1[0]*p[0]+e1[1]*p[1]+e1[2]*p[2]; if (std::fabs(det) < 1e-9) continue;
                double inv = 1 / det; double s[3] = {o[0]-A[3*i], o[1]-A[3*i+1], o[2]-A[3*i+2]};
                double u = (s[0]*p[0]+s[1]*p[1]+s[2]*p[2]) * inv; if (u < 0 || u > 1) continue;
                double q[3] = {s[1]*e1[2]-s[2]*e1[1], s[2]*e1[0]-s[0]*e1[2], s[0]*e1[1]-s[1]*e1[0]};
                double v = (d[0]*q[0]+d[1]*q[1]+d[2]*q[2]) * inv; if (v < 0 || u + v > 1) continue;
                double tt = (e2[0]*q[0]+e2[1]*q[1]+e2[2]*q[2]) * inv;
                if (tt >= tmin && tt <= te) occ = true;
            }
            if (occ) continue;
            ++esc;
            const double x[3] = {o[0]+te*d[0], o[1]+te*d[1], o[2]+te*d[2]};
            bool covered = false;
            for (auto& p : P) {
                const int ua = (p.axis + 1) % 3, va = (p.axis + 2) % 3;
                if (std::fabs(x[p.axis] - p.plane) < 1 && x[ua] >= p.u0 && x[ua] <= p.u1 && x[va] >= p.v0 && x[va] <= p.v1) { covered = true; break; }
            }
            if (!covered) {
                ++miss;
                const int ax = ef / 2, ua = (ax + 1) % 3, va = (ax + 2) % 3;
                #pragma omp critical
                { if (mf) fprintf(mf, "%d %d %d %d\n", eb, ef, int(std::floor(x[ua] / mcell)), int(std::floor(x[va] / mcell)));
                if (miss <= 20) printf("  MISS eye %s dir %.4f %.4f %.4f exit face %d at %.0f %.0f %.0f\n", argv[ei], d[0], d[1], d[2], ef, x[0], x[1], x[2]); }
            }
        }
        printf("eye %s: %d directions, %ld escape, %ld outside the portals\n", argv[ei], K, esc, miss);
    }
    if (mf) fclose(mf);
    return 0;
}
