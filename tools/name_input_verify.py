"""이름 입력 자모 조합 패치 검증: 패치된 main.dol 을 unicorn(PPC32 BE)에 올려 실제 기계어를 돌리고
파이썬 기준 구현(tools/hangul_compose.py)과 결과를 비교한다. 원본 ISO 는 읽기만 한다.

  1. 훅 단위(수천 개): 0x8000C1C0(글자 넣기)·0x8000CAE8(지우기)에서 시작 → 나가는 곳·버퍼 17바이트·글자 수·
     효과음(r25 / 지우기음 호출)·비휘발 레지스터(r14~r31, r1) 보존 비교.
  2. 작은 훅: 0x8000C0D0(공백 세기), 0x8000C908~(8글자 END 이동).
  3. 함수 통째: 0x8000BF70(A 글자 고르기)·0x8000C9D0(버튼 분배, B)을 원래 코드째 돌려
     판 0 의 66칸·END 확정(띄어쓰기만 이름 거부)·8글자 END 미이동·판 1 의 원래 동작 확인.
  4. 패치 전후 분해 → work/survey/namein_patch_disasm.txt

    python tools/name_input_verify.py [--n 20000] [--seed 1]
"""
import argparse, os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc
import hangul_compose as hc
import name_input_patch as nip
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.ppc_const import *

R = [globals()['UC_PPC_REG_%d' % i] for i in range(32)]
SCRATCH = 0x80500000          # 칸 코드·LR 표지
SENTINEL = 0x80500100
STACK = 0x80460000
SND_TABLE = 0x801E05D8 + nip.SND
CURSOR = 0x8031CE84
PAD = 0x80320F98
SAVE_NAME = 0x803C0BD6


def load_sections(dol):
    offs = struct.unpack('>18I', dol[:0x48]); addrs = struct.unpack('>18I', dol[0x48:0x90])
    sizes = struct.unpack('>18I', dol[0x90:0xD8])
    return [(a, dol[o:o + s]) for o, a, s in zip(offs, addrs, sizes) if s]


class Emu:
    def __init__(self, dol):
        self.base_mem = load_sections(dol)
        self.uc = uc = Uc(UC_ARCH_PPC, UC_MODE_PPC32 | UC_MODE_BIG_ENDIAN)
        uc.mem_map(0x80000000, 0x01800000)
        for a, b in self.base_mem: uc.mem_write(a, bytes(b))
        self.snapshot = {a: bytes(b) for a, b in self.base_mem}
        # 효과음 함수는 빈 함수로(호출만 기록)
        uc.mem_write(nip.SND_FUNC, struct.pack('>I', 0x4E800020))
        self.sounds = []
        uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: self.sounds.append(u.reg_read(R[3])), begin=nip.SND_FUNC, end=nip.SND_FUNC)
        self.exits = set(); self.hit = None
        uc.hook_add(UC_HOOK_CODE, self._code)
        self.snd = struct.unpack('>10I', bytes(uc.mem_read(SND_TABLE, 40)))   # +0 수락 +4 지우기 +0x20 오류 +0x24 확정

    def _code(self, uc, addr, size, data):
        if addr in self.exits:
            self.hit = addr; uc.emu_stop()

    def r8(self, a): return self.uc.mem_read(a, 1)[0]
    def w8(self, a, v): self.uc.mem_write(a, bytes([v & 0xFF]))
    def r32(self, a): return struct.unpack('>I', bytes(self.uc.mem_read(a, 4)))[0]
    def w32(self, a, v): self.uc.mem_write(a, struct.pack('>I', v & 0xFFFFFFFF))

    def set_state(self, buf, panel):
        b = bytearray(0x21)
        for i, c in enumerate(buf): struct.pack_into('>H', b, 2 * i, c)
        self.uc.mem_write(nip.BUF, bytes(b))
        self.w8(nip.CNT, len(buf)); self.w8(nip.PANEL, panel)

    def get_buf(self):
        return bytes(self.uc.mem_read(nip.BUF, 0x21)), self.r8(nip.CNT)

    def regs(self, rnd):
        uc = self.uc
        vals = {}
        for i in range(32): uc.reg_write(R[i], 0)
        for i in list(range(14, 32)):
            v = rnd.getrandbits(32); uc.reg_write(R[i], v); vals[i] = v
        uc.reg_write(R[1], STACK); uc.reg_write(R[2], 0x80459980); uc.reg_write(R[13], 0x80455B80)
        uc.reg_write(R[31], 0x801E05D8)
        vals.update({1: STACK, 31: 0x801E05D8})
        return vals

    def run(self, start, exits, limit=200000):
        self.exits = set(exits); self.hit = None; self.sounds = []
        self.uc.emu_start(start, 0xFFFFFFFC, count=limit)
        return self.hit


