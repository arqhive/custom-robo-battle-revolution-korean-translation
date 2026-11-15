"""통일 단계 기계 수정안 → work/translation/unify/mech.json (아직 반영 안 함)

- 따옴표: 원문에 「」가 있는데 번역이 ' ' 로 바꾼 곳 → 「」(RULES §2, 원문 「」『』는 그대로)
- 낱말 맞춤(사용자에게 대조표로 보여 줄 것):
  がまん値=인내치(시리즈 GX), 素早さ=재빠름, 足手まとい=짐, 外の世界=바깥의 세계(外界=바깥 세계와 구별), ラーメン=라멘(외래어 표기)
  (버블 すまんす 는 말투 통일 B 가 「죄송함다」로 맞춤 — 받침 없는 어간 뒤 ~ㅁ다)
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

B = os.path.join(disc.ROOT, 'work/translation/batches')
O = os.path.join(disc.ROOT, 'work/translation/out')
TAG = re.compile(r'\{[^}]*\}')
# (원문 낱말, 번역에서 찾을 말, 바꿀 말)
WORDS = [
    ('がまん値', '버팀 수치', '인내치'),
    ('素早さ', '민첩성', '재빠름'),
    ('足手まとい', '걸림돌', '짐'),
    ('足手まとい', '발목을 잡지', '짐이 되지'),
    ('足手まとい', '발목만\n잡지', '짐만\n되지'),
    ('ラーメン', '라면', '라멘'),
    ('外の世界', '밖의 세계', '바깥의 세계'),
]


def main():
    out = []
    for f in sorted(os.listdir(B)):
        items = json.load(open(os.path.join(B, f), encoding='utf-8'))
        tr = json.load(open(os.path.join(O, f), encoding='utf-8'))['translations']
        for x in items:
            k = x['id']; ko = tr.get(k)
            if ko is None: continue
            new = ko; why = []
            jp = TAG.sub('', x['jp'])
            if '「' in jp and '「' not in ko and ko.count("'") >= 2 and ko.count("'") % 2 == 0:
                parts = new.split("'")
                new = ''.join(p + (('「' if i % 2 == 0 else '」') if i < len(parts) - 1 else '') for i, p in enumerate(parts))
                why.append('따옴표 원문대로 「」')
            for w, a, b in WORDS:
                if w in jp and a in new and b not in new.replace(a, ''):
                    new = new.replace(a, b); why.append('%s=%s' % (w, b.replace('\n', '')))
            if new != ko:
                out.append({'cat': '기계', 'id': k, 'batch': f[:-5], 'speaker': x.get('speaker', ''), 'jp': x['jp'], 'before': ko, 'after': new, 'why': ', '.join(why)})
    os.makedirs(os.path.join(disc.ROOT, 'work/translation/unify'), exist_ok=True)
    json.dump(out, open(os.path.join(disc.ROOT, 'work/translation/unify/mech.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(out))
    for x in out: print(x['id'], x['why'], '|', TAG.sub('', x['after']).replace('\n', '/')[:70])


if __name__ == '__main__':
    main()
