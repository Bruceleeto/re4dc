#!/usr/bin/env python3
"""Read-only texture, UV-repeat and material-state census for world packages.

Only JSON reports are written. No game package, fixture or source asset changes.
"""
import sys, json, struct, hashlib, math, collections, zlib, argparse
from pathlib import Path
from types import SimpleNamespace

def parse_args():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mesh',type=Path,required=True,help='prelit R4IM v3 package')
    ap.add_argument('--sidecar',type=Path,required=True,help='matching R4PW placement/material sidecar')
    ap.add_argument('--spatial-first-mesh',type=int,required=True,
                    help='first appended batch mesh; use the mesh count if none are appended')
    ap.add_argument('--expect-mesh-sha256',help='optional input identity pin')
    ap.add_argument('--fixture',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    return ap.parse_args()

def build(args):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import packages as F
    OUT=args.out
    OUT.mkdir(parents=True,exist_ok=True)
    mesh_bytes=args.mesh.read_bytes()
    mesh=F.read(mesh_bytes)
    assert 0<=args.spatial_first_mesh<=len(mesh['meshes']), 'spatial-first-mesh outside package'
    if args.expect_mesh_sha256:
        assert hashlib.sha256(mesh_bytes).hexdigest()==args.expect_mesh_sha256, 'mesh identity mismatch'
    h,meta,places=F.side_read(args.sidecar,mesh)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    fx=json.loads(args.fixture.read_text())['replace']
    def fixture_path(value):
        path=Path(value)
        return path if path.is_absolute() else args.fixture.parent/path
    packpath=fixture_path(fx['dc/tex.pak']);pack=packpath.read_bytes()
    assert pack[:8]==b'RE4PAK1\0'
    ver,n,idx,data,crc=struct.unpack_from('<5I',pack,8)
    packidx={}
    for i in range(n):
        a,b,o,s=struct.unpack_from('<4I',pack,idx+16*i);packidx[(a,b)]=(o,s)
    texs={};payloads={};codebooks={}
    def readtex(key):
        if key in texs:return texs[key]
        a,b=(int(x,16) for x in key.split('-'))
        if (a,b) in packidx:
            off,size=packidx[a,b];blob=pack[off:off+size];source=str(packpath)+':'+str(off)
        else:
            k=f'dc/tex/{a>>28:x}/{a:08x}-{b:08x}.re4tex'
            if k not in fx:raise ValueError('Texture missing from pack and fixture: '+k)
            source=str(fixture_path(fx[k]));blob=Path(source).read_bytes()
        head=struct.unpack_from('<8s10I',blob)
        assert head[0]==b'RE4DCTX\0' and head[1]==2 and head[4]==1
        ts=[]
        for i in range(head[4]):
            t=struct.unpack_from('<64s8I',blob,head[5]+i*head[3])
            name,w,h,fmt,off,size,flags,pay,res=t
            p=blob[off:off+size]
            assert len(p)==size,(key,len(p),size,head,t)
            row=dict(name=name.rstrip(b'\0').decode(errors='replace'),width=w,height=h,format=fmt,
                payload=pay,bytes=size,flags=flags,payload_sha256=sha(p))
            if pay==2 and fmt<3:
                cb=[p[j:j+8] for j in range(0,2048,8)]
                used=set(p[2048:]);usedcb={cb[j] for j in used}
                row.update(used_vq_entries=len(used),distinct_used_vq_vectors=len(usedcb))
                if not (flags&4):codebooks[key]=usedcb
            if fmt>=3:row['palette_sha256']=sha(p[-32:])
            ts.append(row);payloads[key]=p
        t=dict(key=key,source=source,package_sha256=sha(blob),header_flags=head[10],textures=ts,
            header_crc_matches_runtime=zlib.crc32(blob[head[2]:])==head[8],
            header_crc_matches_payload_only=zlib.crc32(blob[head[6]:head[6]+head[7]])==head[8],
            resident_bytes=sum(t['bytes'] for t in ts))
        texs[key]=t
        return t

    parts=[]
    for mi,m in enumerate(mesh['meshes']):
        for pi in range(m[6],m[6]+m[7]):
            part=mesh['parts'][pi];md=meta[pi]
            if not part[7]:continue
            key=f'{md[0]:08x}-{md[1]:08x}'
            tex=readtex(key);t=tex.get('textures',[{}])[0]
            refs=set()
            for li in range(part[6],part[6]+part[7]):
                corners,strips=F.let_corners(mesh,mesh['lets'][li]);refs.update(corners[c] for s in strips for c in s)
            uv=[(part[8]+part[10]*mesh['verts'][v][3],part[9]+part[11]*mesh['verts'][v][4]) for v in refs]
            bounds=[min(v[k] for v in uv) for k in range(2)]+[max(v[k] for v in uv) for k in range(2)]
            spans=[bounds[k+2]-bounds[k] for k in range(2)]
            w,h=t.get('width',0),t.get('height',0)
            # A finite periodic texel patch, including one bilinear gutter texel per side.
            # Rectangle is deliberately conservative: all referenced levels and disconnected islands.
            pixels=[math.ceil(bounds[k+2]*dim)-math.floor(bounds[k]*dim)+2 for k,dim in enumerate((w,h))]
            row=dict(mesh=mi,part=pi,spatial_batch=mi>=args.spatial_first_mesh,key=key,pass_id=md[4],cull=md[5],
                source_size=list(md[2:4]),side_flags=list(md[6:]),part_flags=part[2:6],uv_bounds=bounds,
                uv_span=spans,has_repeat=any(x>1.000001 for x in spans),uv_outside_unit=any(bounds[k]<-1e-6 or bounds[k+2]>1.000001 for k in range(2)),
                referenced_vertices=len(refs),meshlets=part[7],patch_pixels=pixels,
                finite_patch_16bit_bytes=2*pixels[0]*pixels[1],format=t.get('format'),payload=t.get('payload'))
            parts.append(row)

    for key,t in texs.items():
        use=[p for p in parts if p['key']==key]
        t.update(parts=[p['part'] for p in use],spatial_parts=[p['part'] for p in use if p['spatial_batch']],
            nonspatial_parts=[p['part'] for p in use if not p['spatial_batch']],pass_ids=sorted({p['pass_id'] for p in use}))

    cells=[]
    for mi in range(args.spatial_first_mesh,len(mesh['meshes'])):
        ps=[p for p in parts if p['mesh']==mi]
        groups=collections.defaultdict(list)
        # Sidecar texture and MeshPart.texture are source indices, replaced by the atlas identity.
        # Keep pass, cull, sidecar reserved (vertex alpha), MeshPart alpha/flags/reserved.
        for p in ps:groups[(p['pass_id'],p['cull'],p['side_flags'][1],*p['part_flags'][1:])].append(p)
        gs=[]
        for state,pp in groups.items():
            keys=sorted({p['key'] for p in pp})
            compatible_vq=all(k in codebooks for k in keys) and len({texs[k]['textures'][0]['format'] for k in keys})==1
            union=len(set().union(*(codebooks[k] for k in keys))) if compatible_vq else None
            gs.append(dict(state=list(state),parts=[p['part'] for p in pp],keys=keys,
                vq_original_vector_union=union,lossless_vq_codebook_possible=union is not None and union<=256,
                sum_raw_tile_16bit_bytes=sum(2*texs[k]['textures'][0]['width']*texs[k]['textures'][0]['height'] for k in keys),
                sum_finite_patch_16bit_bytes=sum(p['finite_patch_16bit_bytes'] for p in pp)))
        cells.append(dict(mesh=mi,parts=len(ps),keys=len({p['key'] for p in ps}),state_groups=len(groups),groups=gs))

    def summary(ps):
        keys={p['key'] for p in ps}
        return dict(parts=len(ps),unique_textures=len(keys),unique_resident_bytes=sum(texs[k]['resident_bytes'] for k in keys),
            format_payload_counts=dict(collections.Counter(str((texs[k]['textures'][0]['format'],texs[k]['textures'][0]['payload'])) for k in keys)),
            repeating_parts=sum(p['has_repeat'] for p in ps),outside_unit_parts=sum(p['uv_outside_unit'] for p in ps),
            max_uv_span=[max((p['uv_span'][k] for p in ps),default=0) for k in range(2)],
            finite_patch_16bit_bytes=sum(p['finite_patch_16bit_bytes'] for p in ps))
    result=dict(scope='Asset-wide census; not a visible drawlist. All referenced levels of the supplied packages.',
        sources=dict(mesh=str(args.mesh),mesh_sha256=sha(mesh_bytes),
            sidecar=str(args.sidecar),sidecar_sha256=sha(args.sidecar.read_bytes()),spatial_first_mesh=args.spatial_first_mesh,
            fixture=str(args.fixture),fixture_sha256=sha(args.fixture.read_bytes()),tex_pack=str(packpath),tex_pack_sha256=sha(pack)),
        all=summary(parts),opaque=summary([p for p in parts if p['pass_id']==0]),
        spatial=summary([p for p in parts if p['spatial_batch']]),spatial_state_groups=sum(c['state_groups'] for c in cells),
        textures=list(texs.values()),parts=parts,cells=cells)
    (OUT/'census.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return SimpleNamespace(**locals())

if __name__=='__main__':
    c=build(parse_args())
    print(json.dumps({k:v for k,v in c.result.items() if k not in ['textures','parts','cells']},indent=2,sort_keys=True))
