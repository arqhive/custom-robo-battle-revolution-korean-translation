"""용어집 합치기 → work/glossary/glossary-ko.json, docs/glossary.md

- work/glossary/draft-terms.json(인물·지명·단체·용어·메뉴) + draft-parts.json(파츠·로보·스테이지).
- 둘 다에 있는 원문은 draft-parts 를 따른다(파츠 담당이 시리즈 조각 대조를 함). 번역이 다르면 충돌로 보고.
- work/glossary/decisions.json 이 있으면 사용자 결정으로 덮어쓴다({원문: 번역}).
- 번역의 전각 영숫자·！？는 반각으로(표기 규칙 「원래 영어는 반각」). 가운뎃점 · (U+00B7)은 게임 글꼴에 없어 「・」로.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

G = os.path.join(disc.ROOT, 'work/glossary')
Z2H = {c: chr(c - 0xFEE0) for c in list(range(0xFF10, 0xFF1A)) + list(range(0xFF21, 0xFF3B)) + list(range(0xFF41, 0xFF5B)) + [0xFF01, 0xFF1F]}
Z2H[0xB7] = '・'


def main():
    terms = json.load(open(os.path.join(G, 'draft-terms.json'), encoding='utf-8'))
    parts = json.load(open(os.path.join(G, 'draft-parts.json'), encoding='utf-8'))
    dec_p = os.path.join(G, 'decisions.json')
    dec = json.load(open(dec_p, encoding='utf-8')) if os.path.exists(dec_p) else {}
    out, clash = {}, []
    for src, d in (('terms', terms), ('parts', parts)):
        for jp, v in d.items():
            if jp in out and out[jp]['ko'] != v['ko']:
                clash.append((jp, out[jp]['ko'], v['ko']))
            out[jp] = {'ko': v['ko'], 'cat': v.get('cat', ''), 'note': v.get('note', ''), 'sure': v.get('sure', True), 'from': src}
    for jp, ko in dec.items():
        if jp in out: out[jp].update(ko=ko, sure=True, note=(out[jp]['note'] + ' / 사용자 결정').strip(' /'))
        else: out[jp] = {'ko': ko, 'cat': '결정', 'note': '사용자 결정', 'sure': True, 'from': 'decision'}
    for v in out.values(): v['ko'] = v['ko'].translate(Z2H)
    json.dump(out, open(os.path.join(G, 'glossary-ko.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cats = {}
    for jp, v in out.items(): cats.setdefault(v['cat'] or '기타', []).append((jp, v))
    lines = ['# 용어집 (%d항목)' % len(out), '', '원문 → 한국어. ☆ = 확정 전(질문 대상). 만드는 도구 `tools/make_glossary.py`.', '']
    for c in sorted(cats, key=lambda c: -len(cats[c])):
        lines += ['## %s (%d)' % (c, len(cats[c])), '', '| 원문 | 한국어 | 메모 |', '|---|---|---|']
        for jp, v in cats[c]:
            lines.append('| %s | %s%s | %s |' % (jp, v['ko'], '' if v['sure'] else ' ☆', v['note'].replace('|', '/').replace('\n', ' ')[:80]))
        lines.append('')
    open(os.path.join(disc.ROOT, 'docs/glossary.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print('항목', len(out), '확정 전', sum(not v['sure'] for v in out.values()), '충돌', clash)


if __name__ == '__main__':
    main()
