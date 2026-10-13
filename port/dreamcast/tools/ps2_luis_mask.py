#!/usr/bin/env python3
"""Prepare the complete pinned Luis hair with PS2 diffuse alpha for native review.

Usage (Windows Python with numpy/Pillow):
  ps2_luis_mask.py <luis model directory> <original pl14.dat> <proved runtime header> <fresh output>

The PS2 actor format viewer binds alpha to diffuse_map (see evidence below).
Keep that decoded RGBA source and the unused opacity-index image. Convert to
Dreamcast ARGB4444 using the existing native pair quantization, and measure its
loss. This is a native-look candidate, not proof of original GS blend registers
or animated appearance. No source triangle, vertex, normal, weight or ordering
changes; only undo the colour-atlas UV cell transform for the complete hair.
"""
import argparse,hashlib,json,struct,sys,zlib
from pathlib import Path
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'d367'),str(HERE/'d367/charbake')]
import model_registry as mr
import cb_tex as T
import ps2_cast as pc
from ps2_luis import PS2_SHA, character_image

COVERAGE_SHA='75c2655ee619f800e921850edcea9e0dffcc3af379996cfe9472f89929c36aa0'
HEADER_SHA='6fc181444d83b784780d2724732520e71b3c111eb7a7d7e77f35024659c92846'
VIEWER_COMMIT='ecd32acd1c62cf34ce4a6e958d8ea1ddafbd7dec'
VIEWER='https://github.com/JADERLINK/JADERLINK_MODEL_VIEWER/blob/'+VIEWER_COMMIT+'/'

def require(value,message):
    if not value:raise ValueError(message)

def sha(value):return hashlib.sha256(value).hexdigest()
def key(value):return(zlib.crc32(value)&0xffffffff,mr.digest(value)[2])
def key_text(value):return '%08x-%08x'%value

