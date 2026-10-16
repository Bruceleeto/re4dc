#!/usr/bin/env python3
"""Read-only host verifier for explicitly selected adjacent part-range merges.

Package names, pairs and protected placement IDs come from a caller-owned plan.
The independent checks do not import an asset converter or write game packages.
JSON goes to stdout. Runtime state/lifetime review and visual checks are separate.
"""
from pathlib import Path
import argparse,sys,struct,zlib,hashlib,json,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import packages as F
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--candidate',type=Path,required=True)
parser.add_argument('--plan',type=Path,required=True,help='package names, pair triples and protected placements; see README')
args=parser.parse_args()
S=args.source; C=args.candidate
plan=json.loads(args.plan.read_text())
active_name=plan['active_mesh']; fallback_name=plan['fallback_mesh']
pairs=tuple(tuple(p) for p in plan['pairs'])
assert pairs and all(len(p)==3 and all(isinstance(v,int) and v>=0 for v in p) for p in pairs), 'invalid pairs'
assert len({v for _,a,b in pairs for v in (a,b)})==2*len(pairs), 'overlapping pair rows'
side=(S/plan['sidecar']).read_bytes()
assert side==(C/plan['sidecar']).read_bytes()
sh=struct.unpack_from('<4s7I',side)
assert sh[:2]==(b'R4PW',1) and len(side)==32+16*sh[3]+52*sh[2] and zlib.crc32(side[32:])==sh[5]
meta=[struct.unpack_from('<IIHH4B',side,32+16*i) for i in range(sh[3])]
places=[struct.unpack_from('<HH12f',side,32+16*sh[3]+52*i) for i in range(sh[2])]
assert all(r[4]<=2 and r[5]<=2 and 0<r[2]<=1024 and 0<r[3]<=1024 for r in meta), 'R4PW material admission'
assert all(r[0]<sh[4] and r[1]<sh[2] and all(map(math.isfinite,r[2:])) for r in places), 'R4PW placement admission'
ids=(S/plan['ids']).read_bytes()
assert ids==(C/plan['ids']).read_bytes() and struct.unpack_from('<4s3I',ids)==(b'R4ID',1,sh[2],sh[5])
assert len(ids)>=16+sh[2] and len(ids)%32==0, 'R4ID length/alignment'
protected_ids=set(plan['protected_placements'])
assert all(isinstance(i,int) and 0<=i<sh[2] for i in protected_ids), 'invalid protected placement'
protected={pl[0] for pl in places if pl[1]<=2 or pl[1] in protected_ids or ids[16+pl[1]]<250}

def state(raw,h,p,i):
    return (meta[i],tuple(p['parts'][i][3:6]),raw[h[11]+36*i+20:h[11]+36*i+36])
def walk(raw,h,p):
    result=[]
    for pas in range(3):
        for row,pl in enumerate(places):
            m=p['meshes'][pl[0]]
            for i in range(m[6],m[6]+m[7]):
                if meta[i][4]!=pas: continue
                fc,nc=p['plods'][i]
                for ci in range(fc,fc+nc): result.append((pas,row,pl[0],ci,state(raw,h,p,i)))
    return result

def validate(raw,p):
    h=F.HEADER.unpack_from(raw); l=F.LOD_HEADER.unpack_from(raw,80)
    assert sh[3:5]==(h[5],h[4])
    assert 1<=h[9]<=16, 'palette count'
    for off,count,size in ((h[10],h[4],F.MESH.size),(h[11],h[5],F.PART.size),(h[12],h[6],F.MESHLET.size),(h[13],h[7],F.VERTEX.size),(h[14],h[8],1),(h[15],h[9],4),(l[2],h[5],8),(l[3],l[0],20),(l[4],l[1],12)):
        assert off>=112 and off%4==0 and off+count*size<=len(raw)
    for m in p['meshes']:
        assert 0<=m[6]<=h[5] and 0<=m[7]<=h[5]-m[6]
        assert all(math.isfinite(x) and x>0 for x in m[11:14]), 'mesh grid'
    strips=corners=0
    for m in p['lets']:
        assert 0<m[3]<=256
        indexed=bool(m[4]&0x8000)
        assert not indexed or m[1]%2==0
        assert 0<=m[1] and m[1]+2*m[3]*indexed+m[2]<=len(p['strip'])
        cs,ss=F.let_corners(p,m)
        assert all(0<=c<h[7] for c in cs)
        at=m[1]+2*m[3]*indexed
        for s in ss:
            assert len(s)>=3 and all(0<=k<m[3] for k in s)
            at+=1+len(s)
        assert at==m[1]+2*m[3]*indexed+m[2]
        strips+=len(ss); corners+=sum(map(len,ss))
    prev=0; nonempty=0
    for i,(part,plod) in enumerate(zip(p['parts'],p['plods'])):
        fl,nl=part[6:8]; fc,nc=plod
        assert part[5]==0 and 0<=fl<=h[6] and 0<=nl<=h[6]-fl
        assert 0<=fc<=l[0] and 0<=nc<=l[0]-fc
        if nl:
            ms=p['lets'][fl:fl+nl]
            lo=min(m[0] for m in ms)
            hi=max(max(F.let_corners(p,m)[0])+1 for m in ms)
            assert lo>=prev and hi<=h[7]
            prev=hi; nonempty+=1
        for cl in p['clusters'][fc:fc+nc]:
            assert cl[7]>0 and 0<=cl[6]<=l[1] and cl[7]<=l[1]-cl[6]
            last=0
            for lv in p['levels'][cl[6]:cl[6]+cl[7]]:
                assert fl<=lv[0] and 0<=lv[1]<=nl and lv[0]-fl<=nl-lv[1]
                assert math.isfinite(lv[2]) and last<=lv[2]<3e38
                last=lv[2]
    return dict(strips=strips,corners=corners,nonempty_parts=nonempty)

