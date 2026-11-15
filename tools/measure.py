"""글줄 폭(px) 재기. 원문은 원본 글꼴, 한국어는 만든 글꼴(font_ko) 기준.

- 글자 전진 폭 = WID1 의 폭 칸(원본: 한자 22, 가나 19~23, ASCII 4~17, 반각 공백 1).
- `FF 00 01 hhhh` = 글자 크기 퍼센트(4B=75%, 96=150% …) — 그 뒤 글자에 곱한다. 문자열 처음은 100%.
- `FF 00 02 …` 후리가나는 폭 없음(원문에서만). `FE 00 08` 주인공 이름 = NAME_W, `%s`·`%d` = 자리 표시 폭.
- 그 밖의 제어 코드는 폭 없음.
같은 창에서는 기본 배율이 원문·번역에 똑같이 걸리므로, 「원문 최대 폭」과 비교하면 된다.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import bfn, disc, font_ko

TOK = re.compile(r'\{1A:([0-9A-F]*)\}|\{([0-9A-F]{2})\}|(%[0-9]*[sd])|(\n)|(.)', re.S)
NAME_LEN = 8         # 주인공 이름 최대 글자 수(이름 입력 최대 8글자, 11/14 사용자 실기에서 8글자 이름으로 넘침 확인 → 6에서 8로)
NAME_W = 22 * NAME_LEN   # 한글 8글자(가장 넓은 경우)
FMT_W = {'s': 22 * 6, 'd': 12 * 3}

_jp = _ko = None


def _adv_tables():
    global _jp, _ko
    if _jp is None:
        _, fs = bfn.load(disc.read('/message/font.out'))
        _jp = {}
        for f in fs:
            for c, g in f.cmap().items():
                _jp.setdefault(c, f.width(g)[1])
        _ko = dict(_jp)
        for h, c in font_ko.ko_map().items():
            _ko[h] = font_ko.SPACE_W if h == ' ' else font_ko.THIN_W if h == font_ko.THIN else font_ko.HAIR_W if h == font_ko.HAIR else 22
    return _jp, _ko


def _code(ch):
    if ord(ch) < 0x80: return ord(ch)
    try: return int.from_bytes(ch.encode('cp932'), 'big')
    except UnicodeEncodeError: return None


UI_SPACING = 3   # 메뉴·정보창(info.bin) 글자 사이 간격(px). 10/30 실기 스샷에서 잼: 한글 간격 25px, 영문 O 20·/ 13·F 16 → 글자 폭 + 3


def lines(text, korean=False, spacing=0):
    """문자열 → 줄마다 폭(px) 목록. spacing = 글자마다 더하는 간격(메뉴·정보창은 UI_SPACING)."""
    jp, ko = _adv_tables()
    scale = 1.0; w = 0.0; out = []; narrow = False
    for m in TOK.finditer(text):
        if m.group(5) in (font_ko.NARROW_OPEN, font_ko.NARROW_CLOSE):
            narrow = m.group(5) == font_ko.NARROW_OPEN; continue
        if narrow and korean and m.group(5) and '가' <= m.group(5) <= '힣':
            w += (font_ko.NARROW_W + spacing) * scale; continue
        code, raw, fmt, nl, ch = m.groups()
        if code is not None:
            if code.startswith('FF0001') and len(code) == 10: scale = int(code[6:], 16) / 100
            elif code == 'FE0008': w += (NAME_W + NAME_LEN * spacing) * scale
        elif fmt: w += (FMT_W[fmt[-1]] + (6 if fmt[-1] == 's' else 3) * spacing) * scale
        elif nl: out.append(w); w = 0.0
        elif ch:
            if korean and ch in ko: a = ko[ch]
            else:
                c = _code(ch); a = jp.get(c, 22) if c is not None else 22
            w += (a + spacing) * scale
    out.append(w)
    return out


def width(text, korean=False):
    return max(lines(text, korean))
