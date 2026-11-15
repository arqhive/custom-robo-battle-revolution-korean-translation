"""승인된 수정안을 번역 결과(work/translation/out)에 반영한다.

    python tools/unify_apply.py [수정안 파일=work/translation/unify-proposed.json] [백업 폴더 이름=before-unify]

반영 전 out 폴더를 work/translation/<백업 폴더 이름>/ 으로 한 번만 백업한다.
수정 전 문장이 지금 번역과 다르면(그새 바뀜) 멈춘다.
"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

T = os.path.join(disc.ROOT, 'work/translation')


def main(name='unify-proposed.json', backup='before-unify'):
    prop = json.load(open(os.path.join(T, name), encoding='utf-8'))
    assert prop, '수정안 0개'
    O = os.path.join(T, 'out'); bk = os.path.join(T, backup)
    if not os.path.exists(bk): shutil.copytree(O, bk)
    files = {}
    for x in prop:
        f = x['batch'] + '.json'
        if f not in files: files[f] = json.load(open(os.path.join(O, f), encoding='utf-8'))
        tr = files[f]['translations']
        assert tr[x['id']] == x['before'], ('번역이 수정안과 다름', x['id'])
        tr[x['id']] = x['after']
    for f, data in files.items():
        json.dump(data, open(os.path.join(O, f), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('반영', len(prop), '파일', len(files))


if __name__ == '__main__':
    main(*sys.argv[1:3])
