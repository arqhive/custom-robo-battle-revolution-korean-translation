"""/bmg/info.bin (파츠·로보 설명) 읽기·쓰기·추출.

구조: u32 개수 N, u32 오프셋 N개, u32 파일 전체 크기, u32 0, (첫 블록까지 0), 블록 N개.
전체 크기 칸을 안 고치면 게임이 멈춘다(10/23 시험 ISO, 메모리 카드 안내 뒤 멈춤).
블록마다 BMG(MESGbmg1). 영문판 짝은 /bmg/info_usa.bin(블록 수 같음).

    python tools/info_bin.py check     # 일본판·영문판 무변경 왕복 검사
    python tools/info_bin.py extract   # work/translation/info-jp.json
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import bmg, disc


def split(b):
    n = struct.unpack('>I', b[:4])[0]
    offs = list(struct.unpack('>%dI' % n, b[4:4 + 4 * n]))
    ends = offs[1:] + [len(b)]
    return {'pre': b[4 + 4 * n:offs[0]].hex(), 'blocks': [bmg.read(b[s:e]) for s, e in zip(offs, ends)]}


def join(info):
    blobs = [bmg.write(x) for x in info['blocks']]
    n = len(blobs); pre = bytearray.fromhex(info['pre'])
    o = 4 + 4 * n + len(pre); tab = []
    for x in blobs:
        tab.append(o); o += len(x)
    pre[0:4] = struct.pack('>I', o)  # 파일 전체 크기
    return struct.pack('>I', n) + struct.pack('>%dI' % n, *tab) + bytes(pre) + b''.join(blobs)


def check():
    for p in ('/bmg/info.bin', '/bmg/info_usa.bin'):
        b = disc.read(p)
        print(p, len(b), '왕복 일치' if join(split(b)) == b else '왕복 불일치')


def extract():
    jp = split(disc.read('/bmg/info.bin'))['blocks']
    us = split(disc.read('/bmg/info_usa.bin'))['blocks']
    assert len(jp) == len(us)
    out = []
    for bi, (a, b) in enumerate(zip(jp, us)):
        ea, eb = a['inf']['entries'], b['inf']['entries']
        for k, e in enumerate(ea):
            en = eb[k].get('text') if k < len(eb) else None
            out.append({'id': 'info:%02d:%03d' % (bi, k), 'block': bi, 'no': k, 'jp': e.get('text', ''), 'en': en})
    dst = os.path.join(disc.ROOT, 'work/translation/info-jp.json')
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cnt = [len(x['inf']['entries']) for x in jp], [len(x['inf']['entries']) for x in us]
    print('항목', len(out), '빈 것 아님', sum(1 for x in out if x['jp']), '블록별 항목 수 같음', cnt[0] == cnt[1])


if __name__ == '__main__':
    {'check': check, 'extract': extract}[sys.argv[1]]()
