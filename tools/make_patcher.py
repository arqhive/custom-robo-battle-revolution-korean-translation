"""게임큐브 파일 단위 패처 zip 만들기(patcher/ + data/ + bin/). 치비로보 GC 패처에서 가져와 일반화.

빌드(tools/build_iso.py)는 원본 이미지에서 이렇게 바꾼다.
  - 헤더 0x420~0x42F(실행 파일·FST 위치·크기)
  - 커진 main.dol 은 원래 자리, FST 는 그 바로 뒤로
  - 바뀐 파일은 제자리(원래 크기 이하)나 앞쪽 빈 영역(커진 것)으로
  - 옮긴 파일의 옛 자리·작아진 파일의 꼬리는 0
패처는 원본 이미지를 통째로 복사한 뒤 ① 0으로 채울 구간 ② 바뀐 파일 차분(xdelta) ③ 새 FST ④ 헤더를 쓴다.
이 스크립트는 같은 순서로 결과를 흉내 내 빌드 ISO 와 바이트까지 같은지 확인한 뒤 zip 을 만든다.

사용: python -X utf8 tools/make_patcher.py 빌드.iso 버전
"""
import hashlib, shutil, struct, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIG = ROOT / 'Custom Robo - Battle Revolution (Japan).iso'
BIN = ROOT / 'tools/bin'
XDELTA = (BIN / 'xdelta3.exe').resolve()
GAMEID, CODE, TITLE, RESULT = 'GXCJ01', 'GXCJ', '커스텀 로보 배틀 레볼루션', 'Custom Robo Battle Revolution (Korean) [GXCJ01]'
CH = 1 << 24


def md5(b): return hashlib.md5(b).hexdigest()


def at(f, off, n): f.seek(off); b = f.read(n); assert len(b) == n; return b


def dol_size(dol):
    offs = struct.unpack('>18I', dol[:72]); sizes = struct.unpack('>18I', dol[0x90:0xd8])
    return max(o + s for o, s in zip(offs, sizes) if s)


def fst_files(fst):
    n = struct.unpack_from('>I', fst, 8)[0]; strs = n * 12; out = {}
    def name(o): return fst[strs + o:fst.index(b'\0', strs + o)].decode('cp932')
    def walk(i, stop, pre):
        while i < stop:
            flag = fst[i * 12]; no = int.from_bytes(fst[i * 12 + 1:i * 12 + 4], 'big')
            a, b = struct.unpack_from('>II', fst, i * 12 + 4)
            if flag: walk(i + 1, b, pre + name(no) + '/'); i = b
            else: out[pre + name(no)] = (a, b); i += 1
    walk(1, n, ''); return out


def image(f):
    head = at(f, 0, 0x440); doff, fo, fsz = struct.unpack_from('>3I', head, 0x420)
    fst = at(f, fo, fsz); dol = at(f, doff, 0x100); dol = at(f, doff, dol_size(dol))
    return head, fo, fst, fst_files(fst), doff, dol


