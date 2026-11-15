"""공개 저장소 트리 만들기: 도구·패처·한국어 번역(ID→번역만)·문서만 복사한다.
원문 추출본·작업 기록(work/translation/batches, out/, notes, docs/ 등)·그림·글꼴·게임 데이터는 넣지 않는다.

사용: python -X utf8 tools/make_public.py 출력폴더
  출력폴더에 .git 이 있으면 그대로 두고 나머지만 지운 뒤 다시 채운다.
"""
import json, os, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / 'public'          # README.md·CHANGELOG.md·LICENSE·.gitignore·.gitattributes 원본


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for p in out.iterdir():
        if p.name == '.git': continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for f in PUB.iterdir():
        shutil.copy(f, out / f.name)
    # 도구: tools/*.py 만(글꼴·실행 파일·캐시 제외)
    (out / 'tools').mkdir()
    for f in sorted((ROOT / 'tools').glob('*.py')):
        shutil.copy(f, out / 'tools' / f.name)
    shutil.copytree(ROOT / 'patcher', out / 'patcher')
    shutil.copytree(ROOT / 'licenses', out / 'licenses')
    # 번역: 묶음마다 translations 만(메모 notes 는 원문 인용이 있어 뺌)
    src = ROOT / 'work/translation/redo'; dst = out / 'translation'; dst.mkdir()
    n = 0
    for f in sorted(src.glob('*.json')):
        d = json.load(open(f, encoding='utf-8'))
        tr = d['translations']; n += len(tr)
        (dst / f.name).write_text(json.dumps({'translations': tr}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('도구', len(list((out / 'tools').iterdir())), '번역 묶음', len(list(dst.iterdir())), '항목', n)


if __name__ == '__main__':
    main()
