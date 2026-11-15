"""원본 ISO에서 파일을 꺼내는 공용 도구 (읽기 전용).

    import disc
    b = disc.read('/bmg/info.bin')      # FST 경로
    dol = disc.read('sys/main.dol')

`python tools/disc.py <경로> <저장할 파일>` 로 하나를 꺼낼 수도 있다.
파일 위치는 manifests/file-list.json 을 쓴다.
"""
import json, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISO = os.path.join(ROOT, 'Custom Robo - Battle Revolution (Japan).iso')
_man = None


def manifest():
    global _man
    if _man is None:
        _man = json.load(open(os.path.join(ROOT, 'manifests/file-list.json'), encoding='utf-8'))
    return _man


def entry(path):
    m = manifest()
    for x in m['files'] + m['system_files']:
        if x['path'] == path:
            return x
    raise KeyError(path)


def dol_size(f, off):
    """DOL 헤더(텍스트 7·데이터 11 섹션)에서 파일 끝을 구한다."""
    f.seek(off); h = f.read(0x100)
    offs = struct.unpack('>18I', h[:0x48]); sizes = struct.unpack('>18I', h[0x90:0xD8])
    return max(o + s for o, s in zip(offs, sizes) if s)


def read(path):
    x = entry(path)
    with open(ISO, 'rb') as f:
        size = x.get('size') or dol_size(f, x['offset'])
        f.seek(x['offset'])
        return f.read(size)


def paths(prefix=''):
    return [x['path'] for x in manifest()['files'] if x['path'].startswith(prefix)]


if __name__ == '__main__':
    open(sys.argv[2], 'wb').write(read(sys.argv[1]))
