"""대사 다시 번역: 같은 장소의 같은 조사 대사 옮겨 오기 — python -X utf8 tools/redo_same.py dlg-14 125 250 dlg-14.b

묶음 [시작, 끝) 줄 중 원문·화자가 이미 번역한 줄(redo/ 전체 + parts)과 글자까지 같은 줄만 그 번역을 복사해
redo/parts/<조각 이름>.json 에 쓴다(물건 조사 혼잣말처럼 장면이 같은 반복 대사용 — 화자·상대가 다르면 쓰지 않는다).
남은 줄 id 를 찍는다. 옮긴 줄도 다시 읽어 장면에 맞는지 본 뒤 고친다.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

T = os.path.join(disc.ROOT, 'work/translation')


def main():
    name, a, b, part = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    items = []
    for f in sorted(os.listdir(os.path.join(T, 'batches'))):   # 대괄호 경로라 glob 금지
        if f.startswith('dlg'): items += json.load(open(os.path.join(T, 'batches', f), encoding='utf-8'))
    byid = {x['id']: x for x in items}
    done = {}
    for d in ('redo', os.path.join('redo', 'parts')):
        for f in os.listdir(os.path.join(T, d)):
            if f.endswith('.json'):
                done.update(json.load(open(os.path.join(T, d, f), encoding='utf-8')).get('translations', {}))
    seen = {}
    for k, v in done.items():
        x = byid.get(k)
        if x: seen.setdefault((x['jp'], x.get('speaker', '').replace('(이어짐)', '')), v)
    batch = json.load(open(os.path.join(T, 'batches', name + '.json'), encoding='utf-8'))[a:b]
    out, rest = {}, []
    for x in batch:
        key = (x['jp'], x.get('speaker', '').replace('(이어짐)', ''))
        if x['id'] not in done and key in seen and x.get('speaker', '').startswith('主人公'): out[x['id']] = seen[key]
        elif x['id'] not in done: rest.append(x['id'])
    json.dump({'translations': out, 'notes': []}, open(os.path.join(T, 'redo', 'parts', part + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print('옮김', len(out), '남음', len(rest))
    print(' '.join(rest))


if __name__ == '__main__':
    main()