def main():
    build, version = Path(sys.argv[1]), sys.argv[2]
    size = ORIG.stat().st_size
    assert build.stat().st_size == size
    fo_, fb = open(ORIG, 'rb'), open(build, 'rb')
    oh, ofo, ofst, ofiles, odoff, odol, = image(fo_)
    nh, nfo, nfst, nfiles, ndoff, ndol = image(fb)
    assert oh[:0x420] == nh[:0x420] and set(ofiles) == set(nfiles)
    assert ndoff == odoff and ndoff + len(ndol) <= nfo, '실행 파일은 원래 자리, FST 는 그 뒤(UWUVCI)'
    rows = [('dol', 'main.dol', odol, ndol, ndoff)]
    for rel in sorted(nfiles, key=lambda k: nfiles[k][0]):
        a, b = at(fo_, *ofiles[rel]), at(fb, *nfiles[rel])
        if a != b or ofiles[rel][0] != nfiles[rel][0]:
            rows.append(('raw', rel, a, b, nfiles[rel][0]))
    rows.append(('fst', 'fst.bin', ofst, nfst, nfo))
    writes = [(pos, b) for _, _, _, b, pos in rows] + [(0x420, nh[0x420:0x430])]

    # 흉내: 원본 + 쓰기 → 빌드와 다른 구간을 찾는다(빌드 쪽이 전부 0이어야 함 → 0으로 채울 구간)
    def sim_diff(zeros):
        diffs = []
        for c0 in range(0, size, CH):
            n = min(CH, size - c0); s = bytearray(at(fo_, c0, n))
            for z0, zl in zeros:
                a0, a1 = max(z0, c0), min(z0 + zl, c0 + n)
                if a0 < a1: s[a0 - c0:a1 - c0] = bytes(a1 - a0)
            for p, b in writes:
                a0, a1 = max(p, c0), min(p + len(b), c0 + n)
                if a0 < a1: s[a0 - c0:a1 - c0] = b[a0 - p:a1 - p]
            t = at(fb, c0, n)
            if s != t:
                i = 0
                while i < n:
                    if s[i] != t[i]:
                        j = i
                        while j < n and s[j] != t[j]: j += 1
                        if diffs and diffs[-1][0] + diffs[-1][1] == c0 + i: diffs[-1] = (diffs[-1][0], diffs[-1][1] + j - i)
                        else: diffs.append((c0 + i, j - i))
                        i = j
                    else: i += 1
        return diffs
    d = sim_diff([])
    # 다른 구간을 빌드 기준으로 넓혀 「빌드가 0」인 연속 구간으로 만든다(0 바이트끼리는 같아서 끊겨 보일 수 있음)
    zeros = []
    for p, l in d:
        assert not any(at(fb, p, l)), ('빌드 쪽이 0이 아닌 차이', hex(p), l)
        if zeros and p - (zeros[-1][0] + zeros[-1][1]) < 0x10000 and not any(at(fb, zeros[-1][0] + zeros[-1][1], p - zeros[-1][0] - zeros[-1][1])):
            zeros[-1] = (zeros[-1][0], p + l - zeros[-1][0])
        else: zeros.append((p, l))
    assert sim_diff(zeros) == [], '흉내 결과가 빌드와 다름'
    print('0으로 채울 구간', [(hex(p), l) for p, l in zeros])

    name = f'{CODE}_KPatch_v{version}'
    out = ROOT / 'release' / name
    if out.exists(): shutil.rmtree(out)
    (out / 'data').mkdir(parents=True); (out / 'bin').mkdir()
    manifest = ['\t'.join(['zero', '-', str(l), '-', '-', str(p)]) for p, l in zeros]
    with tempfile.TemporaryDirectory() as tmp:
        for i, (mode, rel, a, b, pos) in enumerate(rows):
            src, dst, patch = Path(tmp, 'a'), Path(tmp, 'b'), out / 'data' / f'{i:03d}.xdelta'
            src.write_bytes(a); dst.write_bytes(b)
            subprocess.run([str(XDELTA), '-e', '-9', '-S', 'djw', '-A=', '-B', '268435456', '-f', '-s', str(src), str(dst), str(patch)], check=True)
            manifest.append('\t'.join([mode, patch.name, rel, md5(a), md5(b), str(pos)]))
    h = hashlib.md5(); fb.seek(0)
    while chunk := fb.read(CH): h.update(chunk)
    config = {'id': GAMEID, 'rev': str(oh[7]), 'title': TITLE, 'version': version, 'result': RESULT,
              'disc_size': str(size), 'fst_md5': md5(ofst), 'dol_size': str(len(odol)),
              'hdr420': nh[0x420:0x430].hex(), 'result_md5': h.hexdigest()}
    (out / 'data/config.txt').write_text(''.join(f'{k}={v}\n' for k, v in config.items()), encoding='utf-8')
    (out / 'data/manifest.txt').write_text('\n'.join(manifest) + '\n', encoding='utf-8')
    ps1 = (ROOT / 'patcher/patch.ps1').read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\n', '\r\n')
    (out / 'patch.ps1').write_bytes(b'\xef\xbb\xbf' + ps1.encode('utf-8'))
    bat = (ROOT / 'patcher/패치하기.bat').read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    (out / '패치하기.bat').write_bytes(bat)
    shutil.copy(ROOT / 'patcher/README.txt', out / 'README.txt')
    for f in BIN.iterdir(): shutil.copy(f, out / 'bin' / f.name)
    zpath = out.parent / (out.name + '.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file(): z.write(f, f.relative_to(out.parent).as_posix())
    print(zpath, zpath.stat().st_size, config['result_md5'])
    for m in manifest: print(m)


if __name__ == '__main__':
    main()
