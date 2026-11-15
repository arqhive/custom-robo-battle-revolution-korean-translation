"""칸 넘침 수정안 합치기 → work/translation/fit-proposed.json, docs/fit-table.html

work/translation/fit/out-*.json 을 모아 원문 | 지금 | 수정안 표로. 폭·줄 수는 fit_check 와 같은 방식으로 다시 잰다.
지금 번역과 같은 것(「줄일 수 없음」)은 표 아래쪽 따로.
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc, fit_check

T = os.path.join(disc.ROOT, 'work/translation')
TAG = re.compile(r'\{[^}]*\}')
# 사운드 설정 값 자리는 실기 스샷 비율로 손으로 맞춤(10/30) — 에이전트 수정안 안 씀
MANUAL = {'info:03:000', 'info:03:001', 'info:03:002'}


def main():
    lim = {r['id']: r for r in json.load(open(os.path.join(disc.ROOT, 'manifests/ui-fit.json'), encoding='utf-8'))}
    rows = []
    prop = {}
    for f in sorted(os.listdir(os.path.join(T, 'fit'))):
        if f.startswith('out-'):
            for x in json.load(open(os.path.join(T, 'fit', f), encoding='utf-8'))['fixes']:
                if x['id'] not in MANUAL: prop[x['id']] = x   # out2-* 가 out-* 를 덮는다(파일 이름 순)
    for k, r in lim.items():   # 지금 넘침 목록 기준(목록에서 빠진 옛 수정안은 버림)
            x = prop.get(k, {'id': k, 'after': r['ko'], 'why': '수정안 없음'})
            if True:
                bt = fit_check.built(x['after'], r); w = fit_check.px(bt)
                rows.append({'id': x['id'], 'jp': r['jp'], 'before': r['ko_built'], 'after': bt, 'why': x.get('why', ''),
                             'limit': '%dpx·%d줄' % (r['limit_px'], r['limit_lines']), 'before_px': r['ko_px'], 'after_px': round(max(w)),
                             'ok': max(w) <= r['limit_px'] and bt.rstrip('\n').count('\n') + 1 <= r['limit_lines'],
                             'same': x['after'] == r['ko'], 'after_src': x['after']})
    missing = set()
    rows.sort(key=lambda r: (r['same'], r['id']))
    json.dump([dict(r, after=r['after_src']) for r in rows if not r['same']], open(os.path.join(T, 'fit-proposed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    def cell(s): return html.escape(TAG.sub('', s)).replace('\n', '<br>').replace('　', '□')
    trs = ''.join('<tr class="%s"><td class=id>%s<br><small>%s</small></td><td>%s</td><td class=b>%s<br><small>%dpx</small></td><td class=a>%s<br><small>%dpx%s</small></td><td><small>%s</small></td></tr>' % (
        'same' if r['same'] else '', r['id'], r['limit'], cell(r['jp']), cell(r['before']), r['before_px'], cell(r['after']), r['after_px'],
        '' if r['ok'] else ' 넘침', html.escape(r['why'])) for r in rows)
    n = sum(not r['same'] for r in rows)
    page = '''<!doctype html><html lang=ko><head><meta charset=utf-8><title>칸 넘침 대조표</title><style>
:root{--bg:#fff;--fg:#222;--line:#ccc;--b:#fde8e8;--a:#e6f6e6;--s:#f2f2f2}
@media (prefers-color-scheme:dark){:root{--bg:#1c1c1c;--fg:#ddd;--line:#444;--b:#4a2626;--a:#24402a;--s:#2a2a2a}}
body{background:var(--bg);color:var(--fg);font-family:"Malgun Gothic",sans-serif;margin:16px}
table{border-collapse:collapse;width:100%%}td,th{border:1px solid var(--line);padding:4px 6px;vertical-align:top;font-size:14px}
.b{background:var(--b)}.a{background:var(--a)}.id{white-space:nowrap}tr.same td{background:var(--s)}
</style></head><body><h1>메뉴·설명 칸 넘침 대조표 (커스텀 로보 배틀 레볼루션)</h1>
<p>수정안 %d건, 줄일 수 없음 %d건%s. 한계 = 그 칸 원문 폭·줄 수(파츠 설명·도움말·이름 칸은 칸에서 가장 긴 원문). □ = 전각 공백. 아직 반영 안 함.</p>
<table><tr><th>id / 한계</th><th>원문</th><th>지금</th><th>수정안</th><th>이유</th></tr>%s</table></body></html>''' % (
        n, len(rows) - n, ', 빠진 id %d' % len(missing) if missing else '', trs)
    open(os.path.join(disc.ROOT, 'docs/fit-table.html'), 'w', encoding='utf-8').write(page)
    print('수정안', n, '그대로', len(rows) - n, '넘침', sum(not r['ok'] for r in rows), '빠짐', sorted(missing))


if __name__ == '__main__':
    main()
