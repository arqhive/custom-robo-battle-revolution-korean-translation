"""8단계 빌드: 번역·글꼴·main.dol·그림을 넣은 한국어 ISO 만들기.

넣는 것(분야마다 --no-<분야> 로 뺄 수 있다 — 9단계 회귀 점검용)
- text  : 시나리오 대사 /scenario_jp/snr_*.bmg(개발용 snr_f_25~30·snr_t_20 빼고), 상점·용어 SNT_TEST.bmg, /bmg/info.bin(크기 칸 갱신).
          후리가나(FF0002)는 번역문에 없으므로 빠진다. dup_of 항목은 앞 항목 번역을 쓴다.
          대사(line)는 쪽마다 370px·3줄에 맞춘다(아래 「대사 줄 맞추기」). 선택지(choice)는 번역 줄 그대로.
- font  : /message/font.out — G마켓 산스 Medium 고정 폭(10/30, 그전 맑은 고딕 Bold) 한글 2,350자 + 띄어쓰기 + 자모 51자(font_ko)
- dol   : sys/main.dol — 이름 입력판 한글 자모 조합(name_input_patch) + 파츠 이름 46개(dol-name, 제자리 덮어쓰기)
- gfx   : 그림 글씨 23장(work/graphics/ko — 통합 폴더 「커스텀로보 그림글씨 결과\\gc」 사본)
          mode_select.tpl 16장·name_entry.tpl 4장·title.tpl 1장 = C8, 원본 팔레트 그대로 칸 번호만 다시(결과 그림 색은 전부 원본 팔레트 안)
          snr_map.BIN 항목 9·56(受付), 32·79(한자 벽), 25·72(경찰서 화장실 KEEP CLEAN 간판) = CMPR 512×512, 바뀐 4×4 칸만 다시 인코딩
          빼는 것: 오프닝 영상 대사창(보류), 心技体(제외)
- sign  : 3D 지역 이름판 13종(11/13~) — 글자 메시를 G마켓 산스 Bold 한글 삼각형으로 바꿈(tools/sign3d.py).
          /scenario_jp/snr_obj.BIN 항목 54~66 과 사본 rpg_f_models·rpg_t_models 항목 0·1 (세 파일 모두)

대사 줄 맞추기(쪽 = {1A:FE0003xx} 사이)
  (폭은 글자 간격 5px 넣어 잼, 한 줄 448px — 아래 DLG_SP·WIN_PX)
  A. 번역 줄바꿈을 그대로 두고 448px 넘는 줄만 낱말 단위로 꺾는다 → 3줄 이하면 끝
     (11/14 사용자: 넘친 줄은 같은 문장 다음 줄과 이어 같은 줄 수로 고르게 나눔 — wrap_even. 끝 낱말 토막이 혼자 남지 않게)
  B. 문장 끝(. ! ? … 」 ） ~ 등)이 아닌 줄바꿈만 이어 붙여 다시 꺾는다 → 3줄 이하면 끝
  C. 쪽 안 줄바꿈을 모두 이어 다시 꺾는다 → 3줄 이하면 끝
  D. 그래도 넘치면 C 줄을 3줄씩 끊어 {1A:FE000301} 로 쪽을 나눈다(실기 확인 전)

    python tools/build.py --ver v0.1 [--no-text] [--no-font] [--no-dol] [--no-gfx] [--files-only]
    → build/files/…, build/main.dol, build/GXCJ01_KO_<ver>.iso, manifests/build-<ver>.json
"""
import argparse, json, os, re, shutil, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image
import bmg, disc, font_ko, info_bin, kotext, measure, sfd, tpl
import name_input_patch

T = os.path.join(disc.ROOT, 'work/translation')
OUT = os.path.join(disc.ROOT, 'build/files')
GFX = os.path.join(disc.ROOT, 'work/graphics/ko')   # 통합 폴더 결과\gc 사본(10/30)
DEV_FILES = {'snr_f_25', 'snr_f_26', 'snr_f_27', 'snr_f_28', 'snr_f_29', 'snr_f_30', 'snr_t_20'}
PAGE = re.compile(r'(\{1A:FE0003[0-9A-F]{2}\})')
TAG = re.compile(r'\{[^}]*\}')
SCALE = re.compile(r'\{1A:FF0001([0-9A-F]{4})\}')
SPLIT = '{1A:FE000301}'
# 대사창: 글자마다 약 5px 간격(10/30 실기 스샷: 한글 간격 72.7·띄어쓰기 35 → (22+5):(8+5)).
# 한 줄 최대 = 「면접, 합격해 주렴. 또 불합격이라는」(사용자 10/30) = 간격 넣어 448px. 그전(v0.3까지)은 간격 없이 370px.
DLG_SP = 5
WIN_PX, WIN_LINES = 448, 3
END = tuple('.!?…」』）)~〜♪')