def buf_bytes(codes):
    b = bytearray(0x21)
    for i, c in enumerate(codes): struct.pack_into('>H', b, 2 * i, c)
    return bytes(b)


# ---- 무작위 상태 ----
OTHER = [0x8148, 0x815B, 0x8149, 0x824F, 0x8258, 0x8140, 0x82A0, 0x8341]   # 띄어쓰기 아닌 비한글 2바이트


def rand_state(rnd):
    r = rnd.random()
    if r < 0.5:      # 실제 판 입력으로 만든 상태
        b = []
        for _ in range(rnd.randint(0, 14)):
            b, _ = hc.insert(b, rnd.choice(hc.BOARD_KEYS))
        return b
    n = rnd.randint(0, 8); b = []
    for _ in range(n):
        t = rnd.random()
        if t < 0.45: b.append(hc.n2code(rnd.randrange(hc.NSYL)))
        elif t < 0.8: b.append(hc.n2code(hc.JAMO_N + rnd.randrange(51)))
        elif t < 0.88: b.append(hc.n2code(hc.SPACE_N))
        else: b.append(rnd.choice(OTHER))
    return b


def check_preserved(emu, vals, skip=(25,)):
    for i, v in vals.items():
        if i in skip: continue
        assert emu.uc.reg_read(R[i]) == v, ('레지스터 보존 안 됨', i)


def test_select(emu, n, rnd):
    stats = {'조합(판0 자모)': 0, '그대로 통과': 0, '실패(오류음)': 0}
    for _ in range(n):
        buf = rand_state(rnd)
        panel = 0 if rnd.random() < 0.85 else rnd.choice([1, 2])
        if rnd.random() < 0.85: code = hc.n2code(hc.JAMO_N + rnd.randrange(51));
        else: code = rnd.choice(OTHER + [hc.n2code(hc.SPACE_N), 0x9540 + 0x34, 0x9574, 0x9540])
        emu.set_state(buf, panel)
        vals = emu.regs(rnd)
        off = rnd.randrange(0, 64, 2)
        emu.uc.mem_write(SCRATCH + off, struct.pack('>H', code))
        emu.uc.reg_write(R[30], SCRATCH); emu.uc.reg_write(R[27], off)
        vals[30] = SCRATCH; vals[27] = off
        hit = emu.run(nip.HOOK_SELECT, [nip.HOOK_SELECT_RET, nip.SELECT_DONE])
        got_buf, got_n = emu.get_buf()
        k = code - 0x9541
        if panel != 0 or not (0 <= k <= 50):
            assert hit == nip.HOOK_SELECT_RET, (hex(code), panel, hit)
            assert got_buf == buf_bytes(buf) and got_n == len(buf)
            assert emu.uc.reg_read(R[3]) == len(buf)            # 원래 명령 lbz r3,-0x502A(r13)
            check_preserved(emu, vals, skip=())
            stats['그대로 통과'] += 1
            continue
        want, ok = hc.insert(buf, k)
        assert hit == nip.SELECT_DONE, (buf, k, hit)
        assert got_buf == buf_bytes(want) and got_n == len(want), (hc.to_text(buf), hc.COMPAT[k], got_buf.hex(), hc.to_text(want))
        assert emu.uc.reg_read(R[25]) == (emu.snd[0] if ok else emu.snd[8]), 'r25 효과음'
        assert emu.uc.reg_read(R[1]) == STACK
        check_preserved(emu, vals)
        stats['조합(판0 자모)' if ok else '실패(오류음)'] += 1
    return stats


def test_delete(emu, n, rnd):
    stats = {'자모 단위 지움': 0, '원래 코드로(통째)': 0}
    for _ in range(n):
        buf = rand_state(rnd)
        if not buf: buf = [hc.n2code(rnd.randrange(hc.NSYL))]
        panel = 0 if rnd.random() < 0.85 else rnd.choice([1, 2])
        emu.set_state(buf, panel)
        vals = emu.regs(rnd)
        hit = emu.run(nip.HOOK_DELETE, [nip.HOOK_DELETE_RET, nip.DELETE_DONE])
        got_buf, got_n = emu.get_buf()
        want, handled = hc.delete(buf) if panel == 0 else (buf, False)
        if handled:
            assert hit == nip.DELETE_DONE
            assert got_buf == buf_bytes(want) and got_n == len(want), (hc.to_text(buf), got_buf.hex(), hc.to_text(want))
            assert emu.sounds == [emu.snd[1]], emu.sounds
            stats['자모 단위 지움'] += 1
        else:
            assert hit == nip.HOOK_DELETE_RET
            assert got_buf == buf_bytes(buf) and got_n == len(buf)
            assert emu.uc.reg_read(R[3]) == 0x801E05D8 + nip.SND and emu.sounds == []
            stats['원래 코드로(통째)'] += 1
        assert emu.uc.reg_read(R[1]) == STACK
        check_preserved(emu, vals, skip=())
    return stats


