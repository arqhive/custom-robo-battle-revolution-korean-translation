"""main.dol 이름 입력판 한글 자모 조합 패치 (docs/name-input.md 4·「구현」 절, 사용자 결정 10/29).

원본 main.dol 바이트 → 패치된 main.dol 바이트. 바꾸는 것:
  1. 새 텍스트 섹션 T2: VA 0x80466260, 0x2000 바이트, 파일 끝(0x251200)에 붙이고 DOL 헤더에 등록.
     안에 조합 루틴(PowerPC, keystone 으로 조립) + 표(음절표 2,350×2 B, 자모 표).
  2. OSInit 아레나 하한 0x80466260 → 0x80468260 (보통 경로 0x80132004·08, 디버그 경로 0x8013203C·40;
     addi 즉값 0x8260 은 부호 있는 수라 lis 도 0x8046 → 0x8047 로 같이 바꾼다).
  3. 훅 4곳(b 명령으로 T2 로):
       0x8000C1C0 글자 넣기 — 판 0 의 자모(0x9541~0x9573)면 조합
       0x8000CAE8 지우기(B) — 판 0 에서 마지막 글자가 음절이면 자모 한 단계 지움
       0x8000C0D0 END 때 「전부 공백」 검사 — 0x8140 에 더해 0x9540(한글 띄어쓰기)도 공백으로 셈
       0x8000C910 8글자 되면 커서 END 로 — 판 0 에선 하지 않음
  4. 판 0 글자표(0x801E6E6D, 132 바이트) = 배치안 A, 판 0 건너뛸 칸 포인터 0x801E71C4 = 0x801E71BD.

    python tools/name_input_patch.py <출력.dol> [--asm 목록.txt]
    (입력은 원본 ISO 의 sys/main.dol. 출력 기본값 없음 — 빌드 도구가 부를 때는 patch(dol) 를 쓴다.)
"""
import argparse, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hangul_compose as hc

T2_VA = 0x80466260
T2_SIZE = 0x2000
T2_OFF = 0x251200            # 원본 파일 끝
DOL_SIZE = 0x251200
ARENA_NEW = T2_VA + T2_SIZE  # 0x80468260

BUF = 0x801E6E4C             # 입력 중 이름 버퍼
CNT = 0x80450B56             # 글자 수 (-0x502A(r13))
PANEL = 0x8031CE94           # 판 번호 (0x8031CE84 + 0x10)
SND = 0x75AC                 # r31(0x801E05D8) + 0x75AC = 효과음 표 0x801E7B84 (+0 수락, +4 지우기, +0x20 오류)
SND_FUNC = 0x80098C6C

HOOK_SELECT, HOOK_SELECT_RET, SELECT_DONE = 0x8000C1C0, 0x8000C1C4, 0x8000C9A8
HOOK_DELETE, HOOK_DELETE_RET, DELETE_DONE = 0x8000CAE8, 0x8000CAEC, 0x8000CEA8
HOOK_SPACE, SPACE_YES, SPACE_NO = 0x8000C0D0, 0x8000C0D8, 0x8000C0F8
HOOK_END, END_MOVE, END_SKIP = 0x8000C910, 0x8000C914, 0x8000C9A8

# 원래 명령(패치 전 확인용)
ORIG = {
    HOOK_SELECT: 0x886DAFD6,   # lbz r3,-0x502A(r13)
    HOOK_DELETE: 0x387F75AC,   # addi r3,r31,0x75AC
    HOOK_SPACE: 0x28000081,    # cmplwi r0,0x81
    HOOK_END: 0x40820098,      # bne 0x8000C9A8
    0x80132004: 0x3C608046, 0x80132008: 0x38636260,   # lis r3,0x8046 / addi r3,r3,0x6260
    0x8013203C: 0x3C608046, 0x80132040: 0x38634260,   # lis r3,0x8046 / addi r3,r3,0x4260
    0x801E71C4: 0x801E71B5,    # 판 0 건너뛸 칸 목록 포인터
}
ARENA = {
    0x80132004: 0x3C608047, 0x80132008: 0x38638260,   # lis r3,0x8047 / addi r3,r3,-0x7DA0 → 0x80468260
    0x8013203C: 0x3C608047, 0x80132040: 0x38638260,   # 디버그 모니터 경로도 같은 값(+0x1F 정렬해도 그대로)
}
SKIP_PTR_VA, SKIP_PTR_NEW = 0x801E71C4, 0x801E71BD     # 0x801E71BD = 0A 04 FF FF → (10,4) 만 건너뜀

