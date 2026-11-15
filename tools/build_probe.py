"""2단계 한글 출력 시험: 글꼴 + 몇 줄만 한국어로 바꾼 파일을 build/files 에 만들고, --iso 면 ISO 까지.

바꾸는 곳
- /message/font.out : 맑은 고딕 Bold 고정 폭 한글 2,350자 + 띄어쓰기(font_ko)
- /scenario_jp/snr_t_01.bmg 0·1·9·11·16번 : 이야기 첫 장면(면접). 강조색 FF0000 03/04, 선택지 FE0007 포함. 후리가나(FF0002)는 뺀다.
- /bmg/info.bin 6블록 0·5번 : 모드 선택 「シナリオモード」 이름과 설명

    python tools/build_probe.py          # build/files 만
    python tools/build_probe.py --iso    # + build/GXCJ01_KO_probe.iso
    --font tools/fonts/Jua.ttf           # 글꼴 바꿔 보기(기본 맑은 고딕 Bold)
"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import bmg, disc, font_ko, info_bin, kotext

OUT = os.path.join(disc.ROOT, 'build/files')
RUBY = re.compile(r'\{1A:FF0002[0-9A-F]*\}')

DLG = {  # snr_t_01 번호: (원문 확인용 앞부분, 한국어)
    0: ('{1A:FE00060400}', '{1A:FE00060400}네가 지원한 아이냐.\n그럼 바로 면접을 시작하지.'),
    1: ('…', '…너는\n{1A:FF000003}바운티 헌터{1A:FF000004} 일을\n해 본 적이 있나?'),
    9: ('{1A:FE00060001}', '{1A:FE00060001}{1A:FE00070001}물론입니다!\n{1A:FE00070100}아니요, 처음입니다!\n'
                           '{1A:FE00070200}…아마…해 본 적 있다{1A:FE000301}'),
    11: ('{1A:FE00060002}', '{1A:FE00060002}물론입니다!'),
    16: ('{1A:FE00060002}', '{1A:FE00060002}아니요, 처음입니다!'),
}
INFO = {  # (블록, 번호): 한국어
    (6, 0): '시나리오 모드',
    (6, 5): '마을의 치안을 지키는\n커맨더가 되어\n동료와 함께 활약하는\nRPG를 즐길 수 있습니다.\n1인 플레이 전용입니다.\n'
            '손에 넣은 로보와\n무기 파츠는\n아케이드 모드와\n대전 모드에서\n사용할 수 있습니다.',
}


def tags(s):
    return re.findall(r'\{1A:(?!FF0002)[0-9A-F]*\}', s)


def write(path, data):
    p = os.path.join(OUT, path.lstrip('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(data)
    print('씀', path, len(data))


def main():
    font = sys.argv[sys.argv.index('--font') + 1] if '--font' in sys.argv else os.path.join(disc.ROOT, 'tools/fonts/malgunbd.ttf')
    buf, _, _, n = font_ko.build(font, 22)
    print('글꼴', font)
    write('/message/font.out', bytes(buf))

    b = bmg.read(disc.read('/scenario_jp/snr_t_01.bmg'))
    ents = b['inf']['entries']
    for k, (head, ko) in DLG.items():
        jp = ents[k]['text']
        assert jp.startswith(head), (k, jp)
        assert tags(RUBY.sub('', jp)) == tags(ko), ('제어 코드 다름', k, tags(jp), tags(ko))
        ents[k]['text'] = kotext.to_game(ko)
    write('/scenario_jp/snr_t_01.bmg', bmg.write(b))

    info = info_bin.split(disc.read('/bmg/info.bin'))
    for (bi, k), ko in INFO.items():
        e = info['blocks'][bi]['inf']['entries'][k]
        assert tags(e['text']) == tags(ko), (bi, k)
        e['text'] = kotext.to_game(ko)
    write('/bmg/info.bin', info_bin.join(info))

    if '--iso' in sys.argv:
        dst = os.path.join(disc.ROOT, 'build/GXCJ01_KO_probe.iso')
        subprocess.run([sys.executable, os.path.join(disc.ROOT, 'tools/build_iso.py'), disc.ISO, dst, '--repdir', OUT], check=True)


if __name__ == '__main__':
    main()