def run_select(emu, buf, k, rnd):
    emu.set_state(buf, 0); emu.regs(rnd)
    emu.uc.mem_write(SCRATCH, struct.pack('>H', 0x9541 + k)); emu.uc.reg_write(R[30], SCRATCH); emu.uc.reg_write(R[27], 0)
    assert emu.run(nip.HOOK_SELECT, [nip.HOOK_SELECT_RET, nip.SELECT_DONE]) == nip.SELECT_DONE
    b, n = emu.get_buf()
    return [struct.unpack_from('>H', b, 2 * i)[0] for i in range(n)], emu.uc.reg_read(R[25]) == emu.snd[0]


def run_delete(emu, buf, rnd):
    emu.set_state(buf, 0); emu.regs(rnd)
    hit = emu.run(nip.HOOK_DELETE, [nip.HOOK_DELETE_RET, nip.DELETE_DONE])
    b, n = emu.get_buf()
    return [struct.unpack_from('>H', b, 2 * i)[0] for i in range(n)], hit == nip.DELETE_DONE


def test_exhaustive(emu, rnd):
    """KS 2,350자 전부: (1) 빈 버퍼에서 자판대로 한 키씩 넣고 B 로 끝까지 지우기, (2) 그 한 글자 뒤에 판 자모 40개를 하나씩."""
    n = 0
    for i in range(hc.NSYL):
        h = hc.KS[i]; buf = []
        for k in hc.keys_of(h):
            want = hc.insert(buf, k); got = run_select(emu, buf, k, rnd); n += 1
            assert got == want, (h, buf, k)
            buf = want[0]
        assert hc.to_text(buf) == h
        while buf:
            want = hc.delete(buf); got = run_delete(emu, buf, rnd); n += 1
            assert got == want, (h, hc.to_text(buf))
            buf = want[0] if want[1] else hc.delete_whole(buf)
        base = [hc.n2code(i)]
        for k in hc.BOARD_KEYS:
            assert run_select(emu, base, k, rnd) == hc.insert(base, k), (h, k); n += 1
    return n


def test_small_hooks(emu, rnd):
    n = 0
    for lead in range(256):
        emu.regs(rnd); emu.uc.reg_write(R[0], lead)
        hit = emu.run(nip.HOOK_SPACE, [nip.SPACE_YES, nip.SPACE_NO])
        assert hit == (nip.SPACE_YES if lead in (0x81, 0x95) else nip.SPACE_NO), lead; n += 1
    for cnt in range(10):
        for panel in range(3):
            emu.regs(rnd); emu.w8(nip.CNT, cnt); emu.w8(nip.PANEL, panel)
            hit = emu.run(0x8000C908, [nip.END_MOVE, nip.END_SKIP])
            assert hit == (nip.END_MOVE if cnt == 8 and panel != 0 else nip.END_SKIP), (cnt, panel); n += 1
    return n


# ---- 함수 통째 ----
def call(emu, func, rnd, limit=2000000):
    vals = emu.regs(rnd)
    emu.uc.reg_write(UC_PPC_REG_LR, SENTINEL)
    hit = emu.run(func, [SENTINEL], limit)
    assert hit == SENTINEL, ('함수가 안 돌아옴', hex(func))
    check_preserved(emu, vals, skip=())
    return emu.uc.reg_read(R[3])


def set_cursor(emu, x, y, panel):
    emu.w32(CURSOR, x); emu.w32(CURSOR + 4, y); emu.w32(CURSOR + 8, x * 6 + y); emu.w8(nip.PANEL, panel)


def panel0_model(buf, x, y):
    """판 0 에서 A → (새 버퍼, 반환값, 효과음 인덱스, 확정 이름 또는 None)."""
    code = struct.unpack_from('>H', nip.panel0_bytes(), 2 * (y * 11 + x))[0]
    if (x, y) == (10, 5):
        if not buf or all(c in (0x8140, 0x9540) for c in buf): return buf, 0, 8, None
        return buf, 1, 9, buf
    k = code - 0x9541
    if 0 <= k <= 50:
        nb, ok = hc.insert(buf, k)
        return nb, 0, 0 if ok else 8, None
    if len(buf) >= 8: return buf, 0, 8, None
    return buf + [code], 0, 0, None


