"""SFD 묶음(.BIN, 매직 'SFD\\0') 풀기·묶기와 안의 HSD/N40 모델 그림 꺼내기.

SFD 구조 (빅엔디언)
    +0  'SFD\\0'
    +4  u32 항목 수 n
    +8  n × (u32 오프셋, u32 크기)      이름 칸 없음, 압축 없음
    첫 항목은 0x8000, 이후 항목은 0x800 정렬, 빈 곳은 0으로 채움,
    파일 끝도 0x800 정렬.

항목(하위 파일) 종류
    HSD : HAL sysdolphin DAT. 머리 0x20(파일 크기, 데이터 크기, 재배치 수,
          루트 수, 참조 수), 포인터는 +0x20 기준. 루트 이름은 'scene_data'.
          하나의 항목 안에 HSD가 여러 개 붙어 있기도 하다(32바이트 정렬).
    N40 : 머리 0x40짜리 변형. h[1]=파일 크기, h[6]=재배치 표 위치(항목 기준),
          h[7]=재배치 수, 포인터는 +0x40 기준. chara·snr_chara·weapon_* 등.
    그림 기술자는 둘 다 HSD ImageDesc 와 같다:
          u32 그림 포인터, u16 폭, u16 높이, u32 GX 형식, u32 밉맵, f32×2 LOD
    TObj +0x4C 가 ImageDesc, +0x50 이 TlutDesc(u32 포인터, u32 형식, u32, u16 개수).

    import sfd
    ents = sfd.unpack(data)            # [bytes, ...]
    assert sfd.pack(ents) == data      # 무변경 왕복
    for blob, kind, off in sfd.blobs(ents[0]): ...
    for t in sfd.textures(blob, kind): t['image'] (PIL)
"""
import struct
from PIL import Image

MAGIC = b'SFD\0'


# ---------------------------------------------------------------- SFD 묶음
def unpack(d):
    assert d[:4] == MAGIC, 'SFD 아님'
    n = struct.unpack('>I', d[4:8])[0]
    return [d[o:o + s] for o, s in (struct.unpack('>II', d[8 + 8 * i:16 + 8 * i]) for i in range(n))]


def pack(ents, first=0x8000, align=0x800):
    n = len(ents)
    assert 8 + 8 * n <= first
    out = bytearray(first)
    out[:8] = MAGIC + struct.pack('>I', n)
    for i, e in enumerate(ents):
        o = len(out)
        struct.pack_into('>II', out, 8 + 8 * i, o, len(e))
        out += e
        out += b'\0' * ((-len(out)) % align)
    return bytes(out)


