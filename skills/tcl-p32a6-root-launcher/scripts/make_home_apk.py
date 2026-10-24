"""Keep original HOME declaration and add TCL launcher metadata only.
All original APK code/resources are retained byte-for-byte, except manifest.
"""
from pathlib import Path
import argparse, hashlib
import struct as s, zipfile, copy
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
source=args.source
if hashlib.sha256(source.read_bytes()).hexdigest()!='98824777eb845204fc82022a88b82dbce9940a802eaa0f55a28b58cdb9e5cacc':
    raise SystemExit('Expected the verified official LeanbackOnFire 1.63 APK; source hash mismatch')
if args.output.exists():
    raise SystemExit('Output already exists; choose a new path')
args.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(source) as z:
    xml=z.read('AndroidManifest.xml'); chunks=[]; pos=8
    while pos<len(xml):
        typ,hs,n=s.unpack_from('<HHI',xml,pos); chunks.append([typ,xml[pos:pos+n]]); pos+=n
    pool=next(c for t,c in chunks if t==1)
    _,hs,n,count,stylecount,flags,start,styles=s.unpack_from('<HHIIIIII',pool)
    assert stylecount==0 and styles==0
    def readlen(b,off,wide):
        if wide:
            v=s.unpack_from('<H',b,off)[0]; return ((v&32767)<<16|s.unpack_from('<H',b,off+2)[0],off+4) if v&32768 else (v,off+2)
        v=b[off]; return ((v&127)<<8|b[off+1],off+2) if v&128 else (v,off+1)
    strings=[]
    for i in range(count):
        off=start+s.unpack_from('<I',pool,hs+i*4)[0]
        if flags&256:
            _,off=readlen(pool,off,False); length,off=readlen(pool,off,False); st=pool[off:off+length].decode()
        else:
            length,off=readlen(pool,off,True); st=pool[off:off+length*2].decode('utf-16le')
        strings.append(st)
    newstrings=['com.tcl.app.type','com.tcl.ui']; indices={v:len(strings)+i for i,v in enumerate(newstrings)}
    strings+=newstrings
    data=bytearray(); offsets=[]
    def L8(n): return bytes([n]) if n<128 else bytes([(n>>8)|128,n&255])
    for st in strings:
        offsets.append(len(data)); utf16=st.encode('utf-16le')
        if flags&256:
            b=st.encode(); data+=L8(len(utf16)//2)+L8(len(b))+b+b'\0'
        else:
            assert len(utf16)//2<32768
            data+=s.pack('<H',len(utf16)//2)+utf16+b'\0\0'
    while len(data)%4:data+=b'\0'
    newstart=hs+4*len(strings)
    newpool=s.pack('<HHIIIIII',1,hs,newstart+len(data),len(strings),0,flags&~1,newstart,0)+b''.join(s.pack('<I',o) for o in offsets)+data
    template=None
    for i,(typ,c) in enumerate(chunks):
        if typ==0x102 and strings[s.unpack_from('<I',c,20)[0]]=='meta-data':
            ast,asz,ac=s.unpack_from('<HHH',c,24)
            attrs={strings[s.unpack_from('<I',c,16+ast+j*asz+4)[0]]:16+ast+j*asz for j in range(ac)}
            if 'value' in attrs and c[attrs['value']+15]==3:
                template=bytearray(c); end=chunks[i+1][1]; assert chunks[i+1][0]==0x103
                for key,value in [('name','com.tcl.app.type'),('value','com.tcl.ui')]:
                    off=attrs[key]; s.pack_into('<I',template,off+8,indices[value]); s.pack_into('<I',template,off+16,indices[value])
                break
    assert template is not None
    out=[]; inserted=False
    for typ,c in chunks:
        if typ==1:c=newpool
        if typ==0x103 and strings[s.unpack_from('<I',c,20)[0]]=='application':
            out.extend([bytes(template),end]); inserted=True
        out.append(c)
    assert inserted
    newxml=bytearray(xml[:8]+b''.join(out)); s.pack_into('<I',newxml,4,len(newxml))
    target=args.output
    with zipfile.ZipFile(target,'w') as dst:
        for info in z.infolist():
            up=info.filename.upper()
            if up.startswith('META-INF/') and (up.endswith(('.RSA','.DSA','.EC','.SF')) or up=='META-INF/MANIFEST.MF'):continue
            dst.writestr(copy.copy(info),newxml if info.filename=='AndroidManifest.xml' else z.read(info.filename))
    with zipfile.ZipFile(target) as dst:
        assert [x for x in dst.namelist() if dst.read(x)!=z.read(x)]==['AndroidManifest.xml']
print(target)
