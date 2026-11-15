"""4단계 전수 추출 → work/translation/batches/*.json (번역용) + manifests/extract-summary.json

항목: {id, src, kind, speaker, jp, en, dup_of?}
- jp: 후리가나(FF0002) 뺀 원문. 다른 제어 코드는 그대로({1A:..}). 빌드는 id 로 원본을 다시 읽어 바꾼다.
- en: 디스크 안 북미판 짝(scenario_us, info_usa.bin). 없으면 "".
- speaker: 대사 첫 화자 얼굴 코드(FE0006 XX) → work/translation/speakers.json 이름. 코드 없는 메시지는 바로 앞 번호 메시지의 마지막 화자 + '(이어짐)', 앞 번호가 비었으면 '(미상)'.
- dup_of: 같은 묶음 안에서 jp 가 똑같은 앞 항목(번역은 앞 항목을 따른다).
kind
- line·choice : 시나리오 대사(snr_*.bmg) / 선택지(FE0007) 포함
- tip         : SNT_TEST.bmg 상점·용어 설명
- info-1·info-N : info.bin 한 줄(이름·메뉴)·여러 줄(설명). 15블록은 name(화자·대회 이름)
- dol-name    : main.dol 파츠 레코드의 일본어 이름(info 와 같은 말로 맞춘다)
- (세이브 제목·디스크 배너는 사용자 결정 10/23 으로 일본어 그대로 — 추출 안 함)
제외(목록에만 남김)
- dev         : 북미판에서도 일본어 그대로인 시나리오 파일(snr_f_25~30·snr_t_20 복사본, snr_f_28 얼굴 시험 목록)
- debug       : main.dol 디버그 메뉴·내부 이름(모델·이펙트 이름 등, 바로 뒤에 영어 이름 칸이 없는 것)
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import bmg, disc, info_bin

RUBY = re.compile(r'\{1A:FF0002[0-9A-F]*\}')
T = os.path.join(disc.ROOT, 'work/translation')
DEV_FILES = {'snr_f_25', 'snr_f_26', 'snr_f_27', 'snr_f_28', 'snr_f_29', 'snr_f_30', 'snr_t_20'}
BATCH_CHARS = 9000   # 묶음 하나 원문 글자 수 목표


def plain(t):
    return RUBY.sub('', t)


def speaker(t, names, prev=''):
    """첫 화자 이름. 코드가 없으면 앞 메시지의 마지막 화자를 이어받아 '…(이어짐)' 으로."""
    codes = re.findall(r'\{1A:FE0006(..)..\}', t)
    nm = lambda c: names.get(c, {}).get('name', c)
    if not codes: return (prev + '(이어짐)') if prev else '', prev
    return nm(codes[0]), nm(codes[-1])


def main():
    sp = os.path.join(T, 'speakers.json')
    names = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
    items, excluded = [], []
    # 시나리오 대사
    for p in disc.paths('/scenario_jp/'):
        if not p.endswith('.bmg'): continue
        f = os.path.basename(p)[:-4]
        jp = bmg.read(disc.read(p))['inf']['entries']
        us = bmg.read(disc.read(p.replace('scenario_jp', 'scenario_us')))['inf']['entries']
        last = ''; prev_k = -2
        for k, e in enumerate(jp):
            t = e.get('text', '')
            if not plain(t).strip(): continue
            # 바로 앞 번호가 대사일 때만 앞 화자를 이어받는다(번호가 끊긴 자리 = 선택지 분기·회상 등은 미상)
            spk, last = speaker(t, names, last if prev_k == k - 1 else '')
            if not spk: spk = '(미상)'
            prev_k = k
            x = {'id': '%s:%d' % (f, k), 'src': p, 'kind': 'choice' if 'FE0007' in t else 'line',
                 'speaker': spk, 'jp': plain(t), 'en': us[k].get('text', '') if k < len(us) else ''}
            (excluded if f in DEV_FILES else items).append(dict(x, kind='dev') if f in DEV_FILES else x)
    # 상점·용어
    for k, e in enumerate(bmg.read(disc.read('/scenario/sentence/SNT_TEST.bmg'))['inf']['entries']):
        t = e.get('text', '')
        if plain(t).strip():
            items.append({'id': 'SNT_TEST:%d' % k, 'src': '/scenario/sentence/SNT_TEST.bmg', 'kind': 'tip', 'speaker': '', 'jp': plain(t), 'en': ''})
    # info.bin
    for x in json.load(open(os.path.join(T, 'info-jp.json'), encoding='utf-8')):
        t = plain(x['jp'])
        if not t.strip(): continue
        kind = 'name' if x['block'] == 15 else ('info-N' if '\n' in t.strip('\n') else 'info-1')
        items.append({'id': x['id'], 'src': '/bmg/info.bin', 'kind': kind, 'speaker': '', 'jp': t, 'en': x['en'] or ''})
    # main.dol: 파츠 레코드(일본어 이름 0x20 → 영어 이름 0x20 → 모델 이름)의 일본어 이름만 화면용 후보
    dol = disc.read('sys/main.dol')
    def en_after(o):
        e = dol[o + 0x20:o + 0x40].split(b'\0')[0]
        return e.decode('ascii') if o % 4 == 0 and len(e) >= 2 and all(0x20 <= c < 0x7F for c in e) else ''
    for x in json.load(open(os.path.join(T, 'dol-jp.json'), encoding='utf-8')):
        en = en_after(x['off'])
        dbg = not (x['sec'] == 'D3' and x['slot'] >= 0x20 and en)
        y = {'id': x['id'], 'src': 'sys/main.dol', 'kind': 'debug' if dbg else 'dol-name', 'speaker': '', 'jp': x['jp'], 'en': en}
        (excluded if dbg else items).append(y)
    # 같은 원문 묶기
    first = {}
    for x in items:
        key = (x['kind'] in ('line', 'choice'), x['jp'])
        if key in first: x['dup_of'] = first[key]
        else: first[key] = x['id']
    # 묶음 나누기: 대사는 파일 순서대로 글자 수로 끊고, 나머지는 종류별
    out = os.path.join(T, 'batches'); os.makedirs(out, exist_ok=True)
    for n in os.listdir(out):
        os.remove(os.path.join(out, n))
    groups = {}
    def add(prefix, x):
        lst = groups.setdefault(prefix, [[]])
        if sum(len(y['jp']) for y in lst[-1] if 'dup_of' not in y) > BATCH_CHARS: lst.append([])
        lst[-1].append(x)
    order = lambda x: (x['id'].split(':')[0].replace('snr_t', 'snr_a'), int(x['id'].split(':')[1], 16) if x['src'] == 'sys/main.dol' else int(x['id'].split(':')[-1]) if x['id'].split(':')[-1].isdigit() else 0)
    for x in sorted(items, key=lambda x: x['id']):
        pre = {'line': 'dlg', 'choice': 'dlg', 'tip': 'tip', 'name': 'name', 'info-1': 'ui', 'info-N': 'ui', 'dol-name': 'dol', 'system': 'sys'}[x['kind']]
        add(pre, x)
    # 대사는 이야기 순서(旅立ち編 t → 激闘編 f)로
    dl = [x for x in items if x['kind'] in ('line', 'choice')]
    dl.sort(key=lambda x: (0 if x['id'].startswith('snr_t') else 1, x['id'].split(':')[0], int(x['id'].split(':')[1])))
    groups['dlg'] = [[]]
    for x in dl: add('dlg', x)
    summary = {}
    for pre, lst in groups.items():
        for i, b in enumerate(lst):
            name = '%s-%02d.json' % (pre, i)
            json.dump(b, open(os.path.join(out, name), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            summary[name] = {'items': len(b), 'unique': sum('dup_of' not in y for y in b), 'chars': sum(len(re.sub(r'\{[^}]*\}', '', y['jp'])) for y in b if 'dup_of' not in y)}
    json.dump(excluded, open(os.path.join(T, 'excluded.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(summary, open(os.path.join(disc.ROOT, 'manifests/extract-summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tot = {}
    for k, v in summary.items():
        t = tot.setdefault(k.split('-')[0], [0, 0, 0, 0]); t[0] += 1; t[1] += v['items']; t[2] += v['unique']; t[3] += v['chars']
    for k, v in tot.items(): print('%-5s 묶음 %2d  항목 %5d  고유 %5d  글자 %7d' % (k, *v))
    print('제외', len(excluded), {k: sum(1 for x in excluded if x['kind'] == k) for k in ('dev', 'debug')})


if __name__ == '__main__':
    main()
