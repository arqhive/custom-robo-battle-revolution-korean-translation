"""main.dol 데이터 섹션의 시프트JIS 문자열 전수 추출 → work/translation/dol-jp.json

문자열 = NUL 앞에서 끝나는, 시프트JIS로 읽히는 바이트 줄(2바이트 글자나 반각 가나가 하나 이상).
칸 길이 = 문자열 + 뒤따르는 0 바이트(다음 0 아닌 바이트 전까지) — 제자리 덮어쓰기 때 쓸 수 있는 최대 길이.
같은 칸 안에 문자열이 겹치지 않게 앞에서부터 읽는다.
"""
import json, os, re, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

JP = re.compile(r'[぀-ヿ一-鿿＀-￯　-〿]')


def sections(d):
    h = d[:0x100]
    o = struct.unpack('>18I', h[:0x48]); a = struct.unpack('>18I', h[0x48:0x90]); s = struct.unpack('>18I', h[0x90:0xD8])
    return [('D%d' % (i - 7), o[i], a[i], s[i]) for i in range(7, 18) if s[i]]


def plausible(raw, t):
    """잡음(실수·코드 바이트가 우연히 SJIS로 읽힌 것) 거르기.
    - 2바이트 글자는 글꼴에 있는 JIS 1수준까지(0x9872 이하)만
    - 2바이트 글자 2개 이상, 또는 반각 가나만으로 된 4자 이상(세이브 제목 등)
    - 반각 가나와 2바이트 글자를 섞지 않음
    """
    two = []; half = 0; i = 0
    while i < len(raw):
        c = raw[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            two.append((c << 8) | raw[i + 1]); i += 2
        else:
            half += 0xA1 <= c <= 0xDF; i += 1
    if any(x > 0x9872 for x in two): return False
    if two and half: return False
    if half: return half >= 4 and re.fullmatch(r'[｡-ﾟ ]+', t) is not None
    return len(two) >= 2


def char_len(d, i):
    c = d[i]
    if 0x20 <= c < 0x7F or c in (0x0A, 0x09) or 0xA1 <= c <= 0xDF: return 1
    if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and 0x40 <= d[i + 1] <= 0xFC and d[i + 1] != 0x7F:
        try:
            d[i:i + 2].decode('cp932'); return 2
        except UnicodeDecodeError:
            return 0
    return 0


def scan(d, start, end):
    out = []; i = start
    while i < end:
        j = i; ok = True
        while j < end and d[j] != 0:
            n = char_len(d, j)
            if not n: ok = False; break
            j += n
        if ok and j < end and j > i:
            t = d[i:j].decode('cp932')
            if plausible(d[i:j], t):
                k = j
                while k < end and d[k] == 0: k += 1
                out.append((i, j - i, k - i, t))
            i = j + 1
        else:
            i = (j if j > i else i) + 1
    return out


def main():
    d = disc.read('sys/main.dol')
    res = []
    for name, off, addr, size in sections(d):
        for o, n, slot, t in scan(d, off, off + size):
            res.append({'id': 'dol:%06X' % o, 'sec': name, 'off': o, 'va': '%08X' % (addr + o - off),
                        'len': n, 'slot': slot, 'jp': t})
    json.dump(res, open(os.path.join(disc.ROOT, 'work/translation/dol-jp.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    by = {}
    for x in res: by.setdefault(x['sec'], []).append(x)
    for k, v in by.items():
        print(k, len(v), '글자', sum(len(x['jp']) for x in v), '고유', len({x['jp'] for x in v}))


if __name__ == '__main__':
    main()
