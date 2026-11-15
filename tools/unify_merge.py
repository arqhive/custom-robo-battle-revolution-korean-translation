"""통일 수정안 합치기 → work/translation/unify-proposed.json, docs/unify-table.html

- work/translation/unify/{mech,tone-A,tone-B,tone-A2}.json 을 모은다. tone-A2(주인공 높임 원문 다수결 재점검)가 철회한 tone-A 줄은 WITHDRAWN 으로 뺀다.
- 「전」이 지금 번역과 다르면(그새 바뀜) 멈춘다. 제어 코드가 달라진 수정안도 멈춘다.
- 같은 id 를 두 수정안이 고치면: 한쪽 「후」가 다른 쪽 「전」에서 이어지면 이어 붙이고, 아니면 충돌로 표시.
- 사용자 결정이 걸린 줄은 cat 을 「결정 대기 …」로 따로 묶는다.
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

T = os.path.join(disc.ROOT, 'work/translation')
CODE = re.compile(r'\{1A:[0-9A-Fa-f]*\}|\{[0-9A-Fa-f]{2}\}|%[0-9]*[sd]')
TAG = re.compile(r'\{[^}]*\}')
# 결정이 걸린 줄: id → 결정 묶음 이름
DECIDE = {
    'snr_t_14:678': 'A-Q4 마샤의 兄=오라버니', 'snr_t_15:706': 'A-Q4 마샤의 兄=오라버니',
}
# 셰리(사용자 확정: 반말)·히로코(원문 반말 6:2) 해요체 수정안 철회
WITHDRAWN = {'snr_t_13:620', 'snr_t_13:623', 'snr_f_13:380', 'snr_f_13:381',
             'snr_f_11:314', 'snr_f_11:315', 'snr_f_23:340', 'snr_f_23:476', 'snr_f_23:477'}


def current():
    tr, where = {}, {}
    for f in os.listdir(os.path.join(T, 'out')):
        for k, v in json.load(open(os.path.join(T, 'out', f), encoding='utf-8'))['translations'].items():
            tr[k] = v; where[k] = f[:-5]
    return tr, where


def main():
    tr, where = current()
    rows, clash = {}, []
    for name, label in (('mech', '기계'), ('tone-A', '말투 A'), ('tone-B', '말투 B'), ('tone-A2', '주인공 높임 다수결')):
        for x in json.load(open(os.path.join(T, 'unify', name + '.json'), encoding='utf-8')):
            k = x['id']
            if name == 'tone-A' and k in WITHDRAWN: continue
            if '질문 Q2' in x.get('why', ''): x['question'] = 'A2-Q2 주인공→트리시 반말'
            assert CODE.findall(x['before']) == CODE.findall(x['after']), ('제어 코드 다름', name, k)
            cat = label
            if x.get('question'): cat = '결정 대기 ' + (x['question'] if x['question'].startswith('A2') else 'B-' + x['question'])
            if k in DECIDE: cat = '결정 대기 ' + DECIDE[k]
            if k in rows:
                prev = rows[k]
                if prev['after'] == x['before']: prev['after'] = x['after']; prev['why'] += ' / ' + x['why']; prev['cat'] += '+' + label; continue
                if x['after'] == prev['before']: continue
                clash.append((k, prev['cat'], label)); continue
            assert tr[k] == x['before'], ('번역이 수정안 「전」과 다름', name, k)
            rows[k] = {'cat': cat, 'id': k, 'batch': where[k], 'speaker': x.get('speaker', ''), 'listener': x.get('listener', ''),
                       'jp': x['jp'], 'before': x['before'], 'after': x['after'], 'why': x.get('why', '')}
    out = sorted(rows.values(), key=lambda r: (not r['cat'].startswith('결정'), r['cat'], r['batch'], r['id']))
    json.dump(out, open(os.path.join(T, 'unify-proposed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cnt = {}
    for r in out: cnt[r['cat']] = cnt.get(r['cat'], 0) + 1
    def cell(s): return html.escape(TAG.sub('', s)).replace('\n', '<br>')
    trs = ''.join('<tr><td>%s</td><td class=id>%s<br><small>%s</small></td><td><small>%s→%s</small></td><td>%s</td><td class=b>%s</td><td class=a>%s</td><td><small>%s</small></td></tr>' % (
        html.escape(r['cat']), r['id'], r['batch'], html.escape(r['speaker']), html.escape(r['listener']), cell(r['jp']), cell(r['before']), cell(r['after']), html.escape(r['why'])) for r in out)
    page = '''<!doctype html><html lang=ko><head><meta charset=utf-8><title>통일 대조표</title><style>
:root{--bg:#fff;--fg:#222;--line:#ccc;--b:#fde8e8;--a:#e6f6e6}
@media (prefers-color-scheme:dark){:root{--bg:#1c1c1c;--fg:#ddd;--line:#444;--b:#4a2626;--a:#24402a}}
body{background:var(--bg);color:var(--fg);font-family:"Malgun Gothic",sans-serif;margin:16px}
table{border-collapse:collapse;width:100%%}td,th{border:1px solid var(--line);padding:4px 6px;vertical-align:top;font-size:14px}
.b{background:var(--b)}.a{background:var(--a)}.id{white-space:nowrap}
</style></head><body><h1>통일 대조표 (커스텀 로보 배틀 레볼루션)</h1>
<p>모두 %d건: %s. 제어 코드는 표에서 숨김(실제 수정안에는 그대로). 충돌: %s. 아직 반영 안 함.</p>
<table><tr><th>분류</th><th>id</th><th>화자→상대</th><th>원문</th><th>지금</th><th>수정안</th><th>이유</th></tr>%s</table></body></html>''' % (
        len(out), ' · '.join('%s %d' % kv for kv in cnt.items()), clash or '없음', trs)
    open(os.path.join(disc.ROOT, 'docs/unify-table.html'), 'w', encoding='utf-8').write(page)
    print(len(out), cnt, '충돌', clash)


if __name__ == '__main__':
    main()