def test_functions(emu, rnd, n_rand):
    cnt = {'A 판0 칸×상태': 0, 'A END 확정': 0, 'B 함수': 0, '판1 8글자 END 이동': 0}
    states = [[], hc.from_text('가'), hc.from_text('한글'), hc.from_text('가나다라마바사'), hc.from_text('가나다라마바사아'),
              hc.from_text('ㅆㅑ'), hc.from_text('  '), hc.from_text('가나다라마바ㅆㅑ'), [0x8140, 0x9540]]
    cells = [(x, y) for y in range(6) for x in range(11) if (x, y) != (10, 4)]
    jobs = [(s, c) for s in states for c in cells]
    for _ in range(n_rand):
        jobs.append((rand_state(rnd), rnd.choice(cells)))
    for buf, (x, y) in jobs:
        emu.set_state(buf, 0); set_cursor(emu, x, y, 0)
        emu.uc.mem_write(SAVE_NAME - 2, b'\x00' * 20)
        ret = call(emu, 0x8000BF70, rnd)
        want, wret, wsnd, saved = panel0_model(buf, x, y)
        got_buf, got_n = emu.get_buf()
        assert ret == wret, (hc.to_text(buf), x, y, ret)
        assert got_buf == buf_bytes(want) and got_n == len(want), (hc.to_text(buf), x, y, got_buf.hex(), hc.to_text(want))
        assert emu.sounds == [emu.snd[wsnd]], (hc.to_text(buf), x, y, emu.sounds, wsnd)
        # 판 0 은 8글자가 돼도 커서 그대로
        assert (emu.r32(CURSOR), emu.r32(CURSOR + 4)) == (x, y)
        if saved is not None:
            m = 2 * len(saved)
            assert bytes(emu.uc.mem_read(SAVE_NAME, m + 1)) == buf_bytes(saved)[:m] + b'\x00', '확정 이름'
            cnt['A END 확정'] += 1
        cnt['A 판0 칸×상태'] += 1
    # B: 버튼 분배 함수에 B 만 눌린 상태
    for _ in range(max(200, n_rand)):
        buf = rand_state(rnd); panel = 0 if rnd.random() < 0.8 else 1
        emu.set_state(buf, panel); set_cursor(emu, 0, 0, panel)
        emu.w32(PAD + 0x14, 0x200)
        ret = call(emu, 0x8000C9D0, rnd)
        got_buf, got_n = emu.get_buf()
        if not buf:
            want, snd = buf, emu.snd[8]
        else:
            want, h = hc.delete(buf) if panel == 0 else (buf, False)
            if not h: want = hc.delete_whole(buf)
            snd = emu.snd[1]
        assert ret == 0
        assert got_buf == buf_bytes(want) and got_n == len(want), (panel, hc.to_text(buf), got_buf.hex(), hc.to_text(want))
        assert emu.sounds == [snd], (emu.sounds, snd)
        cnt['B 함수'] += 1
    emu.w32(PAD + 0x14, 0)
    # 판 1(가타카나): 8번째 글자에서 원래대로 커서가 END 로 감
    buf = [0x8341] * 7
    emu.set_state(buf, 1); set_cursor(emu, 0, 0, 1)
    call(emu, 0x8000BF70, rnd)
    got_buf, got_n = emu.get_buf()
    assert got_n == 8 and emu.r32(CURSOR + 8) == emu.r32(CURSOR) * 6 + emu.r32(CURSOR + 4) and (emu.r32(CURSOR), emu.r32(CURSOR + 4)) != (0, 0)
    cnt['판1 8글자 END 이동'] += 1
    return cnt


