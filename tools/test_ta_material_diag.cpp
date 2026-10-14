#include "../port/dreamcast/game/platform/include/ta_material_diag.h"
#include <cassert>
#include <limits>
#include <cstdio>
using namespace re4dc_tamat;
int main(){
    const float x[4]={0,640,640,0},y[4]={0,0,480,480};
    assert(area(x,y,4)==307200);
    const float rx[4]={-100,100,100,-100},ry[4]={-100,-100,100,100};
    assert(area(rx,ry,4)==10000);
    const float tx[3]={0,640,0},ty[3]={0,0,480};assert(area(tx,ty,3)==153600);
    const float outside[3]={-10,-5,-1};assert(area(outside,ty,3)==0);
    const float bad[3]={0,std::numeric_limits<float>::infinity(),1};assert(area(bad,ty,3)<0);
    Census c;
    assert(c.select(2,1,4,5,true)==0);
    assert(c.select(2,1,4,5,true)==0);
    c.add(2,tx,ty,3,1);assert(c.rows[0].fill==153600 && c.rows[0].tris==1);
    assert(c.select(4,1,4,5,true)==1);c.add(4,x,y,4,2);
    assert(c.rows[1].fill==307200 && c.fill[2]==153600);
    assert(c.select(2,2,4,5,true)==2);c.add(2,x,y,4,2);
    assert(c.rows[2].tris==2 && c.tris[2]==3);
    c.add(2,bad,ty,3,1);assert(c.invalid==1 && c.tris[2]==3);
    // Complete 64-byte sprite: A/B/Cx in first burst, Cy/Cz/Dx/Dy in second.
    c.clear();c.select(2,4,2,3,true);
    const float first[8]={0,0,0,1,640,0,1,640};const float second[8]={480,1,0,480,0,0,0,0};
    c.sprite_first(2,first);c.sprite_second(2,second);assert(c.fill[2]==307200 && c.tris[2]==2);
    c.clear();assert(c.count==0 && c.fill[2]==0 && c.invalid==0 && c.current[2]==None);
    for(unsigned i=0;i<MaxRows;++i)assert(c.select(2,1,0,i,true)==i);
    assert(c.select(2,1,0,9999,true)==None && c.overflow==1);
    c.add(2,tx,ty,3,1);assert(c.orphans==1 && c.fill[2]==153600);
    assert(c.select(2,1,0,0,true)==0);c.add(2,tx,ty,3,1);assert(c.rows[0].tris==1);
    c.clear();assert(c.select(2,1,0,9999,true)==0);
    std::puts("TA material diagnostic geometry, attribution, overflow and reset PASS");
}