# ---------------------------------------------------------------- 하위 파일
def hsd_at(e, o):
    if o + 0x20 > len(e):
        return None
    fs, ds, rc, nr, nf = struct.unpack('>5I', e[o:o + 20])
    if not (0x40 < fs <= len(e) - o and ds < fs and 1 <= nr + nf < 64 and rc < fs // 4):
        return None
    st = 0x20 + ds + rc * 4 + (nr + nf) * 8
    if st >= fs or e[o + 20:o + 0x20] != b'\0' * 12:
        return None
    names = []
    for k in range(nr + nf):
        q = o + 0x20 + ds + rc * 4 + 8 * k
        so = struct.unpack('>I', e[q + 4:q + 8])[0]
        a = o + st + so
        z = e.find(b'\0', a, o + fs) if a < o + fs else -1
        if z <= a:
            return None
        try:
            names.append(e[a:z].decode('ascii'))
        except UnicodeDecodeError:
            return None
    return fs, names


def n40_at(e, o):
    if o + 0x40 > len(e):
        return None
    h = struct.unpack('>16I', e[o:o + 0x40])
    if h[0] != 0x40:
        return None
    fs, ro, rc = h[1], h[6], h[7]
    if not (0x40 < fs <= len(e) - o and 0 < rc < 0x100000 and ro + rc * 4 <= fs):
        return None
    return fs, h


def blobs(e):
    """항목 안의 HSD/N40 하위 파일을 (bytes, 'hsd'|'n40', 위치) 로 돌려준다."""
    out, i = [], 0
    while i < len(e):
        r = hsd_at(e, i)
        k = 'hsd'
        if not r:
            r = n40_at(e, i)
            k = 'n40'
        if r:
            out.append((e[i:i + r[0]], k, i))
            i += (r[0] + 31) & ~31
        else:
            i += 32
    return out


def relocs(b, kind):
    """(포인터 기준, 재배치 위치 목록, 데이터 크기)"""
    if kind == 'hsd':
        fs, ds, rc = struct.unpack('>3I', b[:12])
        base = 0x20
        rel = struct.unpack('>%dI' % rc, b[0x20 + ds:0x20 + ds + 4 * rc])
        return base, rel, ds
    h = struct.unpack('>16I', b[:0x40])
    rel = struct.unpack('>%dI' % h[7], b[h[6]:h[6] + 4 * h[7]])
    return 0x40, rel, len(b) - 0x40


# ---------------------------------------------------------------- GX 그림
BLK = {0: (8, 8, 4), 1: (8, 4, 8), 2: (8, 4, 8), 3: (4, 4, 16), 4: (4, 4, 16), 5: (4, 4, 16),
       6: (4, 4, 32), 8: (8, 8, 4), 9: (8, 4, 8), 10: (4, 4, 16), 14: (8, 8, 4)}
FMT = {0: 'I4', 1: 'I8', 2: 'IA4', 3: 'IA8', 4: 'RGB565', 5: 'RGB5A3', 6: 'RGBA8',
       8: 'C4', 9: 'C8', 10: 'C14X2', 14: 'CMPR'}


def tex_size(w, h, f):
    bw, bh, bpp = BLK[f]
    return ((w + bw - 1) // bw) * ((h + bh - 1) // bh) * bw * bh * bpp // 8


def c565(v):
    return ((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, 255


def c5a3(v):
    if v & 0x8000:
        return ((v >> 10) & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, (v & 31) * 255 // 31, 255
    return ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, ((v >> 12) & 7) * 255 // 7


def palette(d, n, pf):
    out = []
    for i in range(n):
        v = struct.unpack('>H', d[2 * i:2 * i + 2])[0]
        out.append((v >> 8, v >> 8, v >> 8, v & 255) if pf == 0 else c565(v) if pf == 1 else c5a3(v))
    return out


def decode(d, w, h, f, pal=None):
    """GX 텍스처 → PIL RGBA. d 는 그림 데이터 시작부터."""
    im = Image.new('RGBA', (w, h))
    px = im.load()
    bw, bh, bpp = BLK[f]
    p = 0
    gray = [(i * 17,) * 3 + (255,) for i in range(16)]
    pal = pal or []
    for by in range(0, h, bh):
        for bx in range(0, w, bw):
            if f == 14:
                cells = []
                for s in range(4):
                    c0, c1, bits = struct.unpack('>HHI', d[p:p + 8]); p += 8
                    a, b = c565(c0), c565(c1)
                    if c0 > c1:
                        cs = [a, b, tuple((2 * a[i] + b[i]) // 3 for i in range(4)),
                              tuple((a[i] + 2 * b[i]) // 3 for i in range(4))]
                    else:
                        cs = [a, b, tuple((a[i] + b[i]) // 2 for i in range(4)), (0, 0, 0, 0)]
                    sx, sy = bx + (s & 1) * 4, by + (s >> 1) * 4
                    for i in range(16):
                        x, y = sx + i % 4, sy + i // 4
                        if x < w and y < h:
                            px[x, y] = cs[(bits >> (30 - 2 * i)) & 3]
                continue
            if f == 6:
                ar, gb = d[p:p + 32], d[p + 32:p + 64]; p += 64
                for i in range(16):
                    x, y = bx + i % 4, by + i // 4
                    if x < w and y < h:
                        px[x, y] = (ar[2 * i + 1], gb[2 * i], gb[2 * i + 1], ar[2 * i])
                continue
            for y in range(bh):
                for x in range(bw):
                    if bpp == 4:
                        v = (d[p + (x >> 1)] >> (4 * (1 - (x & 1)))) & 15
                    elif bpp == 8:
                        v = d[p + x]
                    else:
                        v = struct.unpack('>H', d[p + 2 * x:p + 2 * x + 2])[0]
                    if f == 0: c = gray[v]
                    elif f == 1: c = (v, v, v, 255)
                    elif f == 2: c = ((v & 15) * 17,) * 3 + ((v >> 4) * 17,)
                    elif f == 3: c = ((v & 255),) * 3 + (v >> 8,)
                    elif f == 4: c = c565(v)
                    elif f == 5: c = c5a3(v)
                    elif f == 10: v &= 0x3FFF; c = pal[v] if v < len(pal) else (255, 0, 255, 255)
                    else: c = pal[v] if v < len(pal) else (255, 0, 255, 255)
                    X, Y = bx + x, by + y
                    if X < w and Y < h:
                        px[X, Y] = c
                p += bw * bpp // 8
    return im


def textures(b, kind, want_image=True):
    """하위 파일 안의 그림 기술자를 찾아 dict 목록으로."""
    base, rel, ds = relocs(b, kind)
    rs = set(rel)
    u32 = lambda o: struct.unpack('>I', b[base + o:base + o + 4])[0]
    descs = {}
    for r in rel:
        if base + r + 4 > len(b):
            continue
        t = u32(r)
        if t not in rs or base + t + 0x18 > len(b):
            continue
        ip = u32(t)
        w, h, f = struct.unpack('>HHI', b[base + t + 4:base + t + 12])
        if not (0 < w <= 1024 and 0 < h <= 1024 and f in BLK):
            continue
        if base + ip + tex_size(w, h, f) > len(b):
            continue
        descs.setdefault(t, (ip, w, h, f, []))[4].append(r)
    out = []
    for t, (ip, w, h, f, refs) in sorted(descs.items()):
        pal, tl = None, None
        if f in (8, 9, 10):
            for r in refs:   # TObj+0x4C → +0x50 이 TlutDesc
                if r + 4 in rs:
                    q = u32(r + 4)
                    if q in rs and base + q + 14 <= len(b):
                        pp, pf, _, pn = struct.unpack('>IIIH', b[base + q:base + q + 14])
                        if pf <= 2 and 0 < pn <= 16384 and base + pp + 2 * pn <= len(b):
                            tl = (pp, pf, pn)
                            pal = palette(b[base + pp:], pn, pf)
                            break
        x = dict(desc=t, ptr=ip, w=w, h=h, fmt=f, tlut=tl,
                 data=b[base + ip:base + ip + tex_size(w, h, f)])
        if want_image:
            x['image'] = decode(x['data'], w, h, f, pal)
        out.append(x)
    return out
