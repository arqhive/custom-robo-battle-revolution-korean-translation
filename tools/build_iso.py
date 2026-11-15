"""GC ISO 재조립(기프트피아 tools/build_iso.py 에서 가져옴): 바뀌지 않은 파일은 원래 위치에 그대로 두고(음성 32KB 정렬·읽기 위치 보존),
바뀐 파일은 원래 자리에 들어가면 제자리, 커졌으면 FST 뒤 빈 영역(GXCJ01 원본은 약 474MB 비어 있음)에 32바이트 정렬로 넣는다.
파일 사이 빈틈의 원본 바이트도 옮겨 적는다(GXCJ01 은 TITLE_MODEL.dat 뒤 28KB 에 남은 데이터가 있음) → 무변경이면 원본과 MD5 같음.
경로는 FST 기준 앞 '/' 없이(예: message/font.out). --repdir build/files 로 쓴다.

사용: python build_iso.py <원본.iso> <출력.iso> [--dol main.dol] [--repdir DIR] [--rep 디스크경로=로컬파일 ...]
                [--add 루트파일이름=로컬파일 ...]
  --repdir DIR : DIR 아래 같은 상대경로(예: Data/Strings/x.str) 파일이 있으면 교체
  --add        : 디스크 루트에 새 파일 추가(FST 끝에 항목을 덧붙이고 boot.bin 의 FST 크기 갱신)
"""
import argparse
import os
import struct

DISC_SIZE = 1459978240


def read_fst(f):
    f.seek(0)
    h = f.read(0x440)
    dol_off, fst_off, fst_size = struct.unpack('>III', h[0x420:0x42C])
    f.seek(fst_off)
    fst = bytearray(f.read(fst_size))
    n = struct.unpack('>I', fst[8:12])[0]
    strtab = bytes(fst[n * 12:])
    ents = []
    stack = [(n, '')]
    for i in range(1, n):
        while i >= stack[-1][0]:
            stack.pop()
        no = struct.unpack('>I', fst[i * 12:i * 12 + 4])[0] & 0xFFFFFF
        name = strtab[no:strtab.index(b'\0', no)].decode('shift_jis')
        a, b = struct.unpack('>II', fst[i * 12 + 4:i * 12 + 12])
        p = stack[-1][1] + name
        if fst[i * 12]:
            stack.append((b, p + '/'))
        else:
            ents.append((i, p, a, b))
    return dol_off, fst_off, fst, ents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--dol'); ap.add_argument('--repdir')
    ap.add_argument('--rep', nargs='*', default=[])
    ap.add_argument('--add', nargs='*', default=[])
    a = ap.parse_args()
    rep = dict(r.split('=', 1) for r in a.rep)
    add = [r.split('=', 1) for r in a.add]

    f = open(a.src, 'rb')
    dol_off, fst_off, fst, ents = read_fst(f)
    added = []
    if add:
        # 루트 바로 뒤(1번)에 끼워 넣는다. 폴더 항목의 부모·다음 번호와 기존 파일 번호를 그만큼 민다.
        n = struct.unpack('>I', fst[8:12])[0]; m = len(add)
        old = [list(struct.unpack('>III', fst[k * 12:k * 12 + 12])) for k in range(n)]
        strtab = bytearray(fst[n * 12:])
        for k in range(1, n):
            if old[k][0] >> 24:  # 폴더: [이름|플래그, 부모, 다음]
                if old[k][1] >= 1: old[k][1] += m
                old[k][2] += m
        new_ents = []
        for j, (name, local) in enumerate(add):
            new_ents.append([len(strtab), 0, 0]); strtab += name.encode('ascii') + bytes(1)
            added.append((1 + j, name, local))
        rows = [old[0]] + new_ents + old[1:]
        rows[0][2] = n + m
        fst = bytearray(b''.join(struct.pack('>III', *r) for r in rows) + strtab)
        ents = [(i + m, p, a, b) for i, p, a, b in ents]
    ents.sort(key=lambda e: e[2])
    first = ents[0][2]
    f.seek(0)
    head = bytearray(f.read(first))
    if a.dol:
        dol = open(a.dol, 'rb').read()
        if dol_off + len(dol) > fst_off:
            # 실행 파일이 커져 FST 자리를 덮으면 FST 를 실행 파일 바로 뒤(0x100 정렬)로 옮긴다(boot.bin 0x424 갱신)
            new_fst = (dol_off + len(dol) + 0xFF) & ~0xFF
            assert new_fst + len(fst) <= first, 'FST 옮길 자리 없음'
            print('FST 옮김', hex(fst_off), '->', hex(new_fst))
            fst_off = new_fst
            struct.pack_into('>I', head, 0x424, fst_off)
        head[dol_off:dol_off + len(dol)] = dol

    if added:
        struct.pack_into('>II', head, 0x428, len(fst), max(len(fst), struct.unpack('>I', head[0x42C:0x430])[0]))
    out = open(a.dst, 'wb')
    out.write(head)
    free_pos = (fst_off + len(fst) + 0x7FFF) & ~0x7FFF  # 앞쪽 빈 영역 시작
    free_end = first
    changed = moved = 0
    for i, p, off, size in ents:
        src = rep.get(p)
        if src is None and a.repdir and os.path.isfile(os.path.join(a.repdir, p)):
            src = os.path.join(a.repdir, p)
        if src:
            data = open(src, 'rb').read(); changed += 1
            if len(data) <= size:
                pos = off
            else:
                pos = (free_pos + 31) & ~31
                assert pos + len(data) <= free_end, '앞쪽 빈 영역 부족'
                free_pos = pos + len(data); moved += 1
        else:
            f.seek(off); data = f.read(size); pos = off
        out.seek(pos); out.write(data)
        struct.pack_into('>II', fst, i * 12 + 4, pos, len(data))
        if p == 'default.dol' and pos != dol_off:                 # 실행 파일이 커져 옮겨지면 boot.bin 의 실행 파일 위치(0x420)도 고친다
            out.seek(0x420); out.write(struct.pack('>I', pos))
            print('실행 파일 옮김', hex(dol_off), '->', hex(pos))
    for i, name, local in added:
        data = open(local, 'rb').read()
        pos = (free_pos + 31) & ~31
        assert pos + len(data) <= free_end, '앞쪽 빈 영역 부족'
        free_pos = pos + len(data)
        out.seek(pos); out.write(data)
        struct.pack_into('>II', fst, i * 12 + 4, pos, len(data))
        print('추가', name, hex(pos), len(data))
    # 원래 자리에 있던 파일들 사이 빈틈(원본 바이트)을 그대로 옮긴다. 제자리에 들어간 파일이 원래보다 작아진 꼬리는 건드리지 않는다.
    for (_, _, o1, s1), (_, _, o2, _) in zip(ents, ents[1:]):
        if o2 > o1 + s1:
            f.seek(o1 + s1); gap = f.read(o2 - o1 - s1)
            if any(gap):
                out.seek(o1 + s1); out.write(gap)
    out.seek(DISC_SIZE - 1); out.write(bytes(1))
    out.seek(fst_off); out.write(fst)
    out.close()
    print(f'교체 {changed}개(옮김 {moved}개), 앞쪽 빈 영역 남음 {(free_end - free_pos)/1e6:.1f}MB')



if __name__ == '__main__':
    main()
