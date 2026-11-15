"""번역 결과 기계 검사: python -X utf8 tools/check_batch.py [묶음이름...]  (없으면 전체)

문제(고쳐야 함)
- dup_of 없는 id 번역 빠짐 / 묶음에 없는 id
- 제어 코드 {1A:…}·%s·%d 가 글자·개수·순서까지 같은지
- 일본 가나·한자 남음, 게임 글꼴로 바꿀 수 없는 글자(kotext.to_game 실패 = KS X 1001 밖)
- {1A:FE0008}(주인공 이름) 바로 뒤 받침 따라 바뀌는 조사
- 말줄임표·물결표 뒤 마침표
- 선택지 메시지 줄 수가 원문과 다름
경고(확인)
- 용어집 이름: 원문에 용어집 원문(3자 이상 고유명사)이 있는데 번역에 그 한국어가 없음
- info 한 줄 항목(info-1·name)이 창 한계 폭(windows.py)을 넘음
- info 여러 줄 설명(info-N)이 묶음 한계 폭·줄 수를 넘음
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc, kotext, measure

B = os.path.join(disc.ROOT, 'work/translation/batches')
O = os.path.join(disc.ROOT, 'work/translation/out')
# --redo: 대사 다시 번역(11/13) 결과 redo/ 를 검사, dup_of 항목도 번역해야 함
REDO = '--redo' in sys.argv
if REDO:
    sys.argv.remove('--redo'); O = os.path.join(disc.ROOT, 'work/translation/redo')
CODE = re.compile(r'\{1A:[0-9A-Fa-f]*\}|\{[0-9A-Fa-f]{2}\}|%[0-9]*[sd]')
JP = re.compile(r'[ぁ-んァ-ヶ一-龥]')
BAD_PARTICLE = re.compile(r'\{1A:FE0008\}(은|는|이|가|을|를|와|과|이랑|랑|이야|야|으로|로|이에요|예요|이다|다|냐|니|라고|라는|란|라면|여|이여|라도|이라도|나|이나|든|이든)(?![가-힣])')
gloss = json.load(open(os.path.join(disc.ROOT, 'work/glossary/glossary-ko.json'), encoding='utf-8'))
NAMES = sorted(((k, v['ko']) for k, v in gloss.items()
                if len(k) >= 3 and not JP.sub('', k) == k and v.get('cat') in ('인물', '지명', '단체', '대회', '로보', '스테이지', '용어')
                or (len(k) == 2 and JP.fullmatch(k[0]) and JP.fullmatch(k[1]) and v.get('cat') in ('지명', '단체'))
                or (len(k) >= 3 and re.fullmatch(r'[ァ-ヶー・]+', k) and v.get('cat', '').startswith(('파츠', '로보')))),
               key=lambda x: -len(x[0]))
# 일부러 원문 그대로 두는 항목(번역하면 게임 동작이 바뀜)
# dol:239010 レッグ = 파츠 종류 이름표(ガン·ボム·ポッド 와 한 표, 셋은 개발용 제외). 「레그」로 바꾸면 커스텀 화면 다리 이름이
# 「스탠더드 레그」→「스탠더드」로 잘려 보였다(11/14 v0.16 실기). 게임이 이름 끝 종류 말을 떼는 것으로 추정 — 원문 그대로.
KEEP_JP = {'dol:239010'}
LIM = os.path.join(disc.ROOT, 'manifests/window-limits.json')
LIMITS = json.load(open(LIM, encoding='utf-8')) if os.path.exists(LIM) else {}


SCALE_RE = re.compile(r'\{1A:FF0001([0-9A-F]{4})\}')


def screen_problems(ko):
    """빌드가 실제로 넣을 모양(build.fit_message 결과)으로 화면 넘침을 찾는다 — 검사만, 빌드 결과는 안 바꿈(11/14).
    - 쪽 나눔(D, FE000301 넣음): 실기에서 창을 비우지 않고 이어서 넘침(11/14 스샷 2장).
    - 큰 글씨(FF0001 > 100%) 든 쪽이 3줄 이상: 원문 410쪽은 전부 1~2줄, 실기에서 3번째 줄이 창 아래로 넘침(11/14 스샷 2장).
    - 250%(FF0001 FA) 든 쪽이 2줄 이상: 원문 6쪽 전부 1줄, 실기에서 2번째 줄이 창 아래로 넘침(11/15)."""
    import build
    out, how = build.fit_message(ko)
    msgs = []
    if 'D' in how: msgs.append('쪽 나눔(실기에서 넘침) — 3줄 안으로 줄일 것')
    sc = 100
    for p in build.PAGE.split(out):
        if build.PAGE.fullmatch(p) or not p.strip('\n'): continue
        ls = p.rstrip('\n').split('\n'); big = False; top = 100
        for l in ls:
            mx = sc
            for m in SCALE_RE.findall(l): mx = max(mx, int(m, 16)); sc = int(m, 16)
            big |= mx > 100; top = max(top, mx)
        if top > 200 and len(ls) >= 2:   # 250%(FA): 원문 6쪽 전부 1줄, 2줄이면 창 아래로 넘침(11/15 실기 snr_t_16:72)
            msgs.append('250%% 글씨 쪽 %d줄(1줄까지): %s' % (len(ls), TAG_RE.sub('', p).replace('\n', ' / ')[:60]))
        elif big and len(ls) >= 3:
            msgs.append('큰 글씨 쪽 %d줄(2줄까지): %s' % (len(ls), TAG_RE.sub('', p).replace('\n', ' / ')[:60]))
    return msgs


TAG_RE = re.compile(r'\{[^}]*\}')


def check(name):
    items = json.load(open(os.path.join(B, name + '.json'), encoding='utf-8'))
    path = os.path.join(O, name + '.json')
    if not os.path.exists(path): return ['결과 파일 없음'], len(items)
    tr = json.load(open(path, encoding='utf-8')).get('translations', {})
    probs = []
    ids = {it['id'] for it in items}
    for k in tr:
        if k not in ids: probs.append(f'{k} 묶음에 없는 id')
    for it in items:
        k = it['id']; jp = it['jp']; ko = tr.get(k)
        if 'dup_of' in it and not REDO: continue
        if ko is None: probs.append(f'{k} 번역 없음'); continue
        if CODE.findall(jp) != CODE.findall(ko): probs.append(f'{k} 코드 다름 {CODE.findall(jp)} → {CODE.findall(ko)}')
        if JP.search(ko) and not (k in KEEP_JP and ko == jp): probs.append(f'{k} 일본 글자 남음: {ko[:40]}')
        try: kotext.to_game(ko)
        except ValueError as e: probs.append(f'{k} {e}')
        if BAD_PARTICLE.search(ko): probs.append(f'{k} 주인공 이름 뒤 조사: {ko[:60]}')
        if re.search(r'[…~〜～]\.', ko): probs.append(f'{k} 말줄임표·물결표 뒤 마침표')
        if 'FE0007' in jp and jp.count('\n') != ko.count('\n'): probs.append(f'{k} 선택지 줄 수 {jp.count(chr(10))}→{ko.count(chr(10))}')
        if it['kind'] == 'line':
            for msg in screen_problems(ko): probs.append(f'{k} {msg}')
        for jn, kn in NAMES:
            if jn in jp and kn not in ko:
                probs.append(f'{k} (경고) 용어 {jn}={kn} 없음: {ko[:50]}'); break
        if it['kind'] in ('info-1', 'name') and LIMITS:
            g = 'info:%s:1' % k.split(':')[1]
            lim = max(LIMITS.get(g, {}).get('px', 0), max(measure.lines(jp)))
            w = max(measure.lines(ko, korean=True))
            if w > lim: probs.append(f'{k} (경고) 칸 폭 {w:.0f}>{lim:.0f}px: {ko}')
        if it['kind'] == 'info-N' and LIMITS:
            L = LIMITS.get('info:%s:N' % k.split(':')[1], {})
            ls = measure.lines(ko, korean=True)
            lim = max(L.get('px', 0), max(measure.lines(jp)))
            nl = len(ls) - ko.endswith('\n')
            if max(ls) > lim: probs.append(f'{k} (경고) 설명 폭 {max(ls):.0f}>{lim:.0f}px')
            if nl > max(L.get('lines', 0), jp.count('\n') + 1): probs.append(f'{k} (경고) 설명 줄 수 {nl}>{L.get("lines")}')
    return probs, len(items)


def main():
    names = sys.argv[1:] or sorted(f[:-5] for f in os.listdir(B) if f.endswith('.json'))  # 대괄호 경로라 glob 금지
    assert names, '묶음 0개'
    tot = 0
    for n in names:
        p, cnt = check(n)
        hard = [x for x in p if '(경고)' not in x]
        print(f'== {n}: {cnt}개, 문제 {len(hard)}, 경고 {len(p) - len(hard)}')
        for x in p[:40]: print('  ', x)
        tot += len(hard)
    print('전체 문제', tot)


if __name__ == '__main__':
    main()
