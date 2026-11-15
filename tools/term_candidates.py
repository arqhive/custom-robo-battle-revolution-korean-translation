"""5단계 용어 후보 → work/glossary/candidates.json

후보
- name  : info 15블록(화자·대회 이름)
- list  : info 한 줄 항목(파츠·로보·스테이지·메뉴 이름 등) — 블록 번호를 cat 으로
- kata  : 대사·설명에서 3번 이상 나오는 가타카나 낱말(3자 이상, ー·・ 포함)
- kanji : 대사에서 자주 나오는 「○○隊·○○編·○○大会」 같은 한자 고유어
시리즈 용어집(GX·V2, 1편 포함)에 같은 원문이 있으면 그 번역을 붙인다(src).
"""
import collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

GX = r'G:/KoreanTranslation/GPT초벌작/[GBA] 커스텀 로보 GX/work/glossary/glossary-ko.json'
V2 = r'G:/KoreanTranslation/[N64] 커스텀 로보 V2/work/glossary/glossary-ko.json'
B = os.path.join(disc.ROOT, 'work/translation/batches')
TAG = re.compile(r'\{[^}]*\}')
KATA = re.compile(r'[ァ-ヶー・][ァ-ヶー・]{2,}')
KANJI = re.compile(r'[一-龥ァ-ヶー]{1,6}(?:隊|編|大会|カップ|団|部|所|研究所|本部|基地|事務所|博士|署長|隊長|所長)')


def series():
    g = {}
    for path, src in ((V2, 'v2'), (GX, 'gx')):
        for k, v in json.load(open(path, encoding='utf-8')).items():
            g.setdefault(k, dict(v, src=v.get('src', src) if src == 'v2' else 'gx' if v.get('src') not in ('v1', 'v2') else v['src']))
    return g


def main():
    items = []
    for n in sorted(os.listdir(B)):
        items += json.load(open(os.path.join(B, n), encoding='utf-8'))
    assert items
    ser = series()
    cand = collections.OrderedDict()
    def add(jp, cat, en=''):
        jp = jp.strip()
        if not jp or jp in cand: return
        cand[jp] = {'cat': cat, 'en': en, 'count': 0}
    for x in items:
        if x['kind'] == 'name': add(TAG.sub('', x['jp']), '이름(info15)', x['en'])
    for x in items:
        if x['kind'] == 'info-1':
            add(TAG.sub('', x['jp']), 'info%s' % x['id'].split(':')[1], x['en'])
    freq = collections.Counter(); kf = collections.Counter()
    for x in items:
        if 'dup_of' in x or x['kind'] in ('dol-name',): continue
        t = TAG.sub('', x['jp'])
        freq.update(KATA.findall(t)); kf.update(KANJI.findall(t))
    for w, c in freq.items():
        if c >= 3: add(w, '가타카나')
    for w, c in kf.items():
        if c >= 3: add(w, '한자 고유어')
    alltext = '\n'.join(TAG.sub('', x['jp']) for x in items if 'dup_of' not in x)
    for jp, v in cand.items():
        v['count'] = alltext.count(jp)
        if jp in ser: v['series'] = ser[jp]['ko']; v['src'] = ser[jp].get('src', '')
    out = os.path.join(disc.ROOT, 'work/glossary'); os.makedirs(out, exist_ok=True)
    json.dump(cand, open(os.path.join(out, 'candidates.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    c = collections.Counter(v['cat'] for v in cand.values())
    print('후보', len(cand), '시리즈에 있음', sum('series' in v for v in cand.values()))
    print(c.most_common())


if __name__ == '__main__':
    main()