# ---------------------------------------------------------------- 번역 읽기
def load():
    items, tr = {}, {}
    for f in os.listdir(os.path.join(T, 'batches')):        # 대괄호 경로라 glob 금지
        for x in json.load(open(os.path.join(T, 'batches', f), encoding='utf-8')): items[x['id']] = x
    # 11/13 다시 번역(redo, 묶음 파일만 — parts/ 는 조각). 같은 원문(dup_of)도 자리마다 따로 번역했으니 ID 번역을 먼저 쓰고, 없을 때만 짝을 따라간다
    rd = os.path.join(T, 'redo')
    for f in os.listdir(rd):
        if f.endswith('.json'):
            tr.update(json.load(open(os.path.join(rd, f), encoding='utf-8'))['translations'])
    ko = {}
    for k, x in items.items():
        r = k
        while r not in tr and 'dup_of' in items[r]: r = items[r]['dup_of']
        assert r in tr, ('번역 없음', k)
        ko[k] = tr[r]
    return items, ko


# ---------------------------------------------------------------- 대사 줄 맞추기
def width(s, scale, sp=0):
    s = s.replace(NBSP, ' ')
    return measure.lines('{1A:FF0001%04X}' % round(scale * 100) + s, korean=True, spacing=sp)[0]


NBSP = '\u00a0'   # 줄을 나누지 않을 띄어쓰기(정보창: 「할 수」처럼 의존 명사 앞)
BOUND = re.compile(r' (?=(수|것|줄|등|때|데|뿐|적|만큼)(?![가-힣]))')


def scale_after(s, scale):
    m = SCALE.findall(s)
    return int(m[-1], 16) / 100 if m else scale


def wrap(line, scale, px=WIN_PX, sp=DLG_SP):
    """한 줄 → px 안의 줄 목록(낱말 단위, 낱말 하나가 넘치면 글자 단위). sp = 글자 사이 간격."""
    WIN_PX = px
    if width(line, scale, sp) <= WIN_PX: return [line]
    out, cur, sc = [], '', scale
    for w in line.split(' '):
        c = cur + ' ' + w if cur else w
        if width(c, sc, sp) <= WIN_PX: cur = c; continue
        if cur:
            out.append(cur); sc = scale_after(cur, sc); cur = ''
        while width(w, sc, sp) > WIN_PX:                     # 낱말 하나가 창보다 길면 글자 단위(태그는 안 자름)
            toks = re.findall(r'\{[^}]*\}|.', w, re.S); head = ''
            for t in toks:
                if head and width(head + t, sc, sp) > WIN_PX: break
                head += t
            out.append(head); sc = scale_after(head, sc); w = w[len(head):]
        cur = w
    out.append(cur)
    return out


def wrap_all(lines, scale, px=WIN_PX, sp=DLG_SP):
    res, sc = [], scale
    for l in lines:
        for x in wrap(l, sc, px, sp):
            res.append(x); sc = scale_after(x, sc)
    return res


def ends_sentence(l):
    t = TAG.sub('', l).rstrip()
    return not t or t.endswith(END)


def fit_page(body, scale):
    """쪽 하나(끝 줄바꿈 뺀 것) → (새 본문, 방법). 「할 수」처럼 의존 명사 앞 띄어쓰기에서는 줄을 안 나눈다."""
    t, how = _fit_page(BOUND.sub(NBSP, body), scale)
    return t.replace(NBSP, ' '), how


def _fit_page(body, scale):
    lines = body.split('\n')
    blank = 0
    while len(lines) > 1 and not TAG.sub('', lines[-1]).strip() and lines[-1] == '':   # 끝 빈 줄은 줄 수에 안 셈(뒤에 그대로 붙임)
        lines.pop(); blank += 1
    t, how = _fit_lines(lines, scale)
    return t + '\n' * blank, how


