"""칸 넘침 수정안 검사: python -X utf8 tools/fit_check.py <수정안.json>

수정안 형식: {"fixes": [{"id": "...", "after": "...", "why": "..."}]}
manifests/ui-fit.json 의 한계(limit_px·limit_lines)와 같은 방식(글자 간격 3px, INFORMATION 창은 빌드처럼 다시 나눈 모양)으로 잰다.
제어 코드가 원문과 같은지, 게임 글꼴로 바꿀 수 있는지도 본다. 문제 있는 줄만 찍고 마지막에 합계.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import build, disc, kotext, measure

CODE = re.compile(r'\{1A:[0-9A-Fa-f]*\}|\{[0-9A-Fa-f]{2}\}|%[0-9]*[sd]')


def built(t, r):
    """빌드가 넣을 모양(INFORMATION 창 설명은 247px 로 다시 나눔)."""
    b = r['id'].split(':')[1] if r['id'].startswith('info') else ''
    if r['kind'] == 'info-N' and b in build.INFO_BLOCKS: t, _ = build.fit_info(t, r['jp_lines'])
    return t


def px(t, r=None):
    if r is not None: t = built(t, r)
    return measure.lines(t, korean=True, spacing=measure.UI_SPACING)


def main():
    lim = {r['id']: r for r in json.load(open(os.path.join(disc.ROOT, 'manifests/ui-fit.json'), encoding='utf-8'))}
    fixes = json.load(open(sys.argv[1], encoding='utf-8'))['fixes']
    bad = 0
    for f in fixes:
        r = lim[f['id']]; a = f['after']; p = []
        bt = built(a, r); w = px(bt); nl = bt.rstrip('\n').count('\n') + 1
        if max(w) > r['limit_px']: p.append('폭 %d > %d' % (max(w), r['limit_px']))
        if nl > r['limit_lines']: p.append('줄 %d > %d' % (nl, r['limit_lines']))
        if CODE.findall(a) != CODE.findall(r['ko']): p.append('제어 코드 다름')
        try: kotext.to_game(a)
        except ValueError as e: p.append(str(e))
        if p: bad += 1; print(f['id'], ' / '.join(p), repr(a))
    print('수정안', len(fixes), '문제', bad)


if __name__ == '__main__':
    main()