PANEL0_VA = 0x801E6E6D
# 배치안 A (11열 × 6행, 행 우선)
PANEL0 = [
    'ㄱ', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ',
    'ㅂ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ',
    'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ', 0x815B, 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ',
    'ㄲ', 'ㄸ', 'ㅃ', 'ㅆ', 'ㅉ', 'ㅡ', 'ㅢ', 'ㅣ', 0x8149, 0x8148, 0x8160,
    0x824F, 0x8250, 0x8251, 0x8252, 0x8253, 0x8145, 0x81F4, 0x818A, 0x8197, ' ', 0x8140,
    0x8254, 0x8255, 0x8256, 0x8257, 0x8258, 0x8175, 0x8176, 0x8169, 0x816A, 0x8190, 0x8140,
]
# docs/name-input.md 4-2 절에 적은 바이트(대조용)
PANEL0_BYTES_DOC = bytes.fromhex(
    '95 41 95 44 95 47 95 49 95 51 95 5f 95 60 95 61 95 62 95 63 95 64 95 52 95 55 95 57 95 58 95 5a 95 65 95 66 95 67 95 68 95 69 95 6a 95 5b 95 5c 95 5d 95 5e 81 5b 95 6b 95 6c 95 6d 95 6e 95 6f 95 70 95 42 95 48 95 53 95 56 95 59 95 71 95 72 95 73 81 49 81 48 81 60 82 4f 82 50 82 51 82 52 82 53 81 45 81 f4 81 8a 81 97 95 40 81 40 82 54 82 55 82 56 82 57 82 58 81 75 81 76 81 69 81 6a 81 90 81 40')

TBL_LAYOUT = [('SYL', 2 * hc.NSYL), ('CHO_OF', 30), ('JONG_OF', 30), ('CHO2K', 19), ('JONG2K', 28),
              ('JS1', 28), ('JS2', 28), ('VS1', 21), ('VS2', 21)]


def panel0_bytes():
    out = b''
    for c in PANEL0:
        if isinstance(c, str):
            i = hc.SPACE_N if c == ' ' else hc.JAMO_N + hc.COMPAT.index(c)
            c = hc.n2code(i)
        out += struct.pack('>H', c)
    assert len(out) == 132
    return out


def tables():
    data = {'SYL': b''.join(struct.pack('>H', u) for u in hc.SYL), 'CHO_OF': hc.CHO_OF, 'JONG_OF': hc.JONG_OF,
            'CHO2K': hc.CHO2K, 'JONG2K': hc.JONG2K, 'JS1': hc.JS1, 'JS2': hc.JS2, 'VS1': hc.VS1, 'VS2': hc.VS2}
    blob = b''; off = {}
    for name, size in TBL_LAYOUT:
        assert len(data[name]) == size, name
        off[name] = len(blob); blob += data[name]
    return blob, off


def ha(x): return ((x + 0x8000) >> 16) & 0xFFFF
def lo(x): return x & 0xFFFF if (x & 0xFFFF) < 0x8000 else (x & 0xFFFF) - 0x10000