# 고르게 나눌 때 이 말 바로 뒤에서는 줄을 안 나눈다(뒤 말을 꾸밈: 부정·정도 부사, 관형사, 수 관형사, 의성어)
NOBREAK_AFTER = set('안 못 잘 좀 더 덜 꼭 또 다 쌩 휙 확 쭉 꽉 딱 막 그 이 저 그런 이런 저런 그런데도 무슨 어느 어떤 웬 온 각 매 한 두 세 네 몇 여러 아주 너무 매우 제일 가장 정말 진짜 엄청 되게 아무 새 헌 옛 첫'.split())
NOBREAK_BEFORE = ('테니', '텐', '테야', '테고', '테지', '테다', '터라')   # 「할 테니까」처럼 앞말에 붙는 말
NOBREAK_WORD = set('건 걸 게 거 거야 거다 거지 거냐 거니 거고 거라 거든 거죠 거예요 겁니다 건데 거잖아'.split())   # 「차지한 건」처럼 의존 명사 것


def balanced(line, scale, n, px=None, sp=None):
    """한 줄을 낱말 단위로 n 줄에 나눔: 위 금지 자리 수 최소, 그다음 가장 긴 줄과 짧은 줄 차이 최소. 안 되면 None."""
    import itertools
    px = WIN_PX if px is None else px; sp = DLG_SP if sp is None else sp
    ws = line.split(' ')
    if len(ws) > 30 or len(ws) < n: return None
    best = None
    for cuts in itertools.combinations(range(1, len(ws)), n - 1):
        parts = [' '.join(ws[a:b]) for a, b in zip((0,) + cuts, cuts + (len(ws),))]
        wd, sc = [], scale
        for p in parts:
            wd.append(width(p, sc, sp)); sc = scale_after(p, sc)
        if max(wd) > px: continue
        bad = sum(TAG.sub('', p).split(' ')[-1] in NOBREAK_AFTER for p in parts[:-1])
        bad += sum(TAG.sub('', p).startswith(NOBREAK_BEFORE) or TAG.sub('', p).split(' ')[0].rstrip('.,!?…~') in NOBREAK_WORD for p in parts[1:])
        key = (bad, max(wd) - min(wd))
        if best is None or key < best[0]: best = (key, parts)
    return best[1] if best else None


def wrap_even(lines, scale):
    """A꺾음 대신(사용자 11/14): 넘친 줄을 같은 문장의 다음 줄들과 이어 붙여, 꺾었을 때와 같은 줄 수로 고르게 다시 나눈다.
    끝 낱말만 다음 줄로 넘어가 「오든가」처럼 짧은 토막이 혼자 남는 것을 막는다. 넘치지 않는 줄은 그대로."""
    out, i, sc = [], 0, scale
    while i < len(lines):
        l = lines[i]
        if width(l, sc, DLG_SP) <= WIN_PX:
            out.append(l); sc = scale_after(l, sc); i += 1; continue
        grp, j = l, i + 1
        while not ends_sentence(grp) and j < len(lines):
            grp = grp.rstrip() + ' ' + lines[j].lstrip(); j += 1
        w = wrap(grp, sc)
        out += balanced(grp, sc, len(w)) or w
        sc = scale_after(grp, sc); i = j
    return out


