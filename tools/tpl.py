"""GC TPL(0x0020AF30) 디코더. 모든 GX 텍스처 형식을 RGBA PIL 이미지로 푼다.

    import tpl
    for i, (im, info) in enumerate(tpl.decode(data)): im.save(f'{i}.png')

형식: 0 I4, 1 I8, 2 IA4, 3 IA8, 4 RGB565, 5 RGB5A3, 6 RGBA8,
      8 C4, 9 C8, 10 C14X2, 14 CMPR.  팔레트: 0 IA8, 1 RGB565, 2 RGB5A3.
`python tools/tpl.py <in.tpl> <out_dir>` 로 장마다 <번호>.png 를 쓴다.
"""
import os, struct, sys
from PIL import Image

FMT_NAME = {0: 'I4', 1: 'I8', 2: 'IA4', 3: 'IA8', 4: 'RGB565', 5: 'RGB5A3', 6: 'RGBA8',
            8: 'C4', 9: 'C8', 10: 'C14X2', 14: 'CMPR'}
# 블록 크기 (가로, 세로)
BLOCK = {0: (8, 8), 1: (8, 4), 2: (8, 4), 3: (4, 4), 4: (4, 4), 5: (4, 4), 6: (4, 4),
         8: (8, 8), 9: (8, 4), 10: (4, 4), 14: (8, 8)}


def c565(v):
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2), 255


def c5a3(v):
    if v & 0x8000:
        r, g, b = (v >> 10) & 31, (v >> 5) & 31, v & 31
        return (r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 255
    a = (v >> 12) & 7
    return ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, (a << 5) | (a << 2) | (a >> 1)


def cia8(v):
    i = v & 255
    return i, i, i, v >> 8


def data_size(w, h, fm):
    bw, bh = BLOCK[fm]
    bpp = {0: 4, 8: 4, 14: 4, 1: 8, 2: 8, 9: 8}.get(fm, 32 if fm == 6 else 16)
    return ((w + bw - 1) // bw * bw) * ((h + bh - 1) // bh * bh) * bpp // 8


def decode_image(d, w, h, fm, off, pal=None):
    bw, bh = BLOCK[fm]
    W = (w + bw - 1) // bw * bw
    H = (h + bh - 1) // bh * bh
    out = bytearray(W * H * 4)
    p = off
    pal = pal or []
    np_ = len(pal)

    def put(x, y, c):
        o = (y * W + x) * 4
        out[o:o + 4] = bytes(c)

    for by in range(0, H, bh):
        for bx in range(0, W, bw):
            if fm == 14:
                for s in range(4):
                    c0, c1, bits = struct.unpack_from('>HHI', d, p); p += 8
                    a, b = c565(c0), c565(c1)
                    if c0 > c1:
                        cs = [a, b, tuple((2 * a[i] + b[i]) // 3 for i in range(3)) + (255,),
                              tuple((a[i] + 2 * b[i]) // 3 for i in range(3)) + (255,)]
                    else:
                        cs = [a, b, tuple((a[i] + b[i]) // 2 for i in range(3)) + (255,), (0, 0, 0, 0)]
                    sx = bx + (s & 1) * 4; sy = by + (s >> 1) * 4
                    for i in range(16):
                        put(sx + (i & 3), sy + (i >> 2), cs[(bits >> (30 - 2 * i)) & 3])
            elif fm == 6:
                ar = d[p:p + 32]; gb = d[p + 32:p + 64]; p += 64
                for i in range(16):
                    put(bx + (i & 3), by + (i >> 2), (ar[2 * i + 1], gb[2 * i], gb[2 * i + 1], ar[2 * i]))
            else:
                for y in range(bh):
                    for x in range(bw):
                        if fm in (0, 8):
                            v = (d[p + (x >> 1)] >> (4 * (1 - (x & 1)))) & 15
                            if fm == 0:
                                c = (v * 17,) * 3 + (255,)
                            else:
                                c = pal[v] if v < np_ else (0, 0, 0, 0)
                        elif fm in (1, 9):
                            v = d[p + x]
                            c = (v, v, v, 255) if fm == 1 else (pal[v] if v < np_ else (0, 0, 0, 0))
                        elif fm == 2:
                            v = d[p + x]
                            c = ((v & 15) * 17,) * 3 + ((v >> 4) * 17,)
                        else:  # 16비트
                            v = (d[p + 2 * x] << 8) | d[p + 2 * x + 1]
                            if fm == 3:
                                c = (v & 255,) * 3 + (v >> 8,)
                            elif fm == 4:
                                c = c565(v)
                            elif fm == 5:
                                c = c5a3(v)
                            else:  # C14X2
                                v &= 0x3FFF
                                c = pal[v] if v < np_ else (0, 0, 0, 0)
                        put(bx + x, by + y, c)
                    p += {0: 4, 8: 4, 1: 8, 9: 8, 2: 8}.get(fm, 8)
    im = Image.frombytes('RGBA', (W, H), bytes(out))
    if (W, H) != (w, h):
        im = im.crop((0, 0, w, h))
    return im


def entries(d):
    assert d[:4] == b'\x00\x20\xaf\x30', 'not TPL'
    n, to = struct.unpack_from('>II', d, 4)
    res = []
    for j in range(n):
        ih, ph = struct.unpack_from('>II', d, to + 8 * j)
        h, w, fm, off = struct.unpack_from('>HHII', d, ih)
        info = dict(index=j, w=w, h=h, fmt=fm, fmt_name=FMT_NAME.get(fm, str(fm)), off=off, pal=None)
        if ph:
            pn, _, pf, po = struct.unpack_from('>HBxII', d, ph)
            info['pal'] = (pn, pf, po)
        res.append(info)
    return res


def decode(d):
    for info in entries(d):
        pal = None
        if info['pal']:
            pn, pf, po = info['pal']
            conv = {0: cia8, 1: c565, 2: c5a3}[pf]
            pal = [conv(struct.unpack_from('>H', d, po + 2 * i)[0]) for i in range(pn)]
        yield decode_image(d, info['w'], info['h'], info['fmt'], info['off'], pal), info


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    os.makedirs(sys.argv[2], exist_ok=True)
    for im, info in decode(d):
        im.save(os.path.join(sys.argv[2], f"{info['index']}.png"))
        print(info['index'], info['w'], info['h'], info['fmt_name'])