ASM = r'''
# ===== 훅: 글자 넣기 (0x8000C1C0 에서 b) — r27 = 열·2, r30 = 행 시작 주소, r31 = 0x801E05D8 =====
hook_select:
    lis r12, {PANEL_ha}
    lbz r0, {PANEL_lo}(r12)
    cmpwi r0, 0
    bne hs_pass
    lbzx r3, r30, r27
    addi r4, r27, 1
    lbzx r4, r30, r4
    slwi r3, r3, 8
    or r3, r3, r4
    li r4, 0
    ori r4, r4, 0x9541
    subf r3, r4, r3
    cmplwi r3, 50
    bgt hs_pass
    bl compose
    cmpwi r3, 0
    beq hs_fail
    lwz r25, {SND}(r31)
    b {SELECT_DONE}
hs_fail:
    lwz r25, {SND_ERR}(r31)
    b {SELECT_DONE}
hs_pass:
    lbz r3, -0x502a(r13)
    b {HOOK_SELECT_RET}

# ===== 훅: 지우기 B (0x8000CAE8 에서 b) — 글자 수 > 0 이 보장된 자리 =====
hook_delete:
    lis r12, {PANEL_ha}
    lbz r0, {PANEL_lo}(r12)
    cmpwi r0, 0
    bne hd_pass
    bl decompose
    cmpwi r3, 0
    beq hd_pass
    lwz r3, {SND_DEL}(r31)
    bl {SND_FUNC}
    b {DELETE_DONE}
hd_pass:
    addi r3, r31, {SND}
    b {HOOK_DELETE_RET}

# ===== 훅: END 때 공백 세기 (0x8000C0D0 cmplwi r0,0x81 자리) — 0x81 또는 0x95 + 둘째 0x40 =====
hook_space:
    cmplwi r0, 0x81
    beq hp_yes
    cmplwi r0, 0x95
    bne hp_no
hp_yes:
    b {SPACE_YES}
hp_no:
    b {SPACE_NO}

# ===== 훅: 8글자 되면 END 로 (0x8000C910 bne 자리, cr0 = 글자 수 cmplwi 8) — 판 0 이면 건너뜀 =====
hook_end:
    bne he_skip
    lis r12, {PANEL_ha}
    lbz r12, {PANEL_lo}(r12)
    cmpwi r12, 0
    beq he_skip
    b {END_MOVE}
he_skip:
    b {END_SKIP}

# ===== compose(r3 = 자모 k 0~50) → r3 = 1 성공 / 0 실패(버퍼 그대로) =====
# r14 k, r15 글자 수, r16 버퍼, r17 P(마지막 글자 순번), r18 Q(그 앞), r19 모음 v, r20 표,
# r21 CNT ha, r22~24 끝 음절 (초,중,종), r25~27 앞 음절, r28 음절 개수, r29 링크, r30·r31 임시
compose:
    stwu r1, -0x60(r1)
    mflr r0
    stw r0, 0x64(r1)
    stmw r14, 8(r1)
    mr r14, r3
    lis r20, {TBL_ha}
    addi r20, r20, {TBL_lo}
    lis r16, {BUF_ha}
    addi r16, r16, {BUF_lo}
    lis r21, {CNT_ha}
    lbz r15, {CNT_lo}(r21)
    li r17, -1
    li r18, -1
    cmpwi r15, 1
    blt c_go
    addi r3, r15, -1
    slwi r3, r3, 1
    lhzx r3, r16, r3
    bl code2n
    mr r17, r3
    cmpwi r15, 2
    blt c_go
    addi r3, r15, -2
    slwi r3, r3, 1
    lhzx r3, r16, r3
    bl code2n
    mr r18, r3
c_go:
    cmplwi r14, 30
    bge v_start
# --- 자음 ---
    cmplwi r17, 2350
    bge c_notsyl
    mr r3, r17
    bl lvt
    mr r22, r3
    mr r23, r4
    mr r24, r5
    cmpwi r24, 0
    bne c_hast
    addi r3, r20, {JONG_OF}
    lbzx r5, r3, r14
    cmpwi r5, 0
    beq append
    b c_mk
c_hast:
    li r25, 1
c_jd:
    cmplwi r25, 28
    bge append
    addi r3, r20, {JS1}
    lbzx r3, r3, r25
    cmpw r3, r24
    bne c_jdn
    addi r3, r20, {JS2}
    lbzx r3, r3, r25
    cmpw r3, r14
    beq c_jdf
c_jdn:
    addi r25, r25, 1
    b c_jd
c_jdf:
    mr r5, r25
c_mk:
    mr r3, r22
    mr r4, r23
    bl mksyl
    cmpwi r3, 0
    blt append
    mr r4, r3
    addi r3, r15, -1
    b put_ok
c_notsyl:
    addi r3, r17, -2381
    cmplwi r3, 20
    bgt append
    bl virtual
    cmpwi r28, 0
    beq append
    addi r3, r20, {JONG_OF}
    lbzx r24, r3, r14
    cmpwi r24, 0
    beq append
    bl lbput
    cmpwi r3, 0
    bne ok
    b append
# --- 모음 ---
v_start:
    addi r19, r14, -30
    cmplwi r17, 2350
    bge v_notsyl
    mr r3, r17
    bl lvt
    mr r22, r3
    mr r23, r4
    mr r24, r5
    cmpwi r24, 0
    bne v_hast
    mr r3, r23
    mr r4, r19
    bl vdouble
    cmpwi r3, 0
    blt append
    mr r4, r3
    mr r3, r22
    li r5, 0
    bl mksyl
    cmpwi r3, 0
    blt append
    mr r4, r3
    addi r3, r15, -1
    b put_ok
v_hast:
    cmplwi r15, 8
    bge append
    addi r3, r20, {JS1}
    lbzx r25, r3, r24
    cmpwi r25, 0
    beq v_single
    addi r3, r20, {JS2}
    lbzx r27, r3, r24
    b v_mv
v_single:
    addi r3, r20, {JONG2K}
    lbzx r27, r3, r24
v_mv:
    addi r3, r20, {CHO_OF}
    lbzx r27, r3, r27
    mr r3, r22
    mr r4, r23
    mr r5, r25
    bl mksyl
    cmpwi r3, 0
    blt append
    mr r30, r3
    mr r3, r27
    mr r4, r19
    li r5, 0
    bl mksyl
    cmpwi r3, 0
    blt append
    mr r31, r3
    addi r3, r15, -1
    mr r4, r30
    bl put
    mr r3, r15
    mr r4, r31
    bl put
    addi r15, r15, 1
    b ok
v_notsyl:
    addi r3, r17, -2351
    cmplwi r3, 29
    bgt v_vow
    addi r4, r20, {CHO_OF}
    lbzx r3, r4, r3
    cmpwi r3, 0xff
    beq append
    mr r4, r19
    li r5, 0
    bl mksyl
    cmpwi r3, 0
    blt append
    mr r4, r3
    addi r3, r15, -1
    b put_ok
v_vow:
    addi r3, r17, -2381
    cmplwi r3, 20
    bgt append
    bl virtual
    cmpwi r28, 0
    beq v_jamo
    mr r3, r23
    mr r4, r19
    bl vdouble
    cmpwi r3, 0
    blt v_jamo
    mr r23, r3
    bl lbput
    cmpwi r3, 0
    bne ok
v_jamo:
    addi r3, r17, -2381
    mr r4, r19
    bl vdouble
    cmpwi r3, 0
    blt append
    addi r4, r3, 2381
    addi r3, r15, -1
    b put_ok
append:
    cmplwi r15, 8
    bge fail
    mr r3, r15
    addi r4, r14, 2351
    bl put
    addi r15, r15, 1
    b ok
put_ok:
    bl put
ok:
    stb r15, {CNT_lo}(r21)
    li r3, 1
    b c_epi
fail:
    li r3, 0
c_epi:
    lmw r14, 8(r1)
    lwz r0, 0x64(r1)
    mtlr r0
    addi r1, r1, 0x60
    blr

# ===== decompose() → r3 = 1 처리함 / 0 원래 코드로 (마지막 글자가 음절 아님) =====
decompose:
    stwu r1, -0x60(r1)
    mflr r0
    stw r0, 0x64(r1)
    stmw r14, 8(r1)
    lis r20, {TBL_ha}
    addi r20, r20, {TBL_lo}
    lis r16, {BUF_ha}
    addi r16, r16, {BUF_lo}
    lis r21, {CNT_ha}
    lbz r15, {CNT_lo}(r21)
    addi r3, r15, -1
    slwi r3, r3, 1
    lhzx r3, r16, r3
    bl code2n
    cmplwi r3, 2350
    bge d_pass
    bl lvt
    mr r22, r3
    mr r23, r4
    mr r24, r5
d_loop:
    cmpwi r24, 0
    beq d_not
    addi r3, r20, {JS1}
    lbzx r24, r3, r24
    b d_try
d_not:
    addi r3, r20, {VS1}
    lbzx r3, r3, r23
    cmpwi r3, 0xff
    beq d_cho
    mr r23, r3
d_try:
    mr r3, r22
    mr r4, r23
    mr r5, r24
    bl mksyl
    cmpwi r3, 0
    blt d_loop
    mr r4, r3
    b d_put
d_cho:
    addi r3, r20, {CHO2K}
    lbzx r4, r3, r22
    addi r4, r4, 2351
d_put:
    addi r3, r15, -1
    bl put
    li r3, 1
    b d_epi
d_pass:
    li r3, 0
d_epi:
    lmw r14, 8(r1)
    lwz r0, 0x64(r1)
    mtlr r0
    addi r1, r1, 0x60
    blr

# ===== virtual: P(r17) = 낱자 모음, Q(r18). Q·P 가 KS 에 없어 떨어진 꼴이면 r28 = 음절 수(1·2),
#       끝 음절 r22~24, 앞 음절 r25~27. 아니면 r28 = 0. (r29 에 링크 보관) =====
virtual:
    mflr r29
    li r28, 0
    addi r23, r17, -2381
    addi r3, r18, -2351
    cmplwi r3, 29
    bgt vi_syl
    addi r4, r20, {CHO_OF}
    lbzx r22, r4, r3
    cmpwi r22, 0xff
    beq vi_ret
    li r24, 0
    li r28, 1
    b vi_ret
vi_syl:
    cmplwi r18, 2350
    bge vi_ret
    mr r3, r18
    bl lvt
    cmpwi r5, 0
    bne vi_t
    mr r22, r3
    mr r3, r4
    mr r4, r23
    bl vdouble
    cmpwi r3, 0
    blt vi_ret
    mr r23, r3
    li r24, 0
    li r28, 1
    b vi_ret
vi_t:
    mr r25, r3
    mr r26, r4
    addi r6, r20, {JS1}
    lbzx r27, r6, r5
    cmpwi r27, 0
    beq vi_single
    addi r6, r20, {JS2}
    lbzx r6, r6, r5
    b vi_mv
vi_single:
    addi r6, r20, {JONG2K}
    lbzx r6, r6, r5
vi_mv:
    addi r7, r20, {CHO_OF}
    lbzx r22, r7, r6
    li r24, 0
    li r28, 2
vi_ret:
    mtlr r29
    blr

# ===== lbput: virtual 결과(종·중 고친 뒤)를 Q·P 두 칸에 씀. 모두 KS 에 있을 때만. → r3 1/0 =====
lbput:
    mflr r29
    mr r3, r22
    mr r4, r23
    mr r5, r24
    bl mksyl
    cmpwi r3, 0
    blt lb_fail
    mr r30, r3
    cmpwi r28, 2
    bne lb_one
    mr r3, r25
    mr r4, r26
    mr r5, r27
    bl mksyl
    cmpwi r3, 0
    blt lb_fail
    mr r4, r3
    addi r3, r15, -2
    bl put
    addi r3, r15, -1
    mr r4, r30
    bl put
    b lb_ok
lb_one:
    addi r3, r15, -2
    mr r4, r30
    bl put
    addi r3, r15, -1
    slwi r3, r3, 1
    li r0, 0
    sthx r0, r16, r3
    addi r15, r15, -1
lb_ok:
    li r3, 1
    mtlr r29
    blr
lb_fail:
    li r3, 0
    mtlr r29
    blr

# ===== 잎 함수들 (r0, r3~r8 만 씀) =====
# code2n(r3 = SJIS 코드) → r3 = 순번 i (음절 0~2349, 띄어쓰기 2350, 자모 2351~2401…) 또는 -1
code2n:
    srwi r4, r3, 8
    clrlwi r5, r3, 24
    addi r4, r4, -0x88
    cmplwi r4, 13
    bgt c2n_bad
    cmplwi r5, 0x40
    blt c2n_bad
    cmplwi r5, 0x7f
    beq c2n_bad
    cmplwi r5, 0xfc
    bgt c2n_bad
    addi r5, r5, -0x40
    cmplwi r5, 0x40
    blt c2n_lo
    addi r5, r5, -1
c2n_lo:
    mulli r4, r4, 188
    add r3, r4, r5
    addi r3, r3, -94
    cmpwi r3, 0
    blt c2n_bad
    blr
c2n_bad:
    li r3, -1
    blr

# put(r3 = 칸, r4 = 순번 i): 버퍼(r16)+칸·2 에 i 의 SJIS 코드를 씀
put:
    addi r4, r4, 94
    li r5, 188
    divwu r6, r4, r5
    mullw r7, r6, r5
    subf r7, r7, r4
    cmplwi r7, 0x3f
    blt put_lo
    addi r7, r7, 1
put_lo:
    addi r7, r7, 0x40
    addi r6, r6, 0x88
    slwi r6, r6, 8
    or r6, r6, r7
    slwi r3, r3, 1
    sthx r6, r16, r3
    blr

# lvt(r3 = 음절 순번) → r3 초, r4 중, r5 종
lvt:
    slwi r3, r3, 1
    lhzx r3, r20, r3
    li r4, 28
    divwu r6, r3, r4
    mullw r7, r6, r4
    subf r5, r7, r3
    li r4, 21
    divwu r3, r6, r4
    mullw r7, r3, r4
    subf r4, r7, r6
    blr

# mksyl(r3 초, r4 중, r5 종) → r3 = 음절 순번 또는 -1 (음절표 이진 탐색)
mksyl:
    mulli r3, r3, 21
    add r3, r3, r4
    mulli r3, r3, 28
    add r3, r3, r5
    li r4, 0
    li r5, 2350
mk_loop:
    cmpw r4, r5
    bge mk_nf
    add r6, r4, r5
    srwi r6, r6, 1
    slwi r7, r6, 1
    lhzx r7, r20, r7
    cmpw r7, r3
    beq mk_f
    blt mk_lo
    mr r5, r6
    b mk_loop
mk_lo:
    addi r4, r6, 1
    b mk_loop
mk_f:
    mr r3, r6
    blr
mk_nf:
    li r3, -1
    blr

# vdouble(r3 = 앞 모음, r4 = 뒤 모음) → r3 = 겹모음 번호 또는 -1
vdouble:
    li r5, 0
vd_loop:
    cmplwi r5, 21
    bge vd_nf
    addi r6, r20, {VS1}
    lbzx r6, r6, r5
    cmpw r6, r3
    bne vd_nx
    addi r6, r20, {VS2}
    lbzx r6, r6, r5
    cmpw r6, r4
    bne vd_nx
    mr r3, r5
    blr
vd_nx:
    addi r5, r5, 1
    b vd_loop
vd_nf:
    li r3, -1
    blr
end_of_code:
'''


