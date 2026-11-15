"""한글 글꼴 만들기: font.out 의 1수준 한자 칸에 한글 2,350자를 덮어쓴다.

- 대응표: KS X 1001 한글 2,350자(가나다 순) → SJIS 1수준 한자 코드(0x889F부터 차례로).
  work/font/ko_map.json  {"가": "889F", ...}
- 한자 코드 0x8F40~0x8F9A 는 1번·2번 글꼴에 둘 다 있으므로 두 곳 모두 그린다.
- 글자 칸 24×24, 잉크는 원본 한자처럼 가로 1~23·세로 0~22 안.
  고정 폭은 폰트 자리 그대로(render_place: 공통 기준선, 폰트 전진 폭 상자를 칸 가운데에), --prop 은 옛 방식(render: 잉크 가운데).
- 폭 표(WID1): 고정(한자와 같은 (1, 22)) 또는 --prop 이면 글자마다 (잉크 왼쪽-1, 잉크 폭+2).
- 띄어쓰기: 원본 0x20 은 폭 1px, 0x8140 은 표에 없음 → 2,351번째 한자 코드를 빈 글자(폭 SPACE_W)로 만든다.
- 호환 자모 51자(ㄱ~ㅣ, U+3131~U+3163): 띄어쓰기 다음 0x9541~0x9573(이름 입력판 한글 자모, docs/name-input.md).
  앞의 2,350자·띄어쓰기 코드는 그대로다. 자모는 완성형 글자와 같은 높이 느낌이 나게 키워 그린다(render_jamo).
- 원본은 읽기만 하고 결과는 build/files/message/font.out 에 쓴다.

    python tools/font_ko.py [글꼴 파일] [크기px] [--weight N] [--preview 문장]
"""
import argparse, json, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import bfn, disc

KANJI_START = 0x889F
# 사용자 결정 10/30: 그림 글씨(G마켓 산스 Medium)와 맞춰 G마켓 산스 Medium, 고정 폭. 23px 이 맑은 고딕 Bold 22px 와 글자 크기가 같다.
# (10/23 맑은 고딕 Bold → 10/30 변경)
FONT = 'tools/fonts/GmarketSansMedium.otf'
SIZE = 23


def hangul():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            out.append(bytes([hi, lo]).decode('euc-kr'))
    assert len(out) == 2350
    return out


def kanji_codes():
    """SJIS 1수준 한자 코드(0x889F~0x9872) 차례대로. 둘째 바이트 0x7F 제외."""
    out = []
    for hi in range(0x88, 0x99):
        for lo in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            c = hi << 8 | lo
            if KANJI_START <= c <= 0x9872: out.append(c)
    return out


SPACE_W = 8
# 얇은 빈칸: 번역문에 U+2009 로 쓴다. 폭 THIN_W px 빈 글자(게임은 여기에 글자 사이 간격을 더함).
# 띄어쓰기(8px)·원본 0x20(실기에서 띄어쓰기만큼 넓음)보다 잘게 위치를 맞출 때(예: 선택 칸 가운데 맞춤).
THIN, THIN_W = ' ', 1
# 아주 얇은 빈칸(U+200A → 0x9575, 폭 0). 11/13 v0.8 실기 역산: 얇은 빈칸 약 5.5px·띄어쓰기 약 11.7px·전각 빈칸 약 8.5px(간격 포함).
HAIR, HAIR_W = ' ', 0
JAMO =[chr(0x3131 + k) for k in range(51)]     # 호환 자모 ㄱ … ㅣ


NARROW_OPEN, NARROW_CLOSE = '⟪', '⟫'
NARROW_W = 15          # 좁은 글자 전진 폭(보통 한글 22 의 약 70%)
NARROW_CHARS = '카타스트로피포드그라운프리즈랜크봄메테오플커건사이웨새틀'


def narrow_map():
    """11/14: 좁은 한글(가로 70%) — 파츠 이름 창에서 넘치는 이름만 번역문에 ⟪…⟫ 로 감싸 쓴다.
    아주 얇은 빈칸(0x9575) 다음 빈 한자 칸부터 차례로. ko_map 의 코드는 그대로다."""
    ks = kanji_codes(); base = 2353 + len(JAMO)
    assert ks[base - 1] == 0x9575
    assert len(set(NARROW_CHARS)) == len(NARROW_CHARS)
    return {h: ks[base + i] for i, h in enumerate(NARROW_CHARS)}


