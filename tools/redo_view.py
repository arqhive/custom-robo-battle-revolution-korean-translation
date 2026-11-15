"""대사 다시 번역(11/13)용 묶음 보기: python -X utf8 tools/redo_view.py dlg-00 [시작 끝]

줄마다 「id [화자] 원문 ‖ 영어판」(줄바꿈은 ⏎), 맨 끝에 이 묶음 원문에 나오는 용어집 항목.
dup_of 항목도 그대로 보인다(다시 번역은 자리마다 따로 옮김).
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

B = os.path.join(disc.ROOT, 'work/translation/batches')


def main():
    name = sys.argv[1]
    items = json.load(open(os.path.join(B, name + '.json'), encoding='utf-8'))
    a, b = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, len(items))
    for it in items[a:b]:
        en = it.get('en', '').replace('\n', '⏎')
        print('%s [%s]%s %s ‖ %s' % (it['id'], it.get('speaker', ''), ' (선택지)' if it['kind'] == 'choice' else '',
                                     it['jp'].replace('\n', '⏎'), en))
    gloss = json.load(open(os.path.join(disc.ROOT, 'work/glossary/glossary-ko.json'), encoding='utf-8'))
    text = ''.join(it['jp'] for it in items[a:b])
    hits = sorted((k for k in gloss if len(k) >= 2 and k in text), key=lambda k: -len(k))
    print('== 용어집:', ' / '.join('%s=%s' % (k, gloss[k]['ko']) for k in hits))


if __name__ == '__main__':
    main()
