"""7단계 결정(사용자 10/23, Q2·Q3·Q4·Q7·Q8·Q9·Q10·Q12)의 일괄 수정안 → work/translation/bulk-proposed.json, docs/bulk-table.html

- Q3 속마음 괄호: 원문이 전각 （）인 줄에서 번역의 반각 ( )를 전각으로
- Q8 ここでのバトル: 「여기서의 배틀」→「여기 배틀」
- 나머지는 줄마다 정한 바꾸기(EDITS): 조사까지 맞춤
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import disc

T = os.path.join(disc.ROOT, 'work/translation')
TAG = re.compile(r'\{[^}]*\}')
EDITS = {  # id: [(찾을 말, 바꿀 말, 결정)]
    'snr_t_02:400': [('식은 죽 먹기일 테고', '낙승일 테고', 'Q2 楽勝=낙승')],
    'snr_t_02:402': [('식은 죽 먹기, 식은 죽 먹기!', '낙승, 낙승!', 'Q2 楽勝=낙승')],
    'snr_t_02:416': [('식은 죽 먹기, 식은 죽 먹기!', '낙승, 낙승!', 'Q2 楽勝=낙승')],
    'snr_t_03:124': [('식은 죽 먹기', '낙승', 'Q2 楽勝=낙승')],
    'snr_t_03:130': [('식은 죽 먹기.', '낙승.', 'Q2 楽勝=낙승')],
    'snr_t_07:138': [('쉽게 이길 줄', '낙승일 줄', 'Q2 楽勝=낙승')],
    'snr_t_11:936': [('쉽게 이기겠는데', '낙승이겠는데', 'Q2 楽勝=낙승')],
    'snr_t_02:250': [('여자한테서', '여성한테서', 'Q4 女性=여성')],
    'snr_t_02:526': [('여자 한 명', '여성 한 명', 'Q4 女性=여성')],
    'snr_t_04:12': [('젊은 여자가', '젊은 여성이', 'Q4 女性=여성')],
    'snr_t_04:67': [('남자 출입 금지', '남성 출입 금지', 'Q4 男性=남성')],
    'snr_t_08:225': [('같은 여자로서', '같은 여성으로서', 'Q4 女性=여성')],
    'snr_t_09:316': [('여자 옷장', '여성 옷장', 'Q4 女性=여성')],
    'snr_t_12:302': [('여자 동반으로', '여성 동반으로', 'Q4 女性=여성')],
    'snr_t_12:456': [('일행인 여자,', '일행인 여성,', 'Q4 女性=여성')],
    'snr_t_18:457': [('여자들이', '여성들이', 'Q4 女性=여성')],
    'snr_t_18:487': [('여자한테', '여성한테', 'Q4 女性=여성')],
    'snr_t_18:548': [('남자라 해도', '남성이라 해도', 'Q4 男性=남성')],
    'snr_t_16:99': [('이놈, 이놈, 이노오옴!', '괘씸한, 괘씸한, 괘씸하다아!', 'Q7 おのれ=괘씸한')],
    'snr_t_18:635': [('이 녀석들…', '괘씸한…', 'Q7 おのれ=괘씸한')],
    'snr_t_13:897': [('엘레강스한', '엘리건트한', 'Q10 エレガント=엘리건트')],
    'snr_t_13:898': [('엘레강스는', '엘리건트는', 'Q10 エレガント=엘리건트'), ('엘레강스고', '엘리건트고', 'Q10 エレガント=엘리건트')],
    'snr_t_14:167': [('일당은', '보수는', 'Q10 仕事料=보수')],
    'snr_t_14:171': [('일당은', '보수는', 'Q10 仕事料=보수')],
    'info:03:003': [('초기값으로 되돌리기', '초기값 복원', 'Q9 初期値に戻す=초기값 복원')],
    'info:16:007': [('초기값으로 되돌리기', '초기값 복원', 'Q9 初期値に戻す=초기값 복원')],
    'snr_f_13:164': [('괜찮아\n', '괜찮아요\n', 'Q12 주인공→린파 해요체'), ('부탁해!', '부탁해요!', 'Q12 주인공→린파 해요체')],
}


def main():
    items, tr, where = {}, {}, {}
    for f in os.listdir(os.path.join(T, 'batches')):
        for x in json.load(open(os.path.join(T, 'batches', f), encoding='utf-8')):
            if 'dup_of' not in x: items[x['id']] = x
        for k, v in json.load(open(os.path.join(T, 'out', f), encoding='utf-8'))['translations'].items():
            tr[k] = v; where[k] = f[:-5]
    out = []
    for k, x in items.items():
        if k not in tr: continue
        ko = tr[k]; new = ko; why = []
        j = TAG.sub('', x['jp'])
        if '（' in j and '(' not in j and '(' in new:
            new = new.replace('(', '（').replace(')', '）'); why.append('Q3 속마음 괄호 전각')
        if 'ここでのバトル' in j and '여기서의 배틀' in new:
            new = new.replace('여기서의 배틀', '여기 배틀'); why.append('Q8 ここでのバトル=여기 배틀')
        for a, b, w in EDITS.get(k, []):
            assert a in new, (k, a)
            new = new.replace(a, b); why.append(w)
        if new != ko:
            out.append({'cat': why[0].split()[0], 'id': k, 'batch': where[k], 'speaker': x.get('speaker', ''), 'jp': x['jp'], 'before': ko, 'after': new, 'why': ', '.join(why)})
    assert set(EDITS) <= {r['id'] for r in out}, set(EDITS) - {r['id'] for r in out}
    out.sort(key=lambda r: (r['cat'], r['batch'], r['id']))
    json.dump(out, open(os.path.join(T, 'bulk-proposed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cnt = {}
    for r in out: cnt[r['cat']] = cnt.get(r['cat'], 0) + 1
    def cell(s): return html.escape(TAG.sub('', s.replace('{1A:FE0008}', '〈주〉'))).replace('\n', '<br>')
    trs = ''.join('<tr><td>%s</td><td class=id>%s<br><small>%s</small></td><td>%s</td><td class=b>%s</td><td class=a>%s</td></tr>' % (
        html.escape(r['why']), r['id'], r['batch'], cell(r['jp']), cell(r['before']), cell(r['after'])) for r in out)
    page = '''<!doctype html><html lang=ko><head><meta charset=utf-8><title>일괄 결정 대조표</title><style>
:root{--bg:#fff;--fg:#222;--line:#ccc;--b:#fde8e8;--a:#e6f6e6}
@media (prefers-color-scheme:dark){:root{--bg:#1c1c1c;--fg:#ddd;--line:#444;--b:#4a2626;--a:#24402a}}
body{background:var(--bg);color:var(--fg);font-family:"Malgun Gothic",sans-serif;margin:16px}
table{border-collapse:collapse;width:100%%}td,th{border:1px solid var(--line);padding:4px 6px;vertical-align:top;font-size:14px}
.b{background:var(--b)}.a{background:var(--a)}.id{white-space:nowrap}
</style></head><body><h1>7단계 결정 일괄 수정 대조표</h1><p>모두 %d건: %s. 아직 반영 안 함.</p>
<table><tr><th>결정</th><th>id</th><th>원문</th><th>지금</th><th>수정안</th></tr>%s</table></body></html>''' % (
        len(out), ' · '.join('%s %d' % kv for kv in cnt.items()), trs)
    open(os.path.join(disc.ROOT, 'docs/bulk-table.html'), 'w', encoding='utf-8').write(page)
    print(len(out), cnt)


if __name__ == '__main__':
    main()