def assemble(tbl_va=None, src=ASM):
    """ASM 을 keystone 으로 조립. → (코드 바이트, 라벨 주소)."""
    from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
    blob, off = tables()
    if tbl_va is None: tbl_va = T2_VA + 0x1000   # 첫 조립(크기 재기)용 임시값
    v = dict(PANEL_ha=ha(PANEL), PANEL_lo=lo(PANEL), BUF_ha=ha(BUF), BUF_lo=lo(BUF), CNT_ha=ha(CNT), CNT_lo=lo(CNT),
             TBL_ha=ha(tbl_va), TBL_lo=lo(tbl_va), SND=SND, SND_DEL=SND + 4, SND_ERR=SND + 0x20, SND_FUNC=hex(SND_FUNC),
             SELECT_DONE=hex(SELECT_DONE), HOOK_SELECT_RET=hex(HOOK_SELECT_RET), DELETE_DONE=hex(DELETE_DONE),
             HOOK_DELETE_RET=hex(HOOK_DELETE_RET), SPACE_YES=hex(SPACE_YES), SPACE_NO=hex(SPACE_NO),
             END_MOVE=hex(END_MOVE), END_SKIP=hex(END_SKIP), **off)
    text = src.format(**v)
    lines = []
    for ln in text.splitlines():
        ln = ln.split('#')[0].rstrip()
        if not ln.strip(): continue
        lines.append(re.sub(r'\br(\d+)\b', r'%r\1', ln))
    ks = Ks(KS_ARCH_PPC, KS_MODE_PPC32 | KS_MODE_BIG_ENDIAN)
    # 라벨 주소: 줄마다 4바이트(이 원본엔 의사 명령이 없다).
    # keystone 은 여러 줄 조립에서 절대 주소 분기(b 0x8000C9A8)를 잘못 계산하므로 nop 으로 두고 뒤에서 직접 넣는다.
    labels = {}; pc = T2_VA; far = []
    for n, ln in enumerate(lines):
        m = re.match(r'^(\w+):$', ln.strip())
        if m: labels[m.group(1)] = pc; continue
        m = re.match(r'^\s*(bl?)\s+0x([0-9a-fA-F]+)$', ln)
        if m:
            far.append((pc, m.group(1) == 'bl', int(m.group(2), 16))); lines[n] = '    nop'
        pc += 4
    enc, _ = ks.asm('\n'.join(lines), T2_VA)
    code = bytearray(enc)
    assert len(code) == labels['end_of_code'] - T2_VA, (len(code), hex(labels['end_of_code']))
    for at, link, dst in far:
        o = at - T2_VA
        assert code[o:o + 4] == b'\x60\x00\x00\x00'
        struct.pack_into('>I', code, o, b_insn(at, dst) | link)
    return bytes(code), labels