def source_uv(uv,coverage):
    aw,ah=coverage['atlas']['size'];x,y,w,h=coverage['atlas']['cells']['(5, 3)'];out=bytearray()
    for u,v in struct.iter_unpack('<2H',uv):
        un,vn=u*aw-x*32768,v*ah-y*32768
        require(un%w==vn%h==0 and 0<=un//w<=32768 and 0<=vn//h<=32768,'nonexact source UV inverse')
        out+=struct.pack('<2H',un//w,vn//h)
    return bytes(out),w,h

def prepare(model,archive,header,out):
    require(not out.exists(),'output already exists; choose a fresh directory')
    raw=archive.read_bytes();require(sha(raw)==PS2_SHA,'wrong source PS2 pl14 archive')
    manifest=(model/'coverage-manifest.json').read_bytes();require(sha(manifest)==COVERAGE_SHA,'wrong source coverage manifest')
    coverage=json.loads(manifest);hb=header.read_bytes();require(sha(hb)==HEADER_SHA,'unproved native runtime header')
    chunks,bones=mr.parse_header(str(header));require(bones==90,'wrong owner skeleton')
    c=next(c for c in chunks if c['source_info']==3);require(c['triangles']==1273,'incomplete hair')
    ps2={i+4:(tag,data) for i,tag,data in pc.pb.dat_entries(raw)}
    hair=pc.pb.parse_bin(ps2[6][1]);tris=pc.pb.triangles(hair)
    require(len(hair.materials)==1 and hair.materials[0]['raw']=='0403ff04ff000000000000ff30010000','different source hair material')
    require(len(tris)==1273 and all(material==0 for material,_ in tris),'hair source triangle/material coverage changed')
    decoder=pc.load_module('ps2_tpl_decode',pc.WA/'from-main/ps2-trees/tools/ps2_tpl_decode.py')
    tpl=ps2[5][1];parsed=decoder.parse_tpl(tpl);images=[];metadata=[]
    for i in (3,4):
        h=parsed['entries'][i];w,height,pixels,stats=decoder.decode(tpl,h)
        require((w,height)==(128,64),'wrong hair texture shape')
        require(((h['gs_tex0']>>34)&1)==1 and ((h['gs_tex0']>>35)&3)==0,'wrong source TEX0 alpha/function')
        pixels=bytes(pixels);image=character_image(Image.frombytes('RGBA',(w,height),pixels),h['interlace'])
        images.append(np.asarray(image).copy())
        metadata.append(dict(index=i,width=image.width,height=image.height,storage_size=[w,height],interlace=h['interlace'],character_orientation='transpose' if h['interlace']&1 else 'identity',oriented_rgba_sha256=sha(image.tobytes()),tex0='%016x'%h['gs_tex0'],TCC=1,TFX=0,decoded_rgba_sha256=sha(pixels),raw_alpha_histogram=stats['alpha_raw_hist']))
    colour=images[0][:,:,:3];alpha=images[0][:,:,3]
    uv,w,h=source_uv(c['uv'],coverage)
    require((w,h)==images[0].shape[1::-1] and images[0].shape==images[1].shape,'oriented hair texture/UV shape differs')
    ck=key(b'ps2-luis/diffuse-rgb/'+colour.tobytes());mk=key(b'ps2-luis/diffuse-alpha/'+alpha.tobytes())
    pk=key(b'R4MPv001'+struct.pack('<4I',*ck,*mk))
    words=((alpha.astype(np.uint16)//17)<<12)|((colour[:,:,0].astype(np.uint16)>>4)<<8)|((colour[:,:,1].astype(np.uint16)>>4)<<4)|(colour[:,:,2].astype(np.uint16)>>4)
    package=T.package_twiddled16('ps2_luis_source_diffuse_alpha',words,T.ARGB4444)
    info,decoded=T.decode(package)
    expected_rgb=(colour>>4)*17;expected_alpha=(alpha//17)*17
    require(np.array_equal(decoded[:,:,:3],expected_rgb) and np.array_equal(decoded[:,:,3],expected_alpha),'native package texel readback differs')
    out.mkdir(parents=True)
    (out/'source-hair.tpl').write_bytes(tpl)
    Image.fromarray(images[0]).save(out/'source-diffuse.png');Image.fromarray(images[1]).save(out/'source-opacity-index.png')
    Image.fromarray(colour).save(out/'colour.png');Image.fromarray(alpha).save(out/'mask.png');Image.fromarray(decoded).save(out/'pair.png')
    (out/'opaque.blob').write_bytes(b'');(out/'hair.blob').write_bytes(c['stream']);(out/'hair.uv').write_bytes(uv)
    pname=key_text(pk)+'.re4tex';(out/pname).write_bytes(package)
    delta=np.abs(decoded.astype(np.int16)-images[0].astype(np.int16));quant=dict(rule='RGB high nibble, alpha floor(decoded_PS2_alpha / 17); native ARGB4444 pair contract',max_error_rgba=[int(x) for x in delta.max(axis=(0,1))],mean_absolute_error_rgba=[float(x) for x in delta.mean(axis=(0,1))],source_nonzero_alpha=int((alpha>0).sum()),native_nonzero_alpha=int((decoded[:,:,3]>0).sum()),source_opaque=int((alpha==255).sum()),native_opaque=int((decoded[:,:,3]==255).sum()),source_levels=int(len(np.unique(alpha))),native_levels=int(len(np.unique(decoded[:,:,3]))))
    report=dict(tool='tools/ps2_luis_mask.py',status='Native-look candidate; PS2 diffuse alpha supported by format renderer, ARGB4444 quantization measured; original GS blend registers and animated look unverified',header_sha256=HEADER_SHA,coverage_manifest_sha256=COVERAGE_SHA,source_archive_sha256=PS2_SHA,source_material=hair.materials[0]['raw'],section=3,mask_only=True,triangles=dict(chunk=1273,opaque=0,hair=1273),texture=dict(width=w,height=h),keys=dict(colour=key_text(ck),mask=key_text(mk),pair=key_text(pk)),pair_package=dict(file=pname,sha256=sha(package),bytes=len(package),vram_bytes=w*h*2,format='ARGB4444 twiddled'),runs=dict(opaque=dict(triangles=0,bytes=0,sha256=sha(b'')),hair=dict(triangles=1273,bytes=len(c['stream']),sha256=sha(c['stream']),uv_bytes=len(uv),uv_sha256=sha(uv))),source_images=metadata,quantization=quant,evidence=dict(actor_loader=VIEWER+'ALL_VIEWER/RE4_PS2_MODEL_VIEWER/src/LoadPs2BinModel.cs#L291-L301',shader=VIEWER+'ALL_VIEWER/Resources/ObjShaderFrag.frag#L28-L42',interpretation='The format viewer binds both colour and alpha to diffuse_map and samples its alpha channel. The original PS2 TPL confirms TCC=1, MODULATE. Opacity-index image4 is preserved but not substituted for image3 alpha. This does not reproduce original PS2 GS blend/test registers.'))
    (out/'mask-runs.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('model','archive','header','output'):ap.add_argument(name,type=Path)
    a=ap.parse_args();result=prepare(a.model,a.archive,a.header,a.output)
    print(json.dumps({k:result[k] for k in ('status','triangles','keys','pair_package','quantization')},indent=2))

if __name__=='__main__':main()