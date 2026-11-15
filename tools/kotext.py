"""한국어 문장 → 게임 문자열(bmg.py 텍스트 표기)로 바꾸기.

- 한글·띄어쓰기는 font_ko.ko_map() 의 한자 코드 글자로 바꾼다(SJIS 로 인코딩하면 그 코드가 됨).
- 제어 코드 태그 {1A:..}·{XX}, 줄바꿈 \\n, ASCII 부호·숫자·영문, 원본 글꼴에 있는 전각 부호(…！？「」 등)는 그대로.
- 그 밖의 글자(글꼴에 없는 것)는 오류.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import font_ko

_TAG = re.compile(r'(\{1A:[0-9A-Fa-f]*\}|\{[0-9A-Fa-f]{2}\})')
_M = None
# 한자 칸(0x889F~)보다 앞 코드로 원본 글꼴에 있는 문자(가나·전각 부호·기호)는 한글과 섞어 쓸 수 있다.
_KEEP = None


def _keep():
    global _KEEP
    if _KEEP is None:
        import bfn, disc
        _, fs = bfn.load(disc.read('/message/font.out'))
        codes = set()
        for f in fs: codes |= {c for c in f.cmap() if 0x8140 <= c < font_ko.KANJI_START}
        _KEEP = {bytes([c >> 8, c & 0xFF]).decode('cp932', 'ignore') for c in codes} - {''}
    return _KEEP


def _map():
    global _M
    if _M is None:
        _M = {h: bytes([c >> 8, c & 0xFF]).decode('cp932') for h, c in font_ko.ko_map().items()}
    return _M


_N = None


def _nmap():
    global _N
    if _N is None:
        _N = {h: bytes([c >> 8, c & 0xFF]).decode('cp932') for h, c in font_ko.narrow_map().items()}
    return _N


def to_game(ko):
    m = _map(); out = []; narrow = False
    for part in _TAG.split(ko):
        if _TAG.fullmatch(part):
            out.append(part); continue
        for ch in part:
            # ⟪…⟫ 안의 한글은 좁은 글자(font_ko.narrow_map), 괄호는 지운다
            if ch == font_ko.NARROW_OPEN: narrow = True
            elif ch == font_ko.NARROW_CLOSE: narrow = False
            elif narrow and '가' <= ch <= '힣':
                if ch not in _nmap(): raise ValueError('좁은 글자 없음(font_ko.NARROW_CHARS 에 추가): %r (%s)' % (ch, ko))
                out.append(_nmap()[ch])
            elif ch in m: out.append(m[ch])
            # 전각 공백(0x8140)은 글꼴 표에 없지만 원문 메뉴가 칸 맞춤에 쓴다(엔진이 처리)
            elif ch in '\n　' or 0x21 <= ord(ch) < 0x7F or ch in _keep(): out.append(ch)
            else: raise ValueError('글꼴에 없는 글자: %r (%s)' % (ch, ko))
    return ''.join(out)


def from_game(s):
    """게임 문자열 → 한국어(검수용 되돌리기)."""
    r = {v: k for k, v in _map().items()}
    r.update({v: k for k, v in _nmap().items()})
    return ''.join(r.get(ch, ch) for ch in s)


if __name__ == '__main__':
    t = to_game(sys.argv[1]); print(t); print(from_game(t))
