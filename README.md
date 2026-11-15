# 커스텀 로보 배틀 레볼루션 (GC) 한글 패치

*Custom Robo Battle Revolution* (게임큐브, 일본판 `GXCJ01`) 비공식 한국어 팬 패치입니다.
일본판(『カスタムロボ バトルレボリューション』) 원문을 기준으로 번역했고, 1편·V2·GX 한글 패치와 용어·말투를 이어 맞췄습니다.

**제작: arqhive** · **최신 버전: [v1.0f](../../releases/tag/v1.0f)**

**소개 페이지: [arqhive 한글 패치 아카이브](https://arqhive.vercel.app/korean-translation/custom-robo-battle-revolution)**

- 본편 대사, 선택지, 메뉴, 파츠 이름과 설명, 도움말, 공략 조언, 홀로세움 설명, 시스템 안내를 한글화했습니다.
- 모드 선택·이름 입력 화면의 그림 글씨, 마을의 지역 이름판(3D), 간판 그림을 한글화했습니다.
- 주인공 이름을 한글로 입력할 수 있습니다(자모를 골라 글자를 조합합니다).
- 원작에서도 영어인 문구는 영어 그대로 두었습니다.
- **파일 단위 패처**라서 덤프마다 이미지 해시가 달라도 게임 파일만 같으면 적용됩니다.

> 이 저장소에는 **게임 데이터(디스크 이미지, 추출한 원문 대사, 원본 그래픽, 스크린샷)가 들어 있지 않습니다.**
> 패치를 적용하려면 본인이 소유한 게임에서 직접 덤프한 원본이 필요합니다.

## 사용자용: 패치 적용

### 준비물

- 일본판 디스크 이미지(`GXCJ01`). 북미판(*Custom Robo*)에는 적용할 수 없습니다.
- Windows 10 이상. 따로 설치할 것은 없습니다.
- 빈 공간 약 1.5GB.

### 지원 형식

| 원본 | 결과 |
|---|---|
| ISO, GCM | ISO |
| CISO, WIA, WDF, GCZ | ISO (동봉한 wit으로 바꾼 뒤 적용) |
| RVZ, NKit | 지원 안 함. Dolphin 등에서 ISO로 바꾼 뒤 적용 |

### 적용 방법

1. [릴리즈 페이지](../../releases/latest)에서 `GXCJ_KPatch_v<버전>.zip`을 받아 압축을 풉니다.
2. 원본 이미지를 `패치하기.bat` 위에 끌어다 놓거나, 같은 폴더에 넣고 `패치하기.bat`을 더블클릭합니다.
3. 원본과 같은 폴더에 `Custom Robo Battle Revolution (Korean) [GXCJ01].iso`가 생깁니다. 원본은 바뀌지 않습니다.

### 실행 환경

- **확인함**: Dolphin, Wii U Nintendont(USB Loader GX).

### 알려진 문제

- 세이브 파일 이름과 디스크 배너는 본체 메모리 카드 화면의 글꼴에 한글이 없어 일본어 그대로 두었습니다.
- 오프닝 영상 속 대사창과 GBA 연동 화면 문구는 일본어 그대로입니다.

## 개발자용

- 번역문: [`translation/`](translation)에 묶음별 한국어 번역문(ID → 번역)만 들어 있습니다. `{1A:…}`는 원문 제어 코드(이름 칸 `FE0008`, 글자 색 `FF0000…`, 글자 크기 `FF0001…`, 쪽 넘김 `FE000301` 등)라 그대로 둡니다. `⟪…⟫` 안의 글자는 좁은 글꼴로 바뀝니다.
- 도구: [`tools/`](tools)에 분석·추출·글꼴·빌드·검사 도구 소스가 있고, [`patcher/`](patcher)와 [`tools/make_patcher.py`](tools/make_patcher.py)가 배포 패처입니다(Python 3.13, Pillow, fontTools, unicorn, shapely, mapbox_earcut).
- 일본어 원문 추출본, 그림 작업 파일, 작업 상태 기록은 게임 데이터이거나 작업용이라 넣지 않았습니다. 그래서 이 저장소만으로는 바로 빌드되지 않고, 원본 이미지에서 추출부터 다시 해야 합니다.

## 변경 내역

전체 내역은 [`CHANGELOG.md`](CHANGELOG.md)에 있습니다.

## 크레딧·라이선스

- 이 저장소의 도구 코드, 한국어 번역문, 문서: [MIT License](LICENSE) (© 2026 arqhive).
- 글꼴: G마켓 산스(SIL OFL 1.1, [`licenses/GmarketSans-OFL.txt`](licenses/GmarketSans-OFL.txt)). 글꼴 파일은 저장소에 포함하지 않습니다.
- 패처 동봉 도구: wit v3.05a(GPL-2.0), xdelta3 3.1.0(Apache-2.0). 저장소에는 포함하지 않습니다.

## 면책

비공식 팬 번역이며 Nintendo, Noise와 관련이 없습니다. 「커스텀 로보」 관련 상표·저작권은 각 권리자에게 있습니다.
패치를 적용한 게임 파일의 배포를 금지합니다.
