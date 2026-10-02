import re,glob,os
R={}
for f in glob.glob('/root/probe/lanes/crowd/hw-cw-*.log'):
    n=os.path.basename(f)[6:-4]
    t=open(f).read()
    m=re.search(r'hardware projection\s+([\d.]+) ms/frame\s+\[low ([\d.]+) \.\. high ([\d.]+)\]',t)
    a=re.search(r'^actors\s+[\d.]+\s+[\d.]+\s+[-\d.]+\s+\|\s+[\d.]+\s+([\d.]+)',t,re.M)
    g=re.search(r'^game-render-side\s+[\d.]+\s+[\d.]+\s+[-\d.]+\s+\|\s+[\d.]+\s+([\d.]+)',t,re.M)
    gl=re.search(r'^game-logic\s+[\d.]+\s+[\d.]+\s+[-\d.]+\s+\|\s+[\d.]+\s+([\d.]+)',t,re.M)
    if m: R[n]=(float(m.group(1)),a and a.group(1),g and g.group(1),gl and gl.group(1))
arms=['g1','g1f','g1n2','c0','r1','r1c','r1c2','ck','ck2','ck3','r1n4','r1n2','r1d12','fn3','f12','p2','p2n3']
views=['e','l','s','b','b2','k']
print('arm '+' '.join('%-22s'%v for v in views))
for a in arms:
    print('%-6s'%a+' '.join('%-22s'%(('%.1f a%s r%s g%s'%R[a+'-'+v]) if a+'-'+v in R else '-') for v in views))