def build_t2():
    """→ (T2 섹션 바이트 0x2000, 라벨 주소, 표 주소)."""
    blob, off = tables()
    code, _ = assemble()
    tbl_va = (T2_VA + len(code) + 0x1F) & ~0x1F
    code, labels = assemble(tbl_va)
    sec = bytearray(T2_SIZE)
    sec[:len(code)] = code
    t = tbl_va - T2_VA
    assert t + len(blob) <= T2_SIZE, hex(t + len(blob))
    sec[t:t + len(blob)] = blob
    labels['TBL'] = tbl_va
    for k, o in off.items(): labels['TBL_' + k] = tbl_va + o
    labels['TBL_END'] = tbl_va + len(blob)
    return bytes(sec), labels


def b_insn(src, dst):
    d = dst - src
    assert -0x2000000 <= d < 0x2000000 and d % 4 == 0
    return 0x48000000 | (d & 0x3FFFFFC)


def patch(dol):
    """원본 main.dol → 패치된 main.dol (bytes)."""
    assert len(dol) == DOL_SIZE, hex(len(dol))
    d = bytearray(dol)
    f = lambda va: va - 0x80003000          # T1·D3: 파일 오프셋 = VA − 0x80003000

    def word(va): return struct.unpack_from('>I', d, f(va))[0]

    def put(va, w): struct.pack_into('>I', d, f(va), w)

    for va, w in ORIG.items():
        assert word(va) == w, ('원본이 아님', hex(va), hex(word(va)))
    assert bytes(d[f(PANEL0_VA):f(PANEL0_VA) + 2]) == b'\x82\xa0' and d[f(PANEL0_VA) + 132] == 0
    # DOL 헤더: T2 칸이 비어 있어야 함
    assert struct.unpack_from('>I', d, 0x08)[0] == 0 and struct.unpack_from('>I', d, 0x50)[0] == 0 \
        and struct.unpack_from('>I', d, 0x98)[0] == 0
    sec, L = build_t2()
    struct.pack_into('>I', d, 0x08, T2_OFF)
    struct.pack_into('>I', d, 0x50, T2_VA)
    struct.pack_into('>I', d, 0x98, T2_SIZE)
    for va, w in ARENA.items(): put(va, w)
    put(HOOK_SELECT, b_insn(HOOK_SELECT, L['hook_select']))
    put(HOOK_DELETE, b_insn(HOOK_DELETE, L['hook_delete']))
    put(HOOK_SPACE, b_insn(HOOK_SPACE, L['hook_space']))
    put(HOOK_END, b_insn(HOOK_END, L['hook_end']))
    pb = panel0_bytes(); assert pb == PANEL0_BYTES_DOC
    d[f(PANEL0_VA):f(PANEL0_VA) + 132] = pb
    put(SKIP_PTR_VA, SKIP_PTR_NEW)
    assert bytes(d[f(SKIP_PTR_NEW):f(SKIP_PTR_NEW) + 4]) == b'\x0a\x04\xff\xff'
    d += sec
    return bytes(d), L


