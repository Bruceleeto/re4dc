// Hull caster for the house cell. The hull is a union of axis-aligned boxes (the house volume incl. its walls).
// From each camera, a ray towards each target (points on the hull boundary) is followed to the point where it
// first leaves the hull union; if no front-facing (or two-sided) OP triangle lies on it between tmin and that point,
// the exit point is a portal sample. Output: unique exit cells {box, face, iu, iv} (cell = 'cell' mm on that face).
// tris.bin: u32 N, N x {float a[3],b[3],c[3]; u32 twosided}; cams.bin / targets.bin: u32 M, M x float[3]
// hull.txt: one box per line "x0 y0 z0 x1 y1 z1"
// args: tris cams targets hull out tmin cell [eps]: hits within eps mm of the target itself are ignored (an edge target:
// the ray passes through the crack the edge may leave; its own triangles do not occlude it)
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <cstdint>
#include <algorithm>
#include <set>
#include <tuple>
#include <string>
struct Tri { float a[3], b[3], c[3]; uint32_t two; };
struct Box { double lo[3], hi[3]; };
static std::vector<float> load(const char* p, uint32_t& m) {
    FILE* f = fopen(p, "rb"); if (!f || fread(&m, 4, 1, f) != 1) exit(2);
    std::vector<float> v(3 * m); if (fread(v.data(), 4, 3 * m, f) != 3 * m) exit(2); fclose(f); return v;
}
// [t0,t1] of the ray inside box b (t0>t1: miss)
static void slab(const Box& b, const double o[3], const double d[3], double& t0, double& t1, int& f1) {
    t0 = -1e30; t1 = 1e30; f1 = -1;
    for (int a = 0; a < 3; ++a) {
        if (std::fabs(d[a]) < 1e-12) { if (o[a] < b.lo[a] || o[a] > b.hi[a]) { t0 = 1; t1 = 0; return; } continue; }
        double ta = (b.lo[a] - o[a]) / d[a], tb = (b.hi[a] - o[a]) / d[a]; int fa = 2*a, fb = 2*a+1;
        if (ta > tb) { std::swap(ta, tb); std::swap(fa, fb); }
        if (ta > t0) t0 = ta;
        if (tb < t1) { t1 = tb; f1 = fb; }
    }
}
int main(int argc, char** argv) {
    if (argc < 8) return 1;
    FILE* f = fopen(argv[1], "rb"); uint32_t n; if (fread(&n, 4, 1, f) != 1) return 2;
    std::vector<Tri> T(n); if (fread(T.data(), sizeof(Tri), n, f) != n) return 2; fclose(f);
    uint32_t m, k; std::vector<float> C = load(argv[2], m), P = load(argv[3], k);
    std::vector<Box> H; { FILE* h = fopen(argv[4], "r"); Box b; while (fscanf(h, "%lf %lf %lf %lf %lf %lf", &b.lo[0], &b.lo[1], &b.lo[2], &b.hi[0], &b.hi[1], &b.hi[2]) == 6) H.push_back(b); fclose(h); }
    const double tmin = atof(argv[6]), cell = atof(argv[7]), eps = argc > 8 ? atof(argv[8]) : 2.0;
    std::vector<double> A(3*n), E1(3*n), E2(3*n), N(3*n), lo(3*n), hi(3*n);
    for (uint32_t i = 0; i < n; ++i) for (int a = 0; a < 3; ++a) {
        A[3*i+a] = T[i].a[a]; E1[3*i+a] = T[i].b[a] - T[i].a[a]; E2[3*i+a] = T[i].c[a] - T[i].a[a];
        lo[3*i+a] = std::min({T[i].a[a], T[i].b[a], T[i].c[a]}); hi[3*i+a] = std::max({T[i].a[a], T[i].b[a], T[i].c[a]});
    }
    for (uint32_t i = 0; i < n; ++i) { double* e1 = &E1[3*i]; double* e2 = &E2[3*i];
        N[3*i] = e1[1]*e2[2]-e1[2]*e2[1]; N[3*i+1] = e1[2]*e2[0]-e1[0]*e2[2]; N[3*i+2] = e1[0]*e2[1]-e1[1]*e2[0]; }
    typedef std::tuple<int,int,long,long> Key;
    std::set<Key> all; unsigned long long rays = 0, escapes = 0, outside = 0;
    std::vector<uint32_t> camesc(m, 0);
    #pragma omp parallel
    {
        std::set<Key> local; unsigned long long lr = 0, le = 0, lo_ = 0;
        #pragma omp for schedule(dynamic, 1)
        for (int ci = 0; ci < (int)m; ++ci) {
            const double o[3] = {C[3*ci], C[3*ci+1], C[3*ci+2]};
            for (uint32_t ti = 0; ti < k; ++ti) {
                double d[3] = {P[3*ti]-o[0], P[3*ti+1]-o[1], P[3*ti+2]-o[2]};
                const double len = std::sqrt(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]); if (len <= tmin) continue;
                for (double& x : d) x /= len;
                ++lr;
                // first exit from the union: grow [0, te] while some box covers te
                double te = 0; int eb = -1, ef = -1; bool inside = false;
                for (bool grew = true; grew; ) {
                    grew = false;
                    for (int bi = 0; bi < (int)H.size(); ++bi) {
                        double t0, t1; int f1; slab(H[bi], o, d, t0, t1, f1);
                        if (t0 <= te + 1e-6 && t1 > te + 1e-6) { te = t1; eb = bi; ef = f1; grew = true; inside = true; }
                    }
                }
                if (!inside) { ++lo_; continue; } // camera outside the hull
                double slo[3], shi[3]; for (int a = 0; a < 3; ++a) { double e = o[a] + te*d[a]; slo[a] = std::min(o[a], e); shi[a] = std::max(o[a], e); }
                bool occ = false;
                for (uint32_t i = 0; i < n && !occ; ++i) {
                    const double* l = &lo[3*i]; const double* h = &hi[3*i];
                    if (h[0] < slo[0] || l[0] > shi[0] || h[1] < slo[1] || l[1] > shi[1] || h[2] < slo[2] || l[2] > shi[2]) continue;
                    const double dn = d[0]*N[3*i]+d[1]*N[3*i+1]+d[2]*N[3*i+2];
                    if (!T[i].two && dn >= 0) continue;
                    const double* e1 = &E1[3*i]; const double* e2 = &E2[3*i];
                    double p[3] = {d[1]*e2[2]-d[2]*e2[1], d[2]*e2[0]-d[0]*e2[2], d[0]*e2[1]-d[1]*e2[0]};
                    double det = e1[0]*p[0]+e1[1]*p[1]+e1[2]*p[2]; if (std::fabs(det) < 1e-9) continue;
                    double inv = 1 / det; double s[3] = {o[0]-A[3*i], o[1]-A[3*i+1], o[2]-A[3*i+2]};
                    double u = (s[0]*p[0]+s[1]*p[1]+s[2]*p[2]) * inv; if (u < 0 || u > 1) continue;
                    double q[3] = {s[1]*e1[2]-s[2]*e1[1], s[2]*e1[0]-s[0]*e1[2], s[0]*e1[1]-s[1]*e1[0]};
                    double v = (d[0]*q[0]+d[1]*q[1]+d[2]*q[2]) * inv; if (v < 0 || u + v > 1) continue;
                    double t = (e2[0]*q[0]+e2[1]*q[1]+e2[2]*q[2]) * inv;
                    if (t >= tmin && t <= te && std::fabs(t - len) > eps) occ = true;
                }
                if (occ) continue;
                ++le; ++camesc[ci];
                const int ax = ef / 2, ua = (ax + 1) % 3, va = (ax + 2) % 3;
                const double x[3] = {o[0]+te*d[0], o[1]+te*d[1], o[2]+te*d[2]};
                local.insert(Key(eb, ef, (long)std::floor(x[ua] / cell), (long)std::floor(x[va] / cell)));
            }
        }
        #pragma omp critical
        { all.insert(local.begin(), local.end()); rays += lr; escapes += le; outside += lo_; }
    }
    f = fopen(argv[5], "w");
    fprintf(f, "# rays %llu escapes %llu cam-outside %llu cells %zu\n", rays, escapes, outside, all.size());
    for (auto& key : all) fprintf(f, "%d %d %ld %ld\n", std::get<0>(key), std::get<1>(key), std::get<2>(key), std::get<3>(key));
    fclose(f);
    f = fopen((std::string(argv[5]) + ".cams").c_str(), "w"); for (uint32_t ci = 0; ci < m; ++ci) fprintf(f, "%u\n", camesc[ci]); fclose(f);
    return 0;
}
