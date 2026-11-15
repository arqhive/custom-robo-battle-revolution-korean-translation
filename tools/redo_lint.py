"""대사 다시 번역 문체 점검(사용자 번역 문제 17가지 중 기계로 잡히는 것): python -X utf8 tools/redo_lint.py dlg-00 [...]

고칠지는 줄마다 판단한다(일괄 치환 금지). 걸린 줄을 원문과 함께 찍는다.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

T = os.path.join(disc.ROOT, 'work/translation')
TAG = re.compile(r'\{[^}]*\}')
CHECKS = [
    ('맞장구 그렇구나·그렇군·그렇네', r'그렇(구나|군|네)'),
    ('한 대사 구나 2번', r'구나[\s\S]*구나'),
    ('~네 끝', r'(같|없|있|하|되|다|이)네[.!?…~]*$'),
    ('문장 끝 ~니까', r'(?<![습입])니까[!.?]*$'),
    ('이걸로·그걸로', r'(이|그)걸로'),
    ('~해 버리다', r'(해|져|어|아|워) 버(렸|린|려|릴)'),
    ('~것이다·~는 거야 남발', r'것이다'),
    ('대체', r'대체'),
    ('나 자신', r'나 자신'),
    ('~하는 게 좋', r'는 게 좋'),
    ('…, ~,', r'[…~],'),
    ('…. ~.', r'[…~]\.'),
    ('「좀」', r'좀'),
]


def main():
    for name in sys.argv[1:]:
        items = {x['id']: x for x in json.load(open(os.path.join(T, 'batches', name + '.json'), encoding='utf-8'))}
        tr = json.load(open(os.path.join(T, 'redo', name + '.json'), encoding='utf-8'))['translations']
        for label, pat in CHECKS:
            r = re.compile(pat, re.M)
            hit = [k for k, v in tr.items() if r.search(TAG.sub('', v))]
            if not hit: continue
            print('== %s %s %d' % (name, label, len(hit)))
            for k in hit:
                print('  %s [%s] %s → %s' % (k, items[k].get('speaker', ''), TAG.sub('', items[k]['jp']).replace('\n', '⏎'),
                                             TAG.sub('', tr[k]).replace('\n', '⏎')))


if __name__ == '__main__':
    main()