def _fit_lines(lines, scale):
    a = wrap_all(lines, scale)
    if a == lines: return '\n'.join(a), 'A'
    if len(a) <= WIN_LINES:
        e = wrap_even(lines, scale)
        return '\n'.join(e if len(e) <= WIN_LINES else a), 'A꺾음'
    merged = [lines[0]]
    for l in lines[1:]:
        if ends_sentence(merged[-1]): merged.append(l)
        else: merged[-1] = merged[-1].rstrip() + ' ' + l.lstrip()
    b = wrap_all(merged, scale)
    if len(b) <= WIN_LINES: return '\n'.join(b), 'B'
    c = wrap_all([' '.join(l.strip() for l in lines)], scale)
    if len(c) <= WIN_LINES: return '\n'.join(c), 'C'
    best = min((b, c, a), key=lambda x: -(-len(x) // WIN_LINES))      # 쪽 수가 가장 적은 것(같으면 B → C → A: A 는 꺾인 짧은 토막이 남기 쉬움)
    return SPLIT.join('\n'.join(pg) for pg in split_pages(best)), 'D'


def split_pages(lines):
    """줄 목록 → 쪽(3줄 이하) 목록. 쪽 수 최소, 그다음 쪽 끝이 문장 끝(. ! ? …)>쉼표>그 밖, 그다음 쪽마다 줄 수 고르게."""
    def cut(l):
        t = TAG.sub('', l).rstrip()
        return 0 if t.endswith(END) else 1 if t.endswith((',', '，', '、')) else 3
    n = len(lines); INF = (10 ** 9, 0.0)
    dp = [INF] * (n + 1); back = [0] * (n + 1); dp[0] = (0, 0.0)
    for i in range(1, n + 1):
        for k in range(1, WIN_LINES + 1):
            if i - k < 0 or dp[i - k] == INF: continue
            c = (dp[i - k][0] + 1, dp[i - k][1] + (cut(lines[i - 1]) if i < n else 0) + 0.2 * (WIN_LINES - k) ** 2)
            if c < dp[i]: dp[i] = c; back[i] = i - k
    out, i = [], n
    while i: out.append(lines[back[i]:i]); i = back[i]
    return out[::-1]


def fit_message(ko):
    parts = PAGE.split(ko); out = []; how = []; sc = 1.0
    for p in parts:
        if PAGE.fullmatch(p) or not p.strip('\n'):
            out.append(p); continue
        tail = '\n' if p.endswith('\n') else ''
        body, h = fit_page(p[:len(p) - len(tail)], sc)
        out.append(body + tail); how.append(h); sc = scale_after(p, sc)
    return ''.join(out), how


# ---------------------------------------------------------------- 정보창 줄 맞추기
# 메뉴 오른쪽 INFORMATION 창(info.bin 여러 줄 설명). 사용자 10/30: 한 줄 최대는 「마을의 치안을 지키는」(글자 간격 3px 포함 247px).
# 번역 줄바꿈이 원문처럼 짧게 끊겨 있어 대사처럼 B(문장 끝 아닌 줄바꿈 잇기)·C(모두 잇기)로 다시 나눈다.
# 07 블록에는 MENU 창 질문(전체 데이터 삭제 등)도 섞여 있어 줄 수는 원문 줄 수를 넘지 않게 한다.
INFO_BLOCKS = {'01', '03', '05', '06', '07', '08', '10', '27'}
INFO_PX = 247
# 사용자가 줄바꿈·정렬을 직접 정한 정보창 설명: fit_info 로 다시 나누지 않고 그대로 넣는다(줄마다 INFO_PX 안인지만 검사).
INFO_KEEP = {
    'info:07:009',   # 11/13 사용자 지정 줄바꿈 + 빈 줄 + ON/OFF 「…」 정렬
    'info:07:008',   # 11/13 진동: 설명 뒤 빈 줄 + ON/OFF 「…」 정렬
    'info:07:013',   # 11/15 로보 시선(C스틱): ON/OFF 「…」 정렬(fit_info 가 얇은 빈칸을 띄어쓰기로 바꿔서), 줄바꿈은 v0.29 화면과 같음
    'info:07:010',   # 11/13 사운드 설정 설명 사용자 지정 줄바꿈
    'info:06:005',   # 11/13 시나리오 모드 설명 사용자 지정 줄바꿈(「1인 플레이 전용.」)
    'info:06:008',   # 11/13 옵션 설명 사용자 지정 줄바꿈
    'info:07:011',   # 11/13 키 설정 설명 사용자 지정 줄바꿈
    'info:07:012',   # 11/13 대전 성적표 설명 사용자 지정 문장·줄바꿈
    'info:07:015',   # 11/13 전체 데이터 삭제 설명 사용자 지정 문장·줄바꿈
    'info:10:030',   # 11/13 「메뉴를 닫고」 뒤 줄바꿈 유지(자동으로 나누면 「시나리오」가 윗줄로 올라감)
}


# 블록마다 다른 창(11/14 사용자 실기 스샷, 창에 딱 맞게 자른 그림으로 잼):
# 01 = 홀로세움(스테이지) 설명창. 글자 75%(FF0001004B), 스샷 2.81배, 글자 시작 41px~창 끝 584px → 193px.
# 원문 최대 줄도 75%로 181.5px(10자). 247 로 나누면 「로보 배틀의 기본이 되는」(212px) 이 창 밖으로 잘렸다(v0.16).
INFO_PX_BLOCK = {'01': 193}
# 같은 창의 원문 최대 줄 수(01 은 7줄 항목이 있음) — 항목 원문 줄 수보다 길어도 이 안이면 됨
# (11/15 사용자: 이 창은 가로는 고정, 세로는 줄 수만큼 늘어남)
INFO_LINES_BLOCK = {'01': 7}


# 사용자가 줄바꿈을 직접 넣은 설명(11/14~ parts 직접 수정): 넣은 줄바꿈은 그대로 두고 창보다 긴 줄만 낱말 단위로 더 나눈다
# (fit_info 의 B 는 문장 끝 아닌 줄바꿈을 이어 붙여 사용자 줄바꿈이 사라짐). 「커빌」 때 사용자 수정 diff 를 보고 추가.
INFO_HARD = {
    'info:05:006', 'info:05:007', 'info:05:009', 'info:05:010', 'info:05:011',
    'info:08:026', 'info:08:030', 'info:08:031', 'info:08:034', 'info:08:037', 'info:08:041',
    # 11/15 v0.30 사용자 줄바꿈(대전 모드 규칙 설명)
    'info:08:020', 'info:08:024', 'info:08:025', 'info:08:029', 'info:08:032', 'info:08:033',
    'info:08:035', 'info:08:036', 'info:08:038', 'info:08:039', 'info:08:040',
}


def info_hard_wrap(t, px):
    """사용자 줄바꿈 그대로, 창보다 긴 줄만 같은 줄 수로 고르게(끝 낱말 토막 방지)."""
    out, sc, sp = [], 1.0, measure.UI_SPACING
    for l in t.split('\n'):
        l = BOUND.sub(NBSP, l)
        w = wrap(l, sc, px, sp)
        out += (balanced(l, sc, len(w), px, sp) or w) if len(w) > 1 else w
        sc = scale_after(l, sc)
    return out


def fit_info(ko, jp_lines, px=None):
    """여러 줄 설명 → (새 문장, 방법). 원문 줄 수 안에서 px(기본 247, 간격 포함)에 맞춘다. 못 맞추면 그대로."""
    global INFO_PX
    if px is not None:
        old = INFO_PX; INFO_PX = px
        try: return fit_info(ko, jp_lines)
        finally: INFO_PX = old
    tail = '\n' if ko.endswith('\n') else ''
    lines = ko[:len(ko) - len(tail)].split('\n')
    sp = measure.UI_SPACING
    merged = [lines[0]]
    for l in lines[1:]:
        if ends_sentence(merged[-1]) or re.match(r'(ON|OFF|・|[0-9０-９]+[:：.])', TAG.sub('', l)): merged.append(l)
        else: merged[-1] = merged[-1].rstrip() + ' ' + l.lstrip()
    merged = [BOUND.sub(NBSP, l) for l in merged]
    b = [l.replace(NBSP, ' ') for l in wrap_all(merged, 1.0, INFO_PX, sp)]
    if len(b) <= jp_lines: return '\n'.join(b) + tail, 'B'
    a = wrap_all(lines, 1.0, INFO_PX, sp)
    if len(a) <= jp_lines: return '\n'.join(a) + tail, 'A'
    return ko, '넘침'


def write(path, data):
    p = os.path.join(OUT, path.lstrip('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(data)


def build_text(items, ko, rep):
    by_file = {}
    for k, x in items.items():
        if x['src'].endswith('.bmg'): by_file.setdefault(x['src'], []).append(k)
    stat = {}; splits = []; choice_wide = []
    for src, ids in sorted(by_file.items()):
        f = os.path.basename(src)[:-4]
        if f in DEV_FILES: continue
        b = bmg.read(disc.read(src)); ents = b['inf']['entries']
        for k in ids:
            x = items[k]; t = ko[k]; n = int(k.split(':')[1])
            if x['kind'] == 'line':
                t, how = fit_message(t)
                for h in how: stat[h] = stat.get(h, 0) + 1
                if 'D' in how: splits.append(k)
            elif x['kind'] == 'choice':
                if any(w > WIN_PX for w in measure.lines(t, korean=True, spacing=DLG_SP)): choice_wide.append(k)
            ents[n]['text'] = kotext.to_game(t)
        write(src, bmg.write(b)); rep['files'].append(src)
    info = info_bin.split(disc.read('/bmg/info.bin')); n_info = 0; info_how = {}; info_over = []
    for k, x in items.items():
        if x['src'] != '/bmg/info.bin': continue
        _, bi, no = k.split(':'); t = ko[k]
        if k in INFO_KEEP:
            wide = [l for l in t.split('\n') if width(l, 1.0, measure.UI_SPACING) > INFO_PX]
            h = '그대로' if not wide else '넘침'
            info_how[h] = info_how.get(h, 0) + 1
            if wide: info_over.append(k)
        elif k in INFO_HARD:
            tail = '\n' if t.endswith('\n') else ''
            px = INFO_PX_BLOCK.get(bi, INFO_PX)
            t = '\n'.join(l.replace(NBSP, ' ') for l in info_hard_wrap(t[:len(t) - len(tail)], px)) + tail
            n_lim = max(x['jp'].rstrip('\n').count('\n') + 1, INFO_LINES_BLOCK.get(bi, 0))
            h = '사용자줄' if t.rstrip('\n').count('\n') + 1 <= n_lim else '넘침'
            info_how[h] = info_how.get(h, 0) + 1
            if h == '넘침': info_over.append(k)
        elif x['kind'] == 'info-N' and bi in INFO_BLOCKS:
            t, h = fit_info(t, max(x['jp'].rstrip('\n').count('\n') + 1, INFO_LINES_BLOCK.get(bi, 0)), INFO_PX_BLOCK.get(bi))
            info_how[h] = info_how.get(h, 0) + 1
            if h == '넘침': info_over.append(k)
        info['blocks'][int(bi)]['inf']['entries'][int(no)]['text'] = kotext.to_game(t); n_info += 1
    write('/bmg/info.bin', info_bin.join(info)); rep['files'].append('/bmg/info.bin')
    rep['text'] = {'dialogue_pages': stat, 'page_split_ids': splits, 'choice_over_370': choice_wide, 'info_items': n_info,
                   'info_panel': info_how, 'info_panel_over': info_over}
    print('정보창 줄 맞춤', info_how, '넘침', info_over)
    print('대사 쪽 맞춤', stat, '쪽 나눔', len(splits), '선택지 370px 넘음', choice_wide, 'info', n_info)


# ---------------------------------------------------------------- main.dol
def build_dol(items, ko, rep, namein=True):
    dol = disc.read('sys/main.dol')
    if namein: dol, _ = name_input_patch.patch(dol)
    dol = bytearray(dol)
    slots = {x['id']: x for x in json.load(open(os.path.join(T, 'dol-jp.json'), encoding='utf-8'))}
    n = 0
    for k, x in items.items():
        if x['kind'] != 'dol-name': continue
        s = slots[k]; o, slot = s['off'], s['slot']
        assert dol[o:o + s['len']].decode('cp932') == x['jp'], k
        new = kotext.to_game(ko[k]).encode('cp932')
        assert len(new) < slot, ('칸 넘침', k, ko[k], len(new), slot)
        dol[o:o + slot] = new + bytes(slot - len(new)); n += 1
    p = os.path.join(disc.ROOT, 'build/main.dol')
    open(p, 'wb').write(dol)
    rep['dol'] = {'size': len(dol), 'names': n, 'name_input': namein}
    print('main.dol', len(dol), '파츠 이름', n, '이름 입력 패치', namein)
    return p


# ---------------------------------------------------------------- 그림
def c8_put(d, info, im):
    """C8 그림을 원본 팔레트 칸 번호로 다시 쓴다(바뀐 픽셀만)."""
    pn, pf, po = info['pal']
    conv = {0: tpl.cia8, 1: tpl.c565, 2: tpl.c5a3}[pf]
    pal = [conv(struct.unpack_from('>H', d, po + 2 * i)[0]) for i in range(pn)]
    first = {}
    for i, c in enumerate(pal): first.setdefault(c, i)
    w, h, off = info['w'], info['h'], info['off']
    W = (w + 7) // 8 * 8
    px = im.load(); changed = 0
    for y in range(h):
        for x in range(w):
            bi = (y // 4) * (W // 8) + x // 8
            o = off + bi * 32 + (y % 4) * 8 + (x % 8)
            c = px[x, y]
            if pal[d[o]] == c: continue
            if c not in first: raise ValueError('팔레트에 없는 색 %r' % (c,))
            d[o] = first[c]; changed += 1
    return changed


def cmpr_block(px16):
    """4×4 RGB 16개 → CMPR 8바이트(색 쌍 후보를 다 맞춰 보고 오차 가장 작은 것)."""
    def q(c): return ((c[0] >> 3) << 11) | ((c[1] >> 2) << 5) | (c[2] >> 3)
    cands = sorted({q(c) for c in px16})
    best = None
    pairs = [(a, b) for a in cands for b in cands if a > b] or [(cands[0], cands[0])]
    for a, b in pairs:
        A, B = sfd.c565(a)[:3], sfd.c565(b)[:3]
        if a > b:
            cs = [A, B, tuple((2 * A[i] + B[i]) // 3 for i in range(3)), tuple((A[i] + 2 * B[i]) // 3 for i in range(3))]
        else:
            cs = [A, B, tuple((A[i] + B[i]) // 2 for i in range(3)), A]
        err = 0; idx = []
        for c in px16:
            e = [sum((c[i] - k[i]) ** 2 for i in range(3)) for k in cs]
            j = e.index(min(e)); idx.append(j); err += e[j]
        if best is None or err < best[0]: best = (err, a, b, idx)
    _, a, b, idx = best
    bits = 0
    for j in idx: bits = (bits << 2) | j
    return struct.pack('>HHI', a, b, bits)


def cmpr_put(data, w, h, old, new):
    """CMPR 데이터에서 그림이 바뀐 4×4 칸만 다시 인코딩."""
    d = bytearray(data); po, pn = old.load(), new.load(); n = 0; p = 0
    for by in range(0, h, 8):
        for bx in range(0, w, 8):
            for s in range(4):
                sx, sy = bx + (s & 1) * 4, by + (s >> 1) * 4
                blk = [pn[sx + i % 4, sy + i // 4][:3] for i in range(16)]
                if any(po[sx + i % 4, sy + i // 4][:3] != blk[i] for i in range(16)):
                    d[p:p + 8] = cmpr_block(blk); n += 1
                p += 8
    return bytes(d), n


def build_gfx(rep):
    g = rep['gfx'] = {}
    for name, idx in (('mode_select', [11, 12, 13, 32, 50, 54, 55, 66, 67, 68, 69, 70, 72, 83, 84, 85]),
                      ('name_entry', [10, 15, 17, 23]), ('title', [1])):
        path = '/sprite/%s.tpl' % name
        d = bytearray(disc.read(path)); ents = tpl.entries(d)
        for i in idx:
            im = Image.open(os.path.join(GFX, '%s_%02d.png' % (name, i))).convert('RGBA')
            assert im.size == (ents[i]['w'], ents[i]['h']), (name, i)
            g['%s_%02d' % (name, i)] = c8_put(d, ents[i], im)
        for (got, info), i in zip(tpl.decode(bytes(d)), range(len(ents))):     # 다시 풀어 결과 그림과 같은지
            if i in idx:
                want = Image.open(os.path.join(GFX, '%s_%02d.png' % (name, i))).convert('RGBA')
                assert got.tobytes() == want.tobytes(), ('C8 불일치', name, i)
        write(path, bytes(d)); rep['files'].append(path)
    path = '/scenario_jp/snr_map.BIN'
    ents = sfd.unpack(disc.read(path)); ents = [bytearray(e) for e in ents]
    for png, items in (('snr_map_e09_uketsuke_jp', (9, 56)), ('snr_map_e32_kanji_wall_jp', (32, 79)),
                       ('snr_map_e25_keepclean_jp', (25, 72))):   # 경찰서 화장실 KEEP CLEAN 간판(11/15)
        new = Image.open(os.path.join(GFX, png + '.png')).convert('RGB')
        for i in items:
            hits = 0
            for b, kind, boff in sfd.blobs(bytes(ents[i])):
                base = 0x20 if kind == 'hsd' else 0x40
                for ptr in sorted({t['ptr'] for t in sfd.textures(b, kind, want_image=False) if t['fmt'] == 14 and t['w'] == 512 and t['h'] == 512}):
                    o = boff + base + ptr; size = sfd.tex_size(512, 512, 14)
                    old = sfd.decode(bytes(ents[i][o:o + size]), 512, 512, 14).convert('RGB')
                    if sum(a != c for a, c in zip(old.tobytes()[::3], new.tobytes()[::3])) > 0.05 * 512 * 512: continue
                    data, n = cmpr_put(bytes(ents[i][o:o + size]), 512, 512, old, new)
                    ents[i][o:o + size] = data; hits += 1
                    got = sfd.decode(data, 512, 512, 14).convert('RGB')
                    diff = [abs(a - c) for a, c in zip(got.tobytes(), new.tobytes())]
                    g['snr_map_%d_%x' % (i, ptr)] = {'blocks': n, 'max_err': max(diff), 'mean_err': round(sum(diff) / len(diff), 3)}
            assert hits == 1, (png, i, hits)
    data = sfd.pack([bytes(e) for e in ents])
    write(path, data); rep['files'].append(path)
    print('그림', g)


# ---------------------------------------------------------------- 본체
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ver', required=True)
    for k in ('text', 'font', 'dol', 'namein', 'gfx', 'sign'): ap.add_argument('--no-' + k, action='store_true')
    ap.add_argument('--files-only', action='store_true')
    a = ap.parse_args()
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(OUT)
    rep = {'ver': a.ver, 'files': [], 'parts': [k for k in ('text', 'font', 'dol', 'gfx', 'sign') if not getattr(a, 'no_' + k)]}
    items, ko = load()
    if not a.no_text: build_text(items, ko, rep)
    if not a.no_font:
        buf, _, _, n = font_ko.build(os.path.join(disc.ROOT, font_ko.FONT), font_ko.SIZE)
        write('/message/font.out', bytes(buf)); rep['files'].append('/message/font.out'); rep['font'] = n
        print('글꼴', n, '자')
    dol = None
    if not a.no_dol: dol = build_dol(items, ko, rep, namein=not a.no_namein)
    if not a.no_gfx: build_gfx(rep)
    if not a.no_sign:
        import sign3d
        files, slog = sign3d.patch_all(disc.read)
        for p, data in files.items():
            assert not os.path.exists(os.path.join(OUT, p.lstrip('/'))), ('이름판 파일을 다른 분야가 이미 바꿈', p)
            write(p, data); rep['files'].append(p)
        # main.dol 안에 SFD 목차 사본(「u32 개수, u32 0」 + (위치, 크기)×개수)이 있어 게임은 그걸로 읽는다(11/13 v0.13 에서
        # 이걸 안 고쳐 HSD 재배치 중 Invalid read 로 멈춤). 바뀐 SFD 마다 원래 목차를 찾아(정확히 1번) 새 목차로 바꾼다.
        dp = dol or os.path.join(disc.ROOT, 'build/main.dol')
        dbytes = bytearray(open(dol, 'rb').read() if dol else disc.read('sys/main.dol'))
        for p, data in files.items():
            old = disc.read(p); n = struct.unpack('>I', old[4:8])[0]
            assert struct.unpack('>I', data[4:8])[0] == n
            ot, nt = old[8:8 + 8 * n], data[8:8 + 8 * n]
            assert bytes(dbytes).count(ot) == 1, ('main.dol 목차 사본을 하나로 못 찾음', p)
            i = bytes(dbytes).find(ot)
            assert dbytes[i - 8:i] == struct.pack('>II', n, 0)
            dbytes[i:i + 8 * n] = nt
        open(dp, 'wb').write(dbytes); dol = dp
        rep['sign'] = {sign3d.SIGNS[k]: v for k, v in slog.items()}
        print('이름판', len(slog), '종 →', list(files))
    json.dump(rep, open(os.path.join(disc.ROOT, 'manifests/build-%s.json' % a.ver), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.files_only: return
    dst = os.path.join(disc.ROOT, 'build/GXCJ01_KO_%s.iso' % a.ver)
    cmd = [sys.executable, os.path.join(disc.ROOT, 'tools/build_iso.py'), disc.ISO, dst, '--repdir', OUT]
    if dol: cmd += ['--dol', dol]
    subprocess.run(cmd, check=True)
    print('ISO', dst)


if __name__ == '__main__':
    main()
