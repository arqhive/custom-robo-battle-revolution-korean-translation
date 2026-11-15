"""통일 단계 조사 → work/translation/unify-survey.json, docs/translation-unify.md

1. 새 낱말 갈림: 번역 notes 의 「원문=번역」「원문 → 번역」을 모아 같은 원문에 번역이 둘 이상인 것.
   실제 번역문에서 그 원문이 든 항목마다 어느 번역을 썼는지 센다.
2. 젝스 머리글자 말장난: 원문 줄 머리가 ゼ·ク·ス 로 이어지는 항목(원문·번역).
3. 따옴표: 원문에 「」가 있는데 번역에 없는 항목.
4. 화자 보정: notes 에서 화자 표를 바꿨다고 적은 항목 수.
"""
import collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

B = os.path.join(disc.ROOT, 'work/translation/batches')
O = os.path.join(disc.ROOT, 'work/translation/out')
TAG = re.compile(r'\{[^}]*\}')
PAIR = re.compile(r'([ぁ-んァ-ヶー一-龥々〜～・Ａ-Ｚａ-ｚ０-９A-Za-z!！?？]{2,20})\s*(?:=|→|->)\s*[「『\']?([가-힣A-Za-z0-9][가-힣A-Za-z0-9 ~・\-]{0,20}?)(?=[」』\'(（,，、/·.;:\s]|$)')


def load():
    items, tr, notes = {}, {}, []
    for f in sorted(os.listdir(B)):
        for x in json.load(open(os.path.join(B, f), encoding='utf-8')): items[x['id']] = dict(x, batch=f[:-5])
        d = json.load(open(os.path.join(O, f), encoding='utf-8'))
        tr.update(d['translations'])
        notes += [dict(n, batch=f[:-5]) for n in d.get('notes', [])]
    assert items and tr
    for k, x in items.items():           # dup_of 는 대표 번역을 따름
        if 'dup_of' in x and x['dup_of'] in tr: tr.setdefault(k, tr[x['dup_of']])
    return items, tr, notes


def main():
    items, tr, notes = load()
    # 1. 새 낱말 갈림
    pairs = collections.defaultdict(lambda: collections.defaultdict(list))
    for n in notes:
        for a, b in PAIR.findall(n['note']):
            b = b.strip()
            if len(b) >= 1: pairs[a][b].append(n['batch'])
    split = {}
    for a, bs in pairs.items():
        if len(bs) < 2: continue
        use = collections.Counter()
        for k, x in items.items():
            if a in TAG.sub('', x['jp']) and k in tr:
                ko = tr[k]
                for b in bs:
                    if b in ko: use[b] += 1
        split[a] = {b: {'batches': sorted(set(v)), 'used': use.get(b, 0)} for b, v in bs.items()}
    # 2. 젝스 머리글자
    acro = []
    for k, x in items.items():
        lines = TAG.sub('', x['jp']).split('\n')
        heads = ''.join(l[:1] for l in lines)
        if re.search(r'ゼ.?ク.?ス', heads) or re.search(r'ゼ.*\n?ク.*\n?ス.*さん', TAG.sub('', x['jp'])):
            acro.append({'id': k, 'batch': x['batch'], 'jp': TAG.sub('', x['jp']), 'ko': TAG.sub('', tr.get(k, ''))})
    # 3. 따옴표
    quote = [{'id': k, 'jp': TAG.sub('', x['jp'])[:60], 'ko': TAG.sub('', tr[k])[:60]}
             for k, x in items.items() if k in tr and '「' in x['jp'] and '「' not in tr[k]]
    # 4. 화자 보정
    spk = [n for n in notes if '화자' in n['note'] and n.get('id', '*') != '*']
    out = {'split': split, 'acrostic': acro, 'quote': quote, 'speaker_fix': spk}
    json.dump(out, open(os.path.join(disc.ROOT, 'work/translation/unify-survey.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('갈림', len(split), '젝스 말장난', len(acro), '따옴표', len(quote), '화자 보정 notes', len(spk))


if __name__ == '__main__':
    main()