def render_narrow(ch, font, top, bot):
    """보통 글자(render_place)를 가로만 NARROW_W/22 로 줄여 칸 왼쪽(x=1)부터."""
    im = render_place(ch, font, top, bot)
    g = im.crop((1, 0, 23, 24)).resize((NARROW_W, 24), Image.LANCZOS)
    out = Image.new('L', (24, 24)); out.paste(g, (1, 0))
    return out


def ko_map():
    """한글 2,350자 + 띄어쓰기(' ') + 호환 자모 51자 → 한자 코드."""
    ks = kanji_codes(); m = dict(zip(hangul(), ks))
    m[' '] = ks[2350]
    for k, j in enumerate(JAMO): m[j] = ks[2351 + k]
    assert m['ㄱ'] == 0x9541 and m['ㅣ'] == 0x9573
    m[THIN] = ks[2351 + len(JAMO)]                  # 얇은 빈칸(11/13): 자모 다음 칸 0x9574
    m[HAIR] = ks[2352 + len(JAMO)]                  # 아주 얇은 빈칸(11/13): 0x9575
    return m


def make_font(path, size, weight=None):
    f = ImageFont.truetype(path, size)
    if weight is not None:
        try: f.set_variation_by_axes([weight])
        except Exception: pass
    return f


def render(ch, font, cw=24, ch_h=24, box=(1, 0, 23, 22)):
    """글자를 잉크 상자(box) 가운데에 그린다. 넘치면 줄여서 다시."""
    big = Image.new('L', (cw * 3, ch_h * 3)); d = ImageDraw.Draw(big)
    d.text((cw, ch_h), ch, fill=255, font=font)
    bb = big.getbbox()
    g = big.crop(bb)
    bw, bh = box[2] - box[0], box[3] - box[1]
    if g.width > bw or g.height > bh:
        r = min(bw / g.width, bh / g.height)
        g = g.resize((max(1, round(g.width * r)), max(1, round(g.height * r))), Image.LANCZOS)
    im = Image.new('L', (cw, ch_h))
    im.paste(g, (box[0] + (bw - g.width) // 2, box[1] + (bh - g.height) // 2))
    return im


def place_box(font, chars):
    """폰트 자리 그대로 넣을 때의 공통 윗선·아랫선(80×80 판, 글자 원점 (30, 20) 기준)과, 칸(22×22)에 다 들어가는지."""
    top, bot, lmin, rmax = 999, 0, 999, -999
    for ch in chars:
        im = Image.new('L', (80, 80)); ImageDraw.Draw(im).text((30, 20), ch, fill=255, font=font)
        bb = im.getbbox()
        if not bb: continue
        off = (22 - font.getlength(ch)) / 2
        top = min(top, bb[1]); bot = max(bot, bb[3])
        lmin = min(lmin, bb[0] - 30 + off); rmax = max(rmax, bb[2] - 30 + off)
    return top, bot, (bot - top <= 22 and lmin >= 0 and rmax <= 22)


def render_place(ch, font, top, bot, cw=24, ch_h=24, box=(1, 0, 23, 22)):
    """11/13: 글자를 폰트가 정한 자리 그대로 칸에 넣는다(render 는 잉크를 칸 가운데로 옮기고 넘치는 글자만 따로 줄여 들쑥날쑥했음).
    세로 = 폰트 공통 기준선, 가로 = 폰트 전진 폭 상자를 22px 칸 가운데에 두고 잉크는 폰트 자리 그대로."""
    im = Image.new('L', (80, 80)); ImageDraw.Draw(im).text((30, 20), ch, fill=255, font=font)
    out = Image.new('L', (cw, ch_h))
    off = round((22 - font.getlength(ch)) / 2)
    out.paste(im.crop((30, top, 30 + 23, bot)), (box[0] + off, box[1] + (22 - (bot - top)) // 2))
    return out


def render_jamo(ch, font, scale):
    """자모 낱자. 맑은 고딕의 호환 자모 중 모음은 이미 완성형 높이라 render() 그대로,
    자음은 완성형의 반쯤이라 모든 자음을 같은 배율(scale)로 키운다(넘치면 칸에 맞게 줄임)."""
    if ch >= 'ㅏ':
        return render(ch, font)
    big = Image.new('L', (96, 96)); ImageDraw.Draw(big).text((24, 24), ch, fill=255, font=font)
    g = big.crop(big.getbbox())
    r = min(scale, 21 / g.width, 21 / g.height)
    g = g.resize((max(1, round(g.width * r)), max(1, round(g.height * r))), Image.LANCZOS)
    im = Image.new('L', (24, 24))
    im.paste(g, (1 + (22 - g.width) // 2, (22 - g.height) // 2))
    return im


JAMO_H = 0.78     # 자음 낱자 잉크 높이 = 완성형(「한」) 높이 × JAMO_H


def build(font_path, size, weight=None, prop=False):
    buf, fonts = bfn.load(disc.read('/message/font.out'))
    font = make_font(font_path, size, weight)
    m = ko_map(); drawn = 0
    cms = [f.cmap() for f in fonts]
    ref = render('한', font).getbbox(); g = render('ㄱ', font).getbbox()
    jamo_scale = (ref[3] - ref[1]) * JAMO_H / (g[3] - g[1])
    top, bot, fits = place_box(font, [h for h in m if h not in (' ', THIN, HAIR) and h not in JAMO])
    assert prop or fits, '폰트 자리 그대로는 칸(22×22)을 넘는 글자가 있음 — 크기를 줄일 것'
    for h, code in m.items():
        if h == ' ':
            im = Image.new('L', (24, 24)); lw = (0, SPACE_W)
        elif h == THIN:
            im = Image.new('L', (24, 24)); lw = (0, THIN_W)
        elif h == HAIR:
            im = Image.new('L', (24, 24)); lw = (0, HAIR_W)
        elif h in JAMO:
            im = render_jamo(h, font, jamo_scale); bb = im.getbbox()
            lw = (bb[0] - 1, bb[2] - bb[0] + 2) if prop else (1, 22)
        elif prop:
            im = render(h, font); bb = im.getbbox()
            lw = (bb[0] - 1, bb[2] - bb[0] + 2)
        else:
            im = render_place(h, font, top, bot); lw = (1, 22)
        hit = False
        for f, cm in zip(fonts[1:], cms[1:]):
            if code in cm:
                f.put(cm[code], im); f.set_width(cm[code], *lw); hit = True
        assert hit, hex(code)
        drawn += 1
    if not prop:
        for h, code in narrow_map().items():
            im = render_narrow(h, font, top, bot); hit = False
            for f, cm in zip(fonts[1:], cms[1:]):
                if code in cm:
                    f.put(cm[code], im); f.set_width(cm[code], 1, NARROW_W); hit = True
            assert hit, hex(code)
    return buf, fonts, m, drawn


def preview(fonts, m, text, scale=2):
    """만든 글꼴로 문장을 그려 본다(원본 글꼴 0번의 가나·부호는 그대로)."""
    cms = [f.cmap() for f in fonts]
    x = 0; cells = []
    for ch in text:
        if ch in m: code = m[ch]
        elif ord(ch) < 0x80: code = ord(ch)
        else: code = int.from_bytes(ch.encode('cp932'), 'big')
        for f, cm in zip(fonts, cms):
            if code in cm:
                g = cm[code]; l, w = f.width(g); cells.append((x - l, f.get(g))); x += w; break
        else:
            x += 12
    im = Image.new('L', (x + 4, 26), 0)
    for px, g in cells: im.paste(g, (px + 2, 1), g)
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def main():
    ap = argparse.ArgumentParser()
    # 글꼴 파일은 git 에 넣지 않는다(.gitignore).
    ap.add_argument('font', nargs='?', default=os.path.join(disc.ROOT, FONT))
    ap.add_argument('size', nargs='?', type=int, default=SIZE)
    ap.add_argument('--weight', type=int)
    ap.add_argument('--prop', action='store_true')
    ap.add_argument('--out', default=os.path.join(disc.ROOT, 'build/files/message/font.out'))
    a = ap.parse_args()
    buf, fonts, m, n = build(a.font, a.size, a.weight, a.prop)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'wb').write(buf)
    os.makedirs(os.path.join(disc.ROOT, 'work/font'), exist_ok=True)
    json.dump({h: '%04X' % c for h, c in m.items()}, open(os.path.join(disc.ROOT, 'work/font/ko_map.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print('한글', n, '자 →', a.out, len(buf))


if __name__ == '__main__':
    main()
