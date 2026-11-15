"""입체 지역 이름판(3D 글자 메시) 한글화.

대상: /scenario_jp/snr_obj.BIN 항목 54~66(13종). 같은 HSD 사본이 rpg_f_models·rpg_t_models 항목 0(10종)·1(3종)에도 있다.

이름판 HSD(scene_data) 구조(조사 11/13):
- JObj 하나에 DObj 여러 개. 그림 없는 DObj = 글자(흰색, 색 표 2번), 그림 있는 DObj 2개 = 판 배경(사각형)·테두리.
- 글자는 두께 없는 평면(z = 0.08) 삼각형, 시계 방향. 정점 속성 POS(index16, float xyz) + CLR0(index8, RGBA8 색 표).
- 일본판은 글자 조각마다 DObj 를 나눴고 북미판은 글자 전체를 DObj 하나로 넣었다(판도 조금 넓힘).

방법(덧붙이기): 원래 데이터는 그대로 두고 데이터 끝에 새 정점 표·표시 목록·VtxDesc·PObj·DObj 를 붙인 뒤
JObj 의 첫 DObj 포인터를 새 글자 DObj 로 바꾼다. 새 DObj 의 다음은 원래 판 배경 DObj(첫 그림 DObj).
원래 글자 DObj 들은 쓰이지 않는 채 남는다. 재배치 표에 새 포인터 칸을 더하고 머리(크기·재배치 수)를 고친다.

글자 모양: G마켓 산스 Bold 윤곽(fontTools) → 곡선 펴기 → 구멍 판정(shapely) → earcut 삼각형.
크기: 글자 잉크 높이 0.52, 세로 가운데 -0.01(원본 글자 y -0.27~0.25), 폭이 MAX_W 를 넘으면 가로만 줄임.

    python tools/sign3d.py preview       # work/graphics/workdata/sign3d-v01/ 에 삼각형 그림
"""
import os, struct, sys
import numpy as np
import mapbox_earcut as earcut
from shapely.geometry import Polygon
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
sys.path.insert(0, os.path.dirname(__file__))
import disc, sfd

FONT = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Fonts', 'GmarketSansBold.otf')
TEXT_H, TEXT_CY, MAX_W, Z = 0.52, -0.01, 3.77, 0.08
# 글자 색 번호는 판마다 원래 글자가 쓰던 번호를 읽음(orig_text_color). 2번 고정이던 v0.22 까지 57 시험장·62 경찰대 본부는
# 2번 = 회색(b2b2b2)이라 글자가 회색으로 나왔음(11/14 사용자 실기 제보: 시험장).
SIGNS = {54: '스틸하츠', 55: '자택 앞', 56: '랩', 57: '시험장', 58: '트레이닝 짐', 59: '보기의 가게',
         60: '레스토랑 다이몬', 61: '블렌드 파크', 62: '경찰대 본부', 63: '해리와 미라의 집', 64: '돔',
         65: '유원지', 66: '젝스의 아지트'}


# ---------------------------------------------------------------- 글자 윤곽 → 삼각형
class FlatPen(BasePen):
    def __init__(self, gs, steps=8):
        super().__init__(gs); self.rings = []; self.cur = []; self.steps = steps
    def _moveTo(self, p): self.cur = [p]
    def _lineTo(self, p): self.cur.append(p)
    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps; u = 1 - t
            self.cur.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                             u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps; u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    def _closePath(self):
        r = self.cur
        if len(r) > 1 and r[0] == r[-1]: r = r[:-1]
        if len(r) >= 3: self.rings.append(r)
        self.cur = []
    _endPath = _closePath


def glyph_triangles(text, font_path=FONT):
    """글자열 → 삼각형 목록 [(x,y)*3] (글꼴 단위, 왼쪽부터 전진 폭으로 배치)."""
    f = TTFont(font_path); gs = f.getGlyphSet(); cmap = f.getBestCmap(); hmtx = f['hmtx']
    x0 = 0; tris = []
    for ch in text:
        gn = cmap[ord(ch)]
        pen = FlatPen(gs); gs[gn].draw(pen)
        rings = [[(x + x0, y) for x, y in r] for r in pen.rings]
        x0 += hmtx[gn][0]
        if not rings: continue
        polys = [Polygon(r).buffer(0) for r in rings]
        # 고리 전체가 다른 고리 안에 홀수 번 들어 있으면 구멍(대표점으로 재면 ㅇ 의 바깥 고리 점이 구멍 안에 찍혀 틀림)
        inside = lambda i, j: i != j and polys[j].area > polys[i].area and polys[j].contains(polys[i])
        depth = [sum(1 for j in range(len(polys)) if inside(i, j)) for i in range(len(polys))]
        for i, r in enumerate(rings):
            if depth[i] % 2: continue
            holes = [rings[j] for j in range(len(rings)) if depth[j] == depth[i] + 1 and inside(j, i)]
            pts = np.array(r + sum(holes, []), dtype=np.float64)
            ends = np.cumsum([len(r)] + [len(h) for h in holes]).astype(np.uint32)
            for k in earcut.triangulate_float64(pts, ends).reshape(-1, 3):
                tris.append([tuple(pts[k[0]]), tuple(pts[k[1]]), tuple(pts[k[2]])])
    return tris