# ---- 분해 기록 ----
def disasm_report(orig, new, L, path):
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    f = lambda va: va - 0x80003000

    def dis(data, va, n):
        out = []
        for i in md.disasm(data[f(va):f(va) + 4 * n], va):
            out.append('  %08x: %s  %s %s' % (i.address, data[f(i.address):f(i.address) + 4].hex(), i.mnemonic, i.op_str))
        return out

    o = ['# 이름 입력 자모 조합 패치 — 패치 전후 분해 (tools/name_input_verify.py 가 만듦, capstone PPC32 BE)',
         '# 파일 오프셋 = VA − 0x80003000 (T1·D3). T2 = 0x80466260 (파일 0x251200).', '']
    o.append('## DOL 헤더 (T2 칸)')
    for name, off in (('T2 오프셋', 0x08), ('T2 주소', 0x50), ('T2 크기', 0x98)):
        o.append('  0x%02X %-8s 전 %08X → 후 %08X' % (off, name, struct.unpack_from('>I', orig, off)[0], struct.unpack_from('>I', new, off)[0]))
    o.append('  파일 크기 전 0x%X → 후 0x%X' % (len(orig), len(new)))
    o.append('')
    for title, va, n in (('OSInit 아레나 하한 (보통 경로)', 0x80131FFC, 5), ('OSInit 아레나 하한 (디버그 모니터 경로)', 0x80132038, 6),
                         ('훅: 글자 넣기', 0x8000C1B8, 4), ('훅: 지우기(B)', 0x8000CAE0, 4),
                         ('훅: END 공백 세기', 0x8000C0C8, 5), ('훅: 8글자 END 이동', 0x8000C908, 4)):
        o.append('## %s — 전' % title); o += dis(orig, va, n)
        o.append('## %s — 후' % title); o += dis(new, va, n); o.append('')
    o.append('## 판 0 글자표 0x801E6E6D (132 B) — 전 / 후')
    o.append('  ' + orig[f(0x801E6E6D):f(0x801E6E6D) + 132].hex())
    o.append('  ' + new[f(0x801E6E6D):f(0x801E6E6D) + 132].hex())
    o.append('  후 = ' + ''.join(hc.to_text([c]) if hc.code2n(c) >= 0 else bytes([c >> 8, c & 0xFF]).decode('cp932')
                                for c in struct.unpack('>66H', new[f(0x801E6E6D):f(0x801E6E6D) + 132])))
    o.append('## 판 0 건너뛸 칸 포인터 0x801E71C4: 전 %s → 후 %s' % (orig[f(0x801E71C4):f(0x801E71C4) + 4].hex(), new[f(0x801E71C4):f(0x801E71C4) + 4].hex()))
    o.append('')
    lines, L2 = nip.listing()
    o.append('## T2 루틴 (0x%08X~0x%08X, %d B) · 표 0x%08X~0x%08X' % (nip.T2_VA, L2['end_of_code'], L2['end_of_code'] - nip.T2_VA, L2['TBL'], L2['TBL_END']))
    for k in ('SYL', 'CHO_OF', 'JONG_OF', 'CHO2K', 'JONG2K', 'JS1', 'JS2', 'VS1', 'VS2'):
        o.append('#   표 %-7s 0x%08X' % (k, L2['TBL_' + k]))
    o += lines
    open(path, 'w', encoding='utf-8').write('\n'.join(o) + '\n')


def check_branches(L):
    """T2 안 분기 대상이 모두 라벨이거나 원래 코드의 약속된 주소인지."""
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    sec, _ = nip.build_t2()
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    ok = set(v for k, v in L.items() if not k.startswith('TBL')) | {
        nip.SELECT_DONE, nip.HOOK_SELECT_RET, nip.DELETE_DONE, nip.HOOK_DELETE_RET, nip.SPACE_YES, nip.SPACE_NO,
        nip.END_MOVE, nip.END_SKIP, nip.SND_FUNC}
    n = 0
    for i in md.disasm(sec[:L['end_of_code'] - nip.T2_VA], nip.T2_VA):
        if i.mnemonic.startswith('b') and i.mnemonic not in ('blr',) and '0x' in i.op_str:
            t = int(i.op_str.split('0x')[-1], 16)
            assert t in ok, ('이상한 분기', hex(i.address), i.op_str); n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--report', default=os.path.join(disc.ROOT, 'work/survey/namein_patch_disasm.txt'))
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    orig = disc.read('sys/main.dol')
    new, L = nip.patch(orig)
    print('분기 대상 확인', check_branches(L), '개')
    emu = Emu(new)
    print('글자 넣기 훅', a.n, '개:', test_select(emu, a.n, rnd))
    print('지우기 훅', a.n // 2, '개:', test_delete(emu, a.n // 2, rnd))
    print('공백 세기·END 이동 훅', test_small_hooks(emu, rnd), '개')
    print('KS 2,350자 전수(자판 입력·B·음절+자모 40)', test_exhaustive(emu, rnd), '회')
    print('함수 통째', test_functions(emu, rnd, a.n // 20))
    disasm_report(orig, new, L, a.report)
    print('분해 기록 →', a.report)
    print('모두 일치')


if __name__ == '__main__':
    main()