report={'status':'INDEPENDENT_HOST_INVARIANTS_PASS','mesh_files':{},'protected_mesh_count':len(protected),'shared_sidecar_and_ids_identical':True}
for name in (active_name,fallback_name):
    a=(S/name).read_bytes();b=(C/name).read_bytes()
    p=F.read(a);q=F.read(b)
    h=F.HEADER.unpack_from(a); k=F.HEADER.unpack_from(b); l=F.LOD_HEADER.unpack_from(a,80)
    assert len(a)==len(b) and h[:3]==k[:3] and h[4:]==k[4:]
    old=validate(a,p); new=validate(b,q)
    allowed=set(range(12,16)); details=[]
    for mi,x,y in pairs:
        assert mi not in protected
        m=p['meshes'][mi]
        assert y==x+1 and m[6]<=x<y<m[6]+m[7]
        assert state(a,h,p,x)==state(a,h,p,y)==state(b,k,q,x)==state(b,k,q,y)
        assert meta[x][4]==0, 'only opaque pairs are supported'
        ax,by=p['parts'][x],p['parts'][y];cx,dy=p['plods'][x],p['plods'][y]
        assert ax[6]+ax[7]==by[6] and cx[0]+cx[1]==dy[0]
        assert q['parts'][x][7]==ax[7]+by[7] and q['parts'][y][7]==0
        assert q['plods'][x][1]==cx[1]+dy[1] and q['plods'][y][1]==0
        for off in (h[11]+36*x+16,h[11]+36*y+16,l[2]+8*x+4,l[2]+8*y+4): allowed.update(range(off,off+4))
        ss=[s for ml in p['lets'][ax[6]:by[6]+by[7]] for s in F.let_corners(p,ml)[1]]
        details.append(dict(mesh=mi,parts=[x,y],merged_all_level_strip_corners=sum(map(len,ss)),merged_all_level_strips=len(ss),merged_meshlets=ax[7]+by[7]))
    changes={i for i,(v,w) in enumerate(zip(a,b)) if v!=w}
    assert changes<=allowed
    for key in ('meshes','lets','verts','strip','pal','clusters','levels'): assert p[key]==q[key],key
    for mi in protected:
        m=p['meshes'][mi]
        for i in range(m[6],m[6]+m[7]): assert p['parts'][i]==q['parts'][i] and p['plods'][i]==q['plods'][i]
    assert walk(a,h,p)==walk(b,k,q)
    assert old['strips']==new['strips'] and old['corners']==new['corners'] and old['nonempty_parts']-new['nonempty_parts']==len(pairs)
    report['mesh_files'][name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),changed_bytes=len(changes),allowed_change_bytes=len(allowed),before=old,after=new,ordered_cluster_instances=len(walk(b,k,q)),pairs=details)

active=F.HEADER.unpack_from((C/active_name).read_bytes());fallback=F.HEADER.unpack_from((C/fallback_name).read_bytes())
source_active=F.HEADER.unpack_from((S/active_name).read_bytes())
report['strip_groups']={}
for name,kind in plan['strip_groups'].items():
    a=(S/name).read_bytes();b=(C/name).read_bytes();g=struct.unpack_from('<4s7I',b)
    original_g=struct.unpack_from('<4s7I',a)
    assert len(a)==len(b) and a[:16]==b[:16] and a[20:]==b[20:]
    logical=32+16*g[2]*g[3]
    assert g[:3]==(b'R4SG',1,active[6]) and 1<=g[3]<=8 and g[4:7]==(active[3],active[2],sh[5]) and zlib.crc32(b[32:logical])==g[7]
    assert original_g[4:7]==(source_active[3],source_active[2],sh[5]), 'source strip-group identity'
    def admits(raw,m):
        gg=struct.unpack_from('<4s7I',raw)
        return gg[:3]==(b'R4SG',1,m[6]) and 1<=gg[3]<=8 and gg[4:7]==(m[3],m[2],sh[5]) and len(raw)==32+16*gg[2]*gg[3] and zlib.crc32(raw[32:])==gg[7]
    assert kind in ('active','padded_active_reserve'), 'unsupported strip-group role'
    if kind=='active': assert admits(a,source_active) and admits(b,active)
    else:
        assert not admits(b,fallback)
        assert not admits(a,F.HEADER.unpack_from((S/fallback_name).read_bytes()))
        assert not any(b[logical:])
    report['strip_groups'][name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),records_identical=True,active_admission=admits(b,active),fallback_admission=admits(b,fallback))
print(json.dumps(report,indent=2))
