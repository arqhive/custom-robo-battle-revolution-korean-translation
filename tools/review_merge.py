"""7단계 검수 수정안 합치기 → work/translation/review-proposed.json, docs/review-table.html

- work/translation/review/*.json(R1~R9, ZX)의 fixes 를 모은다.
- 지금 번역과 같은 수정안은 뺀다. 제어 코드가 달라진 수정안·게임 글꼴로 못 바꾸는 글자는 멈춘다.
- 같은 id 를 두 담당이 고치면 충돌로 표시(둘 다 표에 남김).
- 사용자 결정이 걸린 줄은 cat 을 「결정 대기 …」로 따로 묶는다(DECIDE).
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc, kotext

T = os.path.join(disc.ROOT, 'work/translation')
CODE = re.compile(r'\{1A:[0-9A-Fa-f]*\}|\{[0-9A-Fa-f]{2}\}|%[0-9]*[sd]')
TAG = re.compile(r'\{[^}]*\}')
DECIDE = {}   # id → 결정 묶음 이름(사용자 질문에 걸린 줄)
# 원문 낱말로 결정 묶음 정하기: (원문에 든 말, 수정안에 든 말, 결정 묶음)
DECIDE_RULES = [('通常', '통상', 'Q5 通常=통상'), ('終了', '종료', 'Q6 終了=종료'),
                ('スティルハーツさん', '스틸하츠 쪽', 'Q1 회사 さん=쪽'), ('やめ', '끝내시겠습니까', 'Q6 終了=종료')]


def main():
    tr, where, jp = {}, {}, {}
    for f in os.listdir(os.path.join(T, 'out')):
        for k, v in json.load(open(os.path.join(T, 'out', f), encoding='utf-8'))['translations'].items():
            tr[k] = v; where[k] = f[:-5]
    for f in os.listdir(os.path.join(T, 'batches')):
        for x in json.load(open(os.path.join(T, 'batches', f), encoding='utf-8')): jp[x['id']] = x
    rows, seen, dropped, notes = [], {}, {'같음': 0, 'id 없음': 0}, []
    for f in sorted(os.listdir(os.path.join(T, 'review'))):
        if not f.endswith('.json'): continue
        d = json.load(open(os.path.join(T, 'review', f), encoding='utf-8'))
        notes += ['[%s] %s' % (f[:-5], n if isinstance(n, str) else json.dumps(n, ensure_ascii=False)) for n in d.get('notes', [])]
        for x in d.get('fixes', []):
            k = x['id']
            if k not in tr: dropped['id 없음'] += 1; continue
            if x['after'] == tr[k]: dropped['같음'] += 1; continue
            assert CODE.findall(x['after']) == CODE.findall(tr[k]), ('제어 코드 다름', f, k)
            kotext.to_game(x['after'])
            cat = DECIDE.get(k, x.get('type', '기타'))
            for a, b, name in DECIDE_RULES:
                if a in jp[k]['jp'] and b in x['after'] and b not in tr[k]: cat = '결정 대기 ' + name
            r = {'cat': cat, 'who': f[:-5], 'id': k, 'batch': where[k], 'speaker': jp[k].get('speaker', ''),
                 'jp': jp[k]['jp'], 'before': tr[k], 'after': x['after'], 'why': x.get('why', '')}
            if k in seen: r['cat'] = '충돌 ' + r['cat']; seen[k]['cat'] = '충돌 ' + seen[k]['cat']
            seen[k] = r; rows.append(r)
    order = lambda r: (0 if r['cat'].startswith('충돌') else 1 if r['cat'].startswith('결정') else 2, r['cat'], r['batch'], r['id'])
    rows.sort(key=order)
    json.dump(rows, open(os.path.join(T, 'review-proposed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cnt = {}
    for r in rows: cnt[r['cat']] = cnt.get(r['cat'], 0) + 1
    def cell(s): return html.escape(TAG.sub('', s.replace('{1A:FE0008}', '〈주〉'))).replace('\n', '<br>')
    trs = ''.join('<tr><td>%s<br><small>%s</small></td><td class=id>%s<br><small>%s</small></td><td><small>%s</small></td><td>%s</td><td class=b>%s</td><td class=a>%s</td><td><small>%s</small></td></tr>' % (
        html.escape(r['cat']), r['who'], r['id'], r['batch'], html.escape(r['speaker']), cell(r['jp']), cell(r['before']), cell(r['after']), html.escape(r['why'])) for r in rows)
    page = '''<!doctype html><html lang=ko><head><meta charset=utf-8><title>검수 대조표</title><style>
:root{--bg:#fff;--fg:#222;--line:#ccc;--b:#fde8e8;--a:#e6f6e6}
@media (prefers-color-scheme:dark){:root{--bg:#1c1c1c;--fg:#ddd;--line:#444;--b:#4a2626;--a:#24402a}}
body{background:var(--bg);color:var(--fg);font-family:"Malgun Gothic",sans-serif;margin:16px}
table{border-collapse:collapse;width:100%%}td,th{border:1px solid var(--line);padding:4px 6px;vertical-align:top;font-size:14px}
.b{background:var(--b)}.a{background:var(--a)}.id{white-space:nowrap}
</style></head><body><h1>7단계 원문 대조 검수 대조표 (커스텀 로보 배틀 레볼루션)</h1>
<p>모두 %d건: %s. 빠진 것: %s. 〈주〉=주인공 이름, 다른 제어 코드는 표에서 숨김. 아직 반영 안 함.</p>
<table><tr><th>분류</th><th>id</th><th>화자</th><th>원문</th><th>지금</th><th>수정안</th><th>이유</th></tr>%s</table></body></html>''' % (
        len(rows), ' · '.join('%s %d' % kv for kv in sorted(cnt.items(), key=lambda kv: -kv[1])), dropped, trs)
    open(os.path.join(disc.ROOT, 'docs/review-table.html'), 'w', encoding='utf-8').write(page)
    open(os.path.join(T, 'review-notes.md'), 'w', encoding='utf-8').write('# 검수 담당 메모\n\n' + '\n'.join('- ' + n for n in notes) + '\n')
    print(len(rows), cnt, dropped, '메모', len(notes))


if __name__ == '__main__':
    main()
