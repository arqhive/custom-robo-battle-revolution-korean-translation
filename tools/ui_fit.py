"""메뉴·설명 칸 넘침 엄격 검사 → manifests/ui-fit.json

10/30 실기에서 info 항목이 칸을 넘거나(「데이터를 로드하시겠습니까?」), 줄이 늘어 아래 칸과 겹치는(「정말로 / 전체 데이터를 / 지우시겠습니까?」) 것이 나왔다.
windows.py 의 묶음 한계(블록 안 원문 최대 폭)는 한 블록에 여러 화면 칸이 섞여 너무 느슨했다.
여기서는 항목마다 **그 항목 원문 자기 폭·자기 줄 수**를 한계로 본다(원문이 그 칸에 들어간다는 것만 확실하므로).
예외(한 화면 칸에 같은 종류만 나오는 곳은 묶음 한계 = 칸에서 가장 긴 원문):
- 파츠 설명(info:00 여러 줄), 규칙·용어·격투 편 도움말(info:12·13·14 여러 줄)
- 이름 칸: 화자·대회 이름(name, info:15), 로보·파츠 이름(info:09 한 줄, dol-name)
폭은 메뉴·정보창 글자 간격(measure.UI_SPACING 3px)을 넣어 원문·번역 모두 같은 방식으로 잰다(10/30 실기 스샷 측정).
INFORMATION 창 설명(build.INFO_BLOCKS 여러 줄)은 빌드가 247px 로 다시 나눈 결과를 원문 줄 수와 비교한다.

대상: info.bin(info-1·info-N·name), main.dol 파츠 이름(dol-name). SNT_TEST(자동 줄넘김 추정)는 뺀다.
    python tools/ui_fit.py      # 블록별 개수 출력
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build, disc, measure

PANEL = {'00', '12', '13', '14'}
LIM = json.load(open(os.path.join(disc.ROOT, 'manifests/window-limits.json'), encoding='utf-8'))


def group_px():
    """묶음 한계를 글자 간격 넣어 다시 잰다(window-limits.json 은 간격 없는 값)."""
    import windows
    org = windows.originals(); g = {}
    for i, t in org.items():
        if not t.strip(): continue
        k = windows.group(i, t)
        for pg in windows.pages(t):
            g[k] = max(g.get(k, 0), max(measure.lines(pg, spacing=measure.UI_SPACING)))
    return g


def main():
    global GROUP
    GROUP = group_px()
    items, ko = build.load()
    rows = []
    for k in sorted(items):
        x = items[k]
        if x['kind'] not in ('info-1', 'info-N', 'name', 'dol-name'): continue
        sp = measure.UI_SPACING
        b = k.split(':')[1] if k.startswith('info') else ''
        t = ko[k]
        if x['kind'] == 'info-N' and b in build.INFO_BLOCKS:
            t, _ = build.fit_info(t, x['jp'].rstrip('\n').count('\n') + 1)
        jw = measure.lines(x['jp'], spacing=sp); kw = measure.lines(t, korean=True, spacing=sp)
        jl = x['jp'].rstrip('\n').count('\n') + 1; kl = t.rstrip('\n').count('\n') + 1
        lim_px, lim_ln = max(jw), jl
        if x['kind'] == 'info-N' and b in build.INFO_BLOCKS: lim_px = build.INFO_PX
        g = None
        if x['kind'] == 'info-N' and b in PANEL: g = 'info:%s:N' % b
        elif x['kind'] == 'name': g = 'info:15:1'
        elif x['kind'] == 'dol-name' or (x['kind'] == 'info-1' and b == '09'): g = 'info:09:1'
        if g: lim_px = max(lim_px, GROUP[g]); lim_ln = max(lim_ln, LIM[g]['lines'])
        over = round(max(kw) - lim_px)
        if over > 0 or kl > lim_ln:
            rows.append({'id': k, 'kind': x['kind'], 'jp': x['jp'], 'ko': ko[k], 'ko_built': t, 'jp_px': round(max(jw)), 'ko_px': round(max(kw)),
                         'over_px': over, 'limit_px': round(lim_px), 'jp_lines': jl, 'limit_lines': lim_ln, 'ko_lines': kl})
    json.dump(rows, open(os.path.join(disc.ROOT, 'manifests/ui-fit.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    by = {}
    for r in rows:
        b = r['id'].split(':')[1] if r['id'].startswith('info') else 'dol'
        t = by.setdefault(b, [0, 0]); t[0] += r['over_px'] > 0; t[1] += r['ko_lines'] > r['limit_lines']
    print('넘침 항목', len(rows))
    for b, (w, l) in sorted(by.items()): print('  블록 %s: 폭 %d, 줄 %d' % (b, w, l))


if __name__ == '__main__':
    main()
