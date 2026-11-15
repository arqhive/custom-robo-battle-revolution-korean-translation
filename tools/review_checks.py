"""7단계 기계 검사(번역 전체) → manifests/review-machine.json

문제(규칙 위반이 분명)
- 마침표 누락: 대사 메시지·쪽(FE0003 앞) 끝이 한글 종결형인데 부호 없음(감탄·웃음뿐인 줄 제외)
- 말줄임표·물결표 뒤 마침표
- 그녀·그들을 한 메시지에 두 번 이상
- 전각 영숫자·！？ 남음
- 띄어쓰기: 공백 두 칸(전각 공백 칸 맞춤 줄 제외), 부호 앞 공백
확인(사람이 봐야 함)
- 직역투 낱말: 이 내가 / 해 버렸 / 에 대해 / 이것을·그것을·저것을 / 하고 있다
- 숫자 불일치: 원문 숫자(전각 포함)가 번역에 없음
- 같은 원문(12자 이하) 다른 번역
- 길이 비율: 번역 글자 수가 원문의 0.35배 미만(빠뜨림 의심) 또는 3배 초과(덧붙임 의심), 원문 6자 이상만
"""
import collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

B = os.path.join(disc.ROOT, 'work/translation/batches')
O = os.path.join(disc.ROOT, 'work/translation/out')
TAG0 = re.compile(r'\{[^}]*\}')
NAME = re.compile(r'\{1A:FE0008\}')


class _Tag:
    """제어 코드를 지우되 주인공 이름 자리는 「아무개」로 채운다(빈자리 때문에 띄어쓰기 오탐이 남)."""
    def sub(self, r, s): return TAG0.sub(r, NAME.sub('아무개', s))


TAG = _Tag()
PAGE = re.compile(r'\{1A:FE0003[0-9A-F]{2}\}')
Z2H = str.maketrans('０１２３４５６７８９', '0123456789')
INTERJ = re.compile(r'^[\s「（(]*[가-힣]{0,3}([아앗악윽흑헉하호후히헤으우오에이흐햐핫킥큭])+[!?…~\-]*[)」）]?$')
KANJI_NUM = re.compile(r'[一二三四五六七八九十百千万]')


def load():
    items = []
    for f in sorted(os.listdir(B)):
        tr = json.load(open(os.path.join(O, f), encoding='utf-8'))['translations']
        for x in json.load(open(os.path.join(B, f), encoding='utf-8')):
            if 'dup_of' in x or x['id'] not in tr: continue
            items.append(dict(x, batch=f[:-5], ko=tr[x['id']]))
    assert items
    return items


def main():
    items = load()
    res = collections.defaultdict(list)
    def add(cat, x, text): res[cat].append({'id': x['id'], 'batch': x['batch'], 'text': text})
    for x in items:
        ko, jp = x['ko'], x['jp']
        core = TAG.sub('', ko); jcore = TAG.sub('', jp)
        if x['kind'] in ('line', 'choice'):
            for seg in PAGE.split(ko):
                s = TAG.sub('', seg).strip()
                if not s or 'FE0007' in seg: continue
                last = s.split('\n')[-1].strip()
                if re.search(r'[가-힣]$', last) and len(last) >= 2 and not INTERJ.match(last):
                    add('마침표 누락', x, s.replace('\n', '/')); break
        if x['kind'] == 'tip' and re.search(r'[가-힣]다$', core.strip()): add('마침표 누락', x, core.replace('\n', '/')[-40:])
        if re.search(r'[…~〜～]\.', core): add('말줄임표·물결표 뒤 마침표', x, core)
        for w in ('그녀', '그들'):
            if core.count(w) >= 2: add('그녀·그들 반복', x, core.replace('\n', '/'))
        if re.search(r'[Ａ-Ｚａ-ｚ０-９！？]', core): add('전각 영숫자 남음', x, core.replace('\n', '/'))
        if (re.search(r'[가-힣A-Za-z0-9.,!?]  +[가-힣A-Za-z0-9]', core) and '　' not in jcore) or re.search(r' [.,!?]', core):
            add('띄어쓰기(두 칸·부호 앞)', x, core.replace('\n', '/'))
        for w in ('이 내가', '해 버렸', '에 대해', '이것을', '그것을', '저것을', '하고 있다'):
            if w in core: add('직역투 확인: ' + w, x, core.replace('\n', '/'))
        nj = set(re.findall(r'\d+', jcore.translate(Z2H))); nk = set(re.findall(r'\d+', core))
        if nj - nk and not KANJI_NUM.search(jcore): add('숫자 불일치 확인', x, '빠진 숫자 %s | %s' % (sorted(nj - nk), core.replace('\n', '/')))
        jl = len(re.sub(r'[\s…・。、！？!?]', '', jcore)); kl = len(re.sub(r'[\s…・.,!?]', '', core))
        if jl >= 6 and (kl < jl * 0.35 or kl > jl * 3): add('길이 비율 확인', x, '%d→%d | %s | %s' % (jl, kl, jcore.replace('\n', '/')[:40], core.replace('\n', '/')[:50]))
    by = collections.defaultdict(set)
    for x in items:
        j = TAG.sub('', x['jp']).strip()
        if len(j) <= 12: by[j].add(TAG.sub('', x['ko']).strip())
    for j, kos in by.items():
        if len(kos) > 1 and re.search(r'[ぁ-んァ-ヶ一-龥]', j):
            res['같은 원문 다른 번역 확인'].append({'id': j, 'batch': '', 'text': ' / '.join(sorted(kos))})
    json.dump(res, open(os.path.join(disc.ROOT, 'manifests/review-machine.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('검사 항목', len(items))
    for k in sorted(res, key=lambda k: -len(res[k])):
        print('%-26s %5d  예: %s' % (k, len(res[k]), res[k][0]['text'][:70]))


if __name__ == '__main__':
    main()