def place(tris):
    """글꼴 단위 삼각형 → 이름판 좌표(가운데 정렬, 높이 TEXT_H, 폭 MAX_W 이하), 시계 방향으로 맞춤."""
    a = np.array(tris)                      # (T, 3, 2)
    xmin, ymin = a[..., 0].min(), a[..., 1].min(); xmax, ymax = a[..., 0].max(), a[..., 1].max()
    s = TEXT_H / (ymax - ymin); sx = min(s, MAX_W / (xmax - xmin))
    out = np.empty_like(a)
    out[..., 0] = (a[..., 0] - (xmin + xmax) / 2) * sx
    out[..., 1] = (a[..., 1] - (ymin + ymax) / 2) * s + TEXT_CY
    res = []
    for t in out:
        (ax, ay), (bx, by), (cx, cy) = t
        area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(area) < 1e-12: continue
        res.append([tuple(t[0]), tuple(t[2]), tuple(t[1])] if area > 0 else [tuple(p) for p in t])   # 시계 방향
    return res, sx / s


# ---------------------------------------------------------------- HSD 고치기(덧붙이기)
def _u32(b, o): return struct.unpack('>I', b[o:o + 4])[0]


def orig_text_color(data, text_dobjs):
    """원래 글자 DObj 들의 표시 목록에서 가장 많이 쓴 CLR0 색 번호(POS idx16 + CLR0 idx8 정점)."""
    import collections
    u32 = lambda o: _u32(data, o)
    cnt = collections.Counter()
    for d in text_dobjs:
        po = u32(d + 0xC)
        while po:
            n32 = struct.unpack('>H', data[po + 0xE:po + 0x10])[0]; q = u32(po + 0x10); end = q + n32 * 32
            while q < end and data[q]:
                n = struct.unpack('>H', data[q + 1:q + 3])[0]; q += 3
                for _ in range(n): cnt[data[q + 2]] += 1; q += 3
            po = u32(po + 4)
    assert cnt, '원래 글자 색 번호를 못 읽음'
    return cnt.most_common(1)[0][0]


def replace_text(blob, tris):
    """이름판 HSD 한 개 → 글자 DObj 를 새 삼각형으로 바꾼 HSD."""
    base = 0x20
    fs, ds, rc, rt, rf = struct.unpack('>5I', blob[:20])
    data = bytearray(blob[base:base + ds])
    rel = list(struct.unpack('>%dI' % rc, blob[base + ds:base + ds + rc * 4]))
    tail = blob[base + ds + rc * 4:]                       # 루트 표 + 이름 표(데이터 기준 오프셋이라 그대로 씀)
    u32 = lambda o: _u32(data, o)
    root = _u32(tail, 0); js = u32(root); jo = u32(u32(js))
    dobjs = []; d = u32(jo + 0x10)
    while d: dobjs.append(d); d = u32(d + 4)
    text = [d for d in dobjs if not u32(u32(d + 8) + 8)]
    pics = [d for d in dobjs if u32(u32(d + 8) + 8)]
    assert text and len(pics) == 2, ('DObj 구조가 예상과 다름', [hex(x) for x in dobjs])   # 57(시험장)은 테두리·배경·글자 순서
    t0 = text[0]; mobj = u32(t0 + 8); po0 = u32(t0 + 0xC); vd0 = u32(po0 + 8)
    clr_ptr = u32(vd0 + 24 + 20)
    assert u32(vd0) == 9 and u32(vd0 + 24) == 11 and u32(vd0 + 48) == 0xFF, 'VtxDesc 가 POS·CLR0 이 아님'
    color_index = orig_text_color(data, text)   # 판마다 색 표가 다름(57 시험장은 1번이 흰색, 나머지는 2번 — 11/14 실기 회색)

    def align(n=32):
        while len(data) % n: data.append(0)

    def ptr_field(off, val):
        struct.pack_into('>I', data, off, val)
        if off not in rel: rel.append(off)

    # 정점(같은 점은 하나로)
    verts = {}; idx = []
    for t in tris:
        for p in t:
            k = (round(p[0], 5), round(p[1], 5))
            if k not in verts: verts[k] = len(verts)
            idx.append(verts[k])
    assert len(verts) < 0x10000
    align(); pos_off = len(data)
    for (x, y) in verts: data += struct.pack('>3f', x, y, Z)
    # 표시 목록: GX_TRIANGLES(0x90, VAT 0), 정점마다 POS idx16 + CLR0 idx8
    align(); dl_off = len(data)
    data += struct.pack('>BH', 0x90, len(idx))
    for i in idx: data += struct.pack('>HB', i, color_index)
    data.append(0); align(); dl_n = (len(data) - dl_off) // 32
    assert dl_n < 0x10000
    # VtxDesc(원본 복사 후 포인터만)
    align(); vd_off = len(data); data += data[vd0:vd0 + 72]
    ptr_field(vd_off + 20, pos_off); ptr_field(vd_off + 24 + 20, clr_ptr)
    # PObj(원본 복사)
    align(); po_off = len(data); data += data[po0:po0 + 0x18]
    struct.pack_into('>I', data, po_off + 4, 0)                      # next 없음
    ptr_field(po_off + 8, vd_off)
    struct.pack_into('>H', data, po_off + 0xE, dl_n)
    ptr_field(po_off + 0x10, dl_off)
    # DObj: 다음 = 판 배경 DObj, MObj = 원래 글자 MObj
    align(); do_off = len(data); data += bytes(0x10)
    ptr_field(do_off + 4, pics[0]); ptr_field(do_off + 8, mobj); ptr_field(do_off + 0xC, po_off)
    align()
    # 그림 DObj 둘을 원래 순서대로 다시 잇고 마지막은 끝(0, 재배치에서도 뺌) — 원래 글자 DObj 가 사슬에서 빠짐
    ptr_field(pics[0] + 4, pics[1])
    struct.pack_into('>I', data, pics[1] + 4, 0)
    if pics[1] + 4 in rel: rel.remove(pics[1] + 4)
    # JObj 의 첫 DObj → 새 DObj
    ptr_field(jo + 0x10, do_off)
    rel.sort()
    nds = len(data)
    out = bytearray(blob[:base]) + data + struct.pack('>%dI' % len(rel), *rel) + tail
    struct.pack_into('>III', out, 0, len(out), nds, len(rel))
    return bytes(out), dict(verts=len(verts), tris=len(tris), dl_blocks=dl_n, size=(len(blob), len(out)))


