"""3단계 창 한계표 만들기·한국어 넘침 검사.

한계 = 같은 창(묶음)에서 원문 일본어 줄의 최대 폭(px, measure.py)·최대 줄 수.
모드 선택 설명칸으로 맞춰 봄(10/23 실기 사진): 원문 최대 218px = 패널 오른쪽 끝, 번역 226·250px 줄은 넘침.

묶음(id 앞부분으로 정함)
- dlg       : 시나리오 대사 `snr_*.bmg` — 줄 370px, 3줄(넘치면 {1A:FE000301} 로 쪽 나누기 — 실기 확인 전)
- snt       : `SNT_TEST.bmg` 상점·용어 — 원문에 700px 넘는 긴 줄이 있어 자동 줄넘김 창으로 추정, 폭 검사 안 함(화면 확인 전)
- info:BB:1 / info:BB:N : info.bin 블록 BB 의 한 줄 항목 / 여러 줄 항목
항목마다 한계는 max(묶음 한계, 그 항목 원문 폭) — 원문 자기 폭은 이미 화면에 들어간다.

    python tools/windows.py build            # manifests/window-limits.json
    python tools/windows.py check 번역.json   # {id: 한국어} → 넘침 목록
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import bmg, disc, measure

RUBY = re.compile(r'\{1A:FF0002[0-9A-F]*\}')
PAGE = re.compile(r'\{1A:FE0003[0-9A-F]{2}\}')
LIMITS = os.path.join(disc.ROOT, 'manifests/window-limits.json')


def originals():
    """id → 원문(후리가나 뺀 것)."""
    out = {}
    for x in json.load(open(os.path.join(disc.ROOT, 'work/translation/bmg-jp.json'), encoding='utf-8')):
        out['%s:%d' % (x['file'][:-4], x['id'])] = x['jp']
    for x in json.load(open(os.path.join(disc.ROOT, 'work/translation/info-jp.json'), encoding='utf-8')):
        out[x['id']] = x['jp']
    snt = bmg.read(disc.read('/scenario/sentence/SNT_TEST.bmg'))
    for k, e in enumerate(snt['inf']['entries']):
        out['SNT_TEST:%d' % k] = e.get('text', '')
    return {k: RUBY.sub('', v) for k, v in out.items()}


def group(i, jp):
    if i.startswith('snr_'): return 'dlg'
    if i.startswith('SNT_TEST'): return 'snt'
    b = i.split(':')[1]
    return 'info:%s:%s' % (b, 'N' if '\n' in jp.strip('\n') else '1')


def pages(t):
    return [p for p in PAGE.split(t)]


def build():
    org = originals(); g = {}
    for i, t in org.items():
        if not t.strip(): continue
        k = group(i, t); w = g.setdefault(k, {'px': 0, 'lines': 0, 'n': 0})
        for p in pages(t):
            ls = measure.lines(p)
            w['px'] = max(w['px'], round(max(ls))); w['lines'] = max(w['lines'], len(ls) - (p.endswith('\n')))
        w['n'] += 1
    g['dlg']['px'] = 370; g['dlg']['lines'] = 3   # 4줄 1개(75% 크기 웃음소리)는 예외로 본다
    json.dump(g, open(LIMITS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    return g


def check(ko):
    org = originals(); lim = json.load(open(LIMITS, encoding='utf-8')); bad = []
    for i, t in ko.items():
        jp = org[i]; k = group(i, jp)
        if k == 'snt': continue
        L = lim[k]; own = max(measure.lines(p) for p in pages(jp)) if jp.strip() else [0]
        px = max(L['px'], round(max(own)))
        for n, p in enumerate(pages(t)):
            ls = measure.lines(p, korean=True)
            nl = len(ls) - (p.endswith('\n'))
            if max(ls) > px: bad.append((i, '폭 %d > %d' % (max(ls), px), p))
            if nl > max(L['lines'], 1): bad.append((i, '줄 %d > %d' % (nl, L['lines']), p))
    return bad


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        g = build(); print(len(g), '묶음')
    else:
        for b in check(json.load(open(sys.argv[2], encoding='utf-8'))): print(*b)
