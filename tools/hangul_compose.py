"""이름 입력판 한글 자모 조합 — 기준 구현(파이썬)과 표.

docs/name-input.md 4-3 절 규칙(사용자 결정 10/29)을 그대로 옮긴 것이다. PowerPC 루틴
(tools/name_input_patch.py)은 이 파일과 바이트 단위로 같게 동작해야 한다(검증 work/survey/namein_verify.py).

- 이름 버퍼 = SJIS 2바이트 코드 목록(최대 8글자). 상태 없이 마지막 두 글자만 보고 조합한다.
- 코드 ↔ 순번 i: 한글 음절 0~2349(KS X 1001 2,350자, 0x889F~), 띄어쓰기 2350(0x9540),
  호환 자모 2351~2401(0x9541~0x9573, ㄱ~ㅣ = U+3131~U+3163). 표 없이 계산한다.
- insert(buf, k): 자모 k(0~50, 0~29 자음·30~50 모음)를 넣는다 → (새 버퍼, 성공 여부).
- delete(buf): 판 0 의 B. 마지막 글자가 음절이면 자모 한 단계 지움, 아니면 글자 통째로.

    python tools/hangul_compose.py          # 단위 시험 + 무작위 대조
"""
import random, sys

MAX = 8
NSYL = 2350
SPACE_N = 2350
JAMO_N = 2351          # 자모 k 의 순번 = 2351 + k
JAMO_CODE = 0x9541

COMPAT = [chr(0x3131 + k) for k in range(51)]   # ㄱ … ㅣ
CONS = COMPAT[:30]
VOWS = COMPAT[30:]
CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG = ['', *'ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ']
JONG_PAIR = {'ㄳ': 'ㄱㅅ', 'ㄵ': 'ㄴㅈ', 'ㄶ': 'ㄴㅎ', 'ㄺ': 'ㄹㄱ', 'ㄻ': 'ㄹㅁ', 'ㄼ': 'ㄹㅂ',
             'ㄽ': 'ㄹㅅ', 'ㄾ': 'ㄹㅌ', 'ㄿ': 'ㄹㅍ', 'ㅀ': 'ㄹㅎ', 'ㅄ': 'ㅂㅅ'}
JUNG_PAIR = {'ㅘ': 'ㅗㅏ', 'ㅙ': 'ㅗㅐ', 'ㅚ': 'ㅗㅣ', 'ㅝ': 'ㅜㅓ', 'ㅞ': 'ㅜㅔ', 'ㅟ': 'ㅜㅣ', 'ㅢ': 'ㅡㅣ'}
assert ''.join(VOWS) == JUNG


def ks_hangul():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            out.append(bytes([hi, lo]).decode('euc-kr'))
    assert len(out) == NSYL
    return out


KS = ks_hangul()
# 음절표: 순번 i → 유니코드 오프셋 u = (초·21 + 중)·28 + 종. KS 순서 = 유니코드 순서(오름차순).
SYL = [ord(h) - 0xAC00 for h in KS]
assert SYL == sorted(SYL)
SYL_INDEX = {u: i for i, u in enumerate(SYL)}

# 자모 표(바이트). 루틴도 같은 표를 쓴다.
CHO_OF = bytes(CHO.index(c) if c in CHO else 0xFF for c in CONS)          # 자음 k → 초성 번호
JONG_OF = bytes(JONG.index(c) if c in JONG else 0 for c in CONS)          # 자음 k → 종성 번호(0 = 받침 불가)
CHO2K = bytes(COMPAT.index(c) for c in CHO)                                # 초성 → k
JONG2K = bytes([0] + [COMPAT.index(c) for c in JONG[1:]])                  # 종성 → k
JS1 = bytes(JONG.index(JONG_PAIR[j][0]) if j in JONG_PAIR else 0 for j in JONG)      # 겹받침 → 앞 받침
JS2 = bytes(COMPAT.index(JONG_PAIR[j][1]) if j in JONG_PAIR else 0 for j in JONG)    # 겹받침 → 뒤 자음 k
VS1 = bytes(JUNG.index(JUNG_PAIR[v][0]) if v in JUNG_PAIR else 0xFF for v in JUNG)   # 겹모음 → 앞 모음
VS2 = bytes(JUNG.index(JUNG_PAIR[v][1]) if v in JUNG_PAIR else 0xFF for v in JUNG)   # 겹모음 → 뒤 모음
# 받침을 다음 글자로 넘길 때 그 자음은 늘 초성이 될 수 있어야 한다
assert all(CHO_OF[JONG2K[t]] != 0xFF for t in range(1, 28) if not JS1[t])
assert all(CHO_OF[JS2[t]] != 0xFF for t in range(1, 28) if JS1[t])