def new_sign(blob, k):
    """원본 이름판 HSD(snr_obj k번 내용) → 한글 HSD."""
    tris, _ = place(glyph_triangles(SIGNS[k]))
    return replace_text(blob, tris)


def _pad(b, n=32):
    return b + b'\0' * (-len(b) % n)


def patch_container(entry, repl):
    """rpg_f·rpg_t 항목(u32 개수, (u32 번호, u32 위치)×개수, 32 정렬 하위 파일들)에서 하위 파일을 바꾸고 위치 목차를 다시 쓴다.
    repl = {원본 하위 파일 bytes(머리 크기만큼): 새 bytes}"""
    n = struct.unpack('>I', entry[:4])[0]
    tab = [struct.unpack('>II', entry[4 + 8 * i:12 + 8 * i]) for i in range(n)]
    offs = sorted(o for _, o in tab); first = offs[0]
    ends = offs[1:] + [len(entry)]
    head = bytearray(entry[:first]); body = bytearray(); newoff = {}
    for o, e in zip(offs, ends):
        sub = entry[o:e]
        size = struct.unpack('>I', sub[:4])[0] if sub[:4] != b'\0\0\0\x40' else struct.unpack('>I', sub[4:8])[0]
        key = bytes(sub[:size])
        newoff[o] = first + len(body)
        body += _pad(repl[key]) if key in repl else sub
    for i, (tid, o) in enumerate(tab):
        struct.pack_into('>II', head, 4 + 8 * i, tid, newoff[o])
    return bytes(head + body)


def patch_all(read):
    """read(디스크 경로) → bytes. 바뀐 파일 {디스크 경로: bytes} 와 기록."""
    log = {}
    so = sfd.unpack(read('/scenario_jp/snr_obj.BIN'))
    repl = {}
    for k in SIGNS:
        e = so[k]; size = struct.unpack('>I', e[:4])[0]
        new, info = new_sign(e[:size], k)
        repl[bytes(e[:size])] = new
        so[k] = _pad(new); log[k] = info
    out = {'/scenario_jp/snr_obj.BIN': sfd.pack(so)}
    for fn in ('/scenario_jp/rpg_f_models.BIN', '/scenario_jp/rpg_t_models.BIN'):
        ents = sfd.unpack(read(fn)); hit = 0
        for ei in (0, 1):
            before = ents[ei]
            ents[ei] = patch_container(before, repl)
            hit += sum(1 for b, k, o in sfd.blobs(before) if k == 'hsd' and bytes(b) in repl)
        assert hit == 13, (fn, '이름판 사본 수', hit)
        out[fn] = sfd.pack(ents)
    return out, log


def preview(outdir):
    from PIL import Image, ImageDraw
    os.makedirs(outdir, exist_ok=True)
    W, H, S = 640, 150, 116.7
    for k, ko in SIGNS.items():
        tris, cond = place(glyph_triangles(ko))
        im = Image.new('RGB', (W, H), (60, 30, 50)); d = ImageDraw.Draw(im)
        d.rectangle([W / 2 - 2.45 * S, H / 2 - 0.47 * S, W / 2 + 2.45 * S, H / 2 + 0.47 * S], outline=(160, 160, 160))
        for t in tris:
            d.polygon([(W / 2 + x * S, H / 2 - y * S) for x, y in t], fill=(240, 240, 240))
        im.save(os.path.join(outdir, 'sign%d.png' % k))
        print(k, ko, '삼각형', len(tris), '가로 줄임 %.2f' % cond)


if __name__ == '__main__':
    if sys.argv[1:2] == ['preview']:
        preview(os.path.join(disc.ROOT, 'work/graphics/workdata/sign3d-v01'))