def listing(code_va=T2_VA):
    """조립 결과 분해 목록(검토용)."""
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
    sec, L = build_t2()
    inv = {}
    for k, v in L.items(): inv.setdefault(v, []).append(k)
    md = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    code_end = L['end_of_code'] - T2_VA
    out = []
    for i in md.disasm(sec[:code_end], code_va):
        for n in inv.get(i.address, []):
            if not n.startswith('TBL'): out.append('%s:' % n)
        w = sec[i.address - code_va:i.address - code_va + 4].hex()
        out.append('  %08x: %s  %s %s' % (i.address, w, i.mnemonic, i.op_str))
    return out, L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', help='패치된 main.dol 을 쓸 경로')
    ap.add_argument('--asm', help='T2 루틴 분해 목록을 쓸 경로')
    a = ap.parse_args()
    import disc
    dol = disc.read('sys/main.dol')
    new, L = patch(dol)
    open(a.out, 'wb').write(new)
    code_len = L['end_of_code'] - T2_VA
    print('main.dol %d → %d 바이트, T2 루틴 %d B(0x%X), 표 0x%08X~0x%08X(%d B), 섹션 0x%X 중 %d B 사용' % (
        len(dol), len(new), code_len, code_len, L['TBL'], L['TBL_END'], L['TBL_END'] - L['TBL'],
        T2_SIZE, L['TBL_END'] - T2_VA))
    if a.asm:
        lines, _ = listing()
        open(a.asm, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