# 판 0 에 있는 자모(배치안 A): 자음 19(겹받침 낱자 없음) + 모음 21(겹모음 포함)
BOARD_KEYS = [k for k in range(51) if k >= 30 or CHO_OF[k] != 0xFF]
assert len(BOARD_KEYS) == 40


# ---- 코드 ↔ 순번 (표 없이 계산) ----
def code2n(code):
    lead, trail = code >> 8, code & 0xFF
    if not (0x88 <= lead <= 0x95) or trail < 0x40 or trail == 0x7F or trail > 0xFC:
        return -1
    i = (lead - 0x88) * 188 + (trail - 0x40 - (trail > 0x7F)) - 94
    return i if i >= 0 else -1


def n2code(i):
    n = i + 94
    t = n % 188
    return (0x88 + n // 188) << 8 | (0x40 + t + (t >= 0x3F))


def is_syl(i): return 0 <= i < NSYL
def is_cons(i): return JAMO_N <= i < JAMO_N + 30
def is_vow(i): return JAMO_N + 30 <= i < JAMO_N + 51


def lvt(i):
    u = SYL[i]
    return u // 588, u // 28 % 21, u % 28


def mksyl(l, v, t):
    return SYL_INDEX.get((l * 21 + v) * 28 + t, -1)


def jdouble(t, k):
    for t2 in range(1, 28):
        if JS1[t2] == t and JS2[t2] == k: return t2
    return 0


def vdouble(v, w):
    for x in range(21):
        if VS1[x] == v and VS2[x] == w: return x
    return -1


# ---- 조합 ----
def virtual(Q, P):
    """P = 낱자 모음. Q·P 가 유니코드라면 합쳐졌을 텐데 KS 에 없어 떨어져 있는 꼴이면 그 (초,중,종) 목록(1~2개).
    Q 자음 낱자 → [(초,P,0)] / Q 받침 없는 음절 + 겹모음 됨 → [(초,겹모음,0)] / Q 받침 음절 → [(받침 뗀 Q), (받침,P,0)]."""
    v = P - JAMO_N - 30
    if is_cons(Q):
        c = CHO_OF[Q - JAMO_N]
        return [[c, v, 0]] if c != 0xFF else None
    if is_syl(Q):
        L, V, T = lvt(Q)
        if T == 0:
            dv = vdouble(V, v)
            return [[L, dv, 0]] if dv >= 0 else None
        if JS1[T]: t1, mk = JS1[T], JS2[T]
        else: t1, mk = 0, JONG2K[T]
        return [[L, V, t1], [CHO_OF[mk], v, 0]]
    return None


def lookback_put(b, n, vs):
    """마지막 두 칸(Q·P)을 vs 음절들로 바꾼다(모두 KS 에 있을 때만). 글자 수는 같거나 1 줄어든다."""
    ss = [mksyl(*x) for x in vs]
    if min(ss) < 0: return False
    b[n - 2:] = [n2code(x) for x in ss]
    return True


def insert(buf, k):
    """buf: 코드 목록, k: 자모 0~50. → (새 목록, 성공). 실패면 버퍼 그대로(오류음)."""
    b = list(buf); n = len(b)
    P = code2n(b[-1]) if n >= 1 else -1
    Q = code2n(b[-2]) if n >= 2 else -1

    def put(pos, i):
        if pos == len(b): b.append(n2code(i))
        else: b[pos] = n2code(i)

    if k < 30:                                     # 자음
        if is_syl(P):
            L, V, T = lvt(P)
            jt = JONG_OF[k] if T == 0 else jdouble(T, k)
            if jt:
                s = mksyl(L, V, jt)
                if s >= 0: put(n - 1, s); return b, True
        elif is_vow(P):                            # 2글자 되돌아보기(ㅆㅑ+ㅇ → 썅, 로ㅐ+ㅆ → 뢨)
            vs = virtual(Q, P); jt = JONG_OF[k]
            if vs and jt:
                vs[-1][2] = jt
                if lookback_put(b, n, vs): return b, True
    else:                                          # 모음
        v = k - 30
        if is_syl(P):
            L, V, T = lvt(P)
            if T == 0:
                dv = vdouble(V, v)
                if dv >= 0:
                    s = mksyl(L, dv, 0)
                    if s >= 0: put(n - 1, s); return b, True
            elif n < MAX:                          # 받침을 다음 글자로
                if JS1[T]: t1, mk = JS1[T], JS2[T]
                else: t1, mk = 0, JONG2K[T]
                a = mksyl(L, V, t1); c = mksyl(CHO_OF[mk], v, 0)
                if a >= 0 and c >= 0:
                    put(n - 1, a); put(n, c); return b, True
        elif is_cons(P):
            c = CHO_OF[P - JAMO_N]
            if c != 0xFF:
                s = mksyl(c, v, 0)
                if s >= 0: put(n - 1, s); return b, True
        elif is_vow(P):
            vs = virtual(Q, P)                     # 2글자 되돌아보기(ㅆㅗ+ㅏ 처럼 겹모음이 돼야 KS 에 있는 경우)
            if vs:
                dv = vdouble(vs[-1][1], v)
                if dv >= 0:
                    vs[-1][1] = dv
                    if lookback_put(b, n, vs): return b, True
            dv = vdouble(P - JAMO_N - 30, v)
            if dv >= 0: put(n - 1, JAMO_N + 30 + dv); return b, True
    if n >= MAX:
        return list(buf), False
    put(n, JAMO_N + k)
    return b, True


def delete(buf):
    """판 0 의 B. → (새 목록, 자모 단위로 처리했는가). False 면 원래 코드가 글자 통째로 지운다."""
    b = list(buf)
    if not b: return b, False
    P = code2n(b[-1])
    if not is_syl(P): return b, False
    L, V, T = lvt(P)
    while True:
        if T: T = JS1[T]
        elif VS1[V] != 0xFF: V = VS1[V]
        else:
            b[-1] = n2code(JAMO_N + CHO2K[L]); return b, True
        s = mksyl(L, V, T)
        if s >= 0:
            b[-1] = n2code(s); return b, True


def delete_whole(buf):
    """원래 B(글자 통째로)."""
    return list(buf[:-1])


# ---- 표시용 ----
def to_text(buf):
    out = []
    for c in buf:
        i = code2n(c)
        if is_syl(i): out.append(KS[i])
        elif i == SPACE_N: out.append(' ')
        elif i >= JAMO_N and i < JAMO_N + 51: out.append(COMPAT[i - JAMO_N])
        else: out.append('<%04X>' % c)
    return ''.join(out)


def from_text(s):
    out = []
    for ch in s:
        if ch in COMPAT: out.append(n2code(JAMO_N + COMPAT.index(ch)))
        elif ch == ' ': out.append(n2code(SPACE_N))
        else: out.append(n2code(KS.index(ch)))
    return out


def keys_of(text):
    """문장 → 두벌식 자판 입력(자모 k 목록). 겹모음·겹받침은 두 번 누름."""
    ks = []
    for ch in text:
        if ch in COMPAT:
            ks.append(COMPAT.index(ch)); continue
        u = ord(ch) - 0xAC00
        L, V, T = u // 588, u // 28 % 21, u % 28
        ks.append(COMPAT.index(CHO[L]))
        for x in JUNG_PAIR.get(JUNG[V], JUNG[V]): ks.append(COMPAT.index(x))
        if T:
            for x in JONG_PAIR.get(JONG[T], JONG[T]): ks.append(COMPAT.index(x))
    return ks


def type_keys(keys, buf=()):
    b = list(buf)
    for k in keys: b, _ = insert(b, k)
    return b


# ---- 독립 대조용: 유니코드 두벌식 오토마타(상태 기계, 11,172자 전부 허용) ----
def unicode_ime(keys):
    out = []; cho = jung = jong = None   # 조합 중 글자의 (초 문자, 중 문자, 종 문자)

    def flush():
        nonlocal cho, jung, jong
        if cho and jung:
            out.append(chr(0xAC00 + (CHO.index(cho) * 21 + JUNG.index(jung)) * 28 + (JONG.index(jong) if jong else 0)))
        elif cho: out.append(cho)
        elif jung: out.append(jung)
        cho = jung = jong = None

    inv_j = {v: k for k, v in JONG_PAIR.items()}; inv_v = {v: k for k, v in JUNG_PAIR.items()}
    for k in keys:
        c = COMPAT[k]
        if k < 30:
            if cho and jung and not jong and c in JONG:
                jong = c
            elif cho and jung and jong and (jong + c) in inv_j:
                jong = inv_j[jong + c]
            else:
                flush()
                if c in CHO: cho = c
                else: out.append(c)
        else:
            if cho and jung and jong:
                if jong in JONG_PAIR: keep, mv = JONG_PAIR[jong]
                else: keep, mv = None, jong
                jong = keep; flush(); cho, jung = mv, c
            elif cho and jung:
                if (jung + c) in inv_v: jung = inv_v[jung + c]
                else: flush(); jung = c
            elif cho:
                jung = c
            elif jung and (jung + c) in inv_v:
                jung = inv_v[jung + c]
            else:
                flush(); jung = c
    flush()
    return ''.join(out)


# ---- 시험 ----
def _t(keys_text, want, start=''):
    got = to_text(type_keys(keys_of(keys_text), from_text(start)))
    assert got == want, (start, keys_text, got, want)


def unit_tests():
    n = 0
    cases = [
        ('한글', '한글'), ('값', '값'), ('앉아', '앉아'), ('앉', '앉'), ('닭', '닭'),
        ('ㅆㅑ', 'ㅆㅑ'), ('ㅆㅑㅇ', '썅'), ('ㅆㅖㄴ', '쏀'), ('ㅆㅠㅇ', '쓩'), ('ㅉㅛㅇ', '쭁'), ('ㄹㅙㅆ', '뢨'),
        ('ㅂㅜㅔㄹㄱ', '붸ㄹㄱ'),     # 뷀·뷁 은 KS 밖 → 붸 + 낱자 ㄹ, ㄱ
        ('ㄱㅗㅏ', '과'), ('ㅗㅏ', 'ㅘ'), ('ㄱㅏㄱㅏ', '가가'), ('ㄷㅏㄹㄱㅇㅣ', '닭이'),
        ('ㄸㅗㅁ', '또ㅁ'), ('ㄸㅗㅁㅏ', '또마'),     # 똠 은 KS 밖
        ('ㄲㅏㄸ', '까ㄸ'), ('ㄲㅏㄸㅏ', '까따'),
        ('ㅏㄱ', 'ㅏㄱ'), ('ㄱㄱ', 'ㄱㄱ'), ('ㄱㅅ', 'ㄱㅅ'),
    ]
    for k, w in cases:
        keys = []
        for ch in k:
            keys += keys_of(ch)
        got = to_text(type_keys(keys)); assert got == w, (k, got, w); n += 1
    assert '뷁' not in KS and '뷀' not in KS and '쌰' not in KS and '썅' in KS
    # 8글자 제한
    b = from_text('가나다라마바사아')
    nb, ok = insert(b, COMPAT.index('ㄴ')); assert ok and to_text(nb) == '가나다라마바사안'; n += 1   # 받침은 됨
    nb, ok = insert(b, COMPAT.index('ㄸ')); assert not ok and nb == b; n += 1                        # 덧붙임은 안 됨
    b2 = from_text('가나다라마바사안')
    nb, ok = insert(b2, COMPAT.index('ㅏ')); assert not ok and nb == b2; n += 1                      # 받침 넘김 안 됨
    nb, ok = insert(from_text('가나다라마바사오'), COMPAT.index('ㅏ')); assert ok and to_text(nb) == '가나다라마바사와'; n += 1
    nb, ok = insert(from_text('가나다라마바ㅆㅑ'), COMPAT.index('ㅇ')); assert ok and to_text(nb) == '가나다라마바썅'; n += 1
    # 지우기
    for s, chain in [('앉', '안아ㅇ'), ('각', '가ㄱ'), ('과', '고ㄱ'), ('괜', '괘고ㄱ'), ('닭', '달다ㄷ'),
                     ('썅', 'ㅆ'), ('뢨', '로ㄹ'), ('읊', '을으ㅇ')]:
        b = from_text(s); got = []
        while True:
            b, ok = delete(b)
            if not ok: break
            got.append(to_text(b))
        assert ''.join(got) == chain, (s, got, chain); n += 1
    assert delete(from_text('ㄱ')) == (from_text('ㄱ'), False); n += 1
    return n


def random_vs_unicode(count=20000, seed=1):
    """무작위 자판 입력을 유니코드 오토마타와 비교. 유니코드 결과가 KS 음절·자모만이고 8글자 이하면 같아야 한다."""
    rnd = random.Random(seed); same = skipped = 0; ks = set(KS)
    for _ in range(count):
        keys = [rnd.choice(BOARD_KEYS) for _ in range(rnd.randint(1, 16))]
        if rnd.random() < 0.6:   # 실제 낱말 꼴(자음+모음 위주)
            keys = keys_of(''.join(rnd.choice(KS) for _ in range(rnd.randint(1, 6))))
        want = unicode_ime(keys)
        if len(want) > MAX or any('가' <= c <= '힣' and c not in ks for c in want):
            skipped += 1; continue
        got = to_text(type_keys(keys))
        assert got == want, (keys, got, want)
        same += 1
    return same, skipped


def roundtrip_all():
    """KS 2,350자 각각: 빈 버퍼에 자판대로 치면 그 한 글자가 되고, B 를 거듭하면 비워질 때까지 자모 단위로 줄어든다."""
    for i, h in enumerate(KS):
        b = type_keys(keys_of(h))
        assert to_text(b) == h, (h, to_text(b))
        steps = 0
        while b:
            nb, ok = delete(b)
            b = nb if ok else delete_whole(b)
            steps += 1; assert steps <= 6
    return NSYL


if __name__ == '__main__':
    print('단위 시험', unit_tests(), '개 통과')
    print('KS 2,350자 왕복', roundtrip_all(), '자 통과')
    s, k = random_vs_unicode()
    print('유니코드 오토마타 대조: 일치', s, '/ 건너뜀(유니코드 결과에 KS 밖 음절·9글자 이상)', k)
