"""대사 다시 번역 조각 합치기: python -X utf8 tools/redo_merge.py dlg-00

work/translation/redo/parts/<묶음>.*.json({"translations": {...}, "notes": [...]}) 을 이름 순으로 합쳐
work/translation/redo/<묶음>.json 으로 쓴다(뒤 조각이 앞 조각을 덮음). 묶음 순서대로 정렬하고 빠진 id 를 찍는다.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

T = os.path.join(disc.ROOT, 'work/translation')


def main():
    name = sys.argv[1]
    order = [x['id'] for x in json.load(open(os.path.join(T, 'batches', name + '.json'), encoding='utf-8'))]
    tr, notes = {}, []
    pd = os.path.join(T, 'redo', 'parts')
    for f in sorted(os.listdir(pd)):   # 대괄호 경로라 glob 금지
        if f.startswith(name + '.') and f.endswith('.json'):
            d = json.load(open(os.path.join(pd, f), encoding='utf-8'))
            tr.update(d.get('translations', {})); notes += d.get('notes', [])
    out = {'translations': {k: tr[k] for k in order if k in tr}, 'notes': notes}
    extra = [k for k in tr if k not in order]
    json.dump(out, open(os.path.join(T, 'redo', name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    miss = [k for k in order if k not in tr]
    print(name, '번역', len(out['translations']), '/', len(order), '빠짐', len(miss), miss[:10], '묶음 밖', extra)


if __name__ == '__main__':
    main()
