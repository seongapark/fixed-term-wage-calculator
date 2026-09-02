# 통계조사관 임금계산 — 작업 지침

## 테스트

저장소 루트에서:

```bash
python -m pytest wage_calculator/tests -q
```

전부 통과해야 커밋한다. 일부 웹앱 테스트는 `demo_assets/`의 예시 xlsx를 직접 읽는데,
**이 폴더는 gitignore 대상**이라 다른 PC에서 clone하면 그 테스트는 돌지 않는다.

앱을 띄워 확인할 때 `python wage_calculator/main.py`는 창이 세션을 붙잡는다. 대신
uvicorn으로 `webapp.server.create_app(AppState())`를 127.0.0.1에 올리고 브라우저로 본다
(SPA 라우터는 해시를 안 쓰므로 `(await import('/js/router.js')).navigate('specialLeave')`로 화면을 옮긴다).

## 버전 올리기

**버전은 exe를 실제로 빌드·배포할 때만 올린다.** 배포하지 않은 변경을 이미 나간 버전 줄에
계속 덧붙이면 안 된다 — 2026-09-02에 실제로 이 사고가 났다. 배포된 v5.4 줄에 미배포 항목이
쌓여 `(예정)`으로 남아 있었고, `dist/변경이력.txt`(실제 배포본)와 대조해서야 갈라낼 수 있었다.
**무엇이 이미 나갔는지는 `dist/변경이력.txt`와 `dist/_old_versions/`가 정본이다.**

버전 문자열이 박힌 곳 — 하나라도 빠뜨리면 배포본이 어긋난다:

| 파일 | 위치 |
|---|---|
| `wage_calculator/통계조사관임금계산.spec` | `name='통계조사관임금계산_vX.Y'` |
| `변경이력.txt` | 새 줄 `vX.Y (YYYY-MM-DD)` — 날짜는 **exe 빌드 생성일** |
| `임금계산_로직_안내(vX.Y).txt` | **파일명**(`git mv`) + 1행 제목 + "프로그램(vX.Y)이 실제로 쓰는" 문구 + 변경점 절 |
| `README.md` | `현재 버전` 행, `9. 개발 이력` 표, 로직 안내문 링크, 테스트 개수·커밋 수 |

로직 안내문의 `★vX.Y` 표시는 **그 항목이 실제로 나간 버전**을 가리킨다. 일괄 치환하면
과거 버전 표시까지 바뀌므로 한 줄씩 확인한다.

## 빌드와 배포 세트

```bash
cd wage_calculator
python -m PyInstaller --noconfirm 통계조사관임금계산.spec
```

빌드가 끝나면 **반드시 `dist/`를 배포 세트 모양으로 맞춘다.** 담당자에게는 이 폴더의
파일들이 그대로 나가므로, exe만 새로 놓고 문서를 안 갱신하면 안내문과 프로그램이 어긋난다.

```bash
cd wage_calculator/dist
mv 통계조사관임금계산_v<이전>.exe _old_versions/     # 이전 버전 보관
cp ../../변경이력.txt .                              # 저장소 루트 것으로 덮어쓴다
cp "../../임금계산_로직_안내(vX.Y).txt" .
rm -f "임금계산_로직_안내(v<이전>).txt"              # 옛 안내문 제거(두 벌이 남지 않게)
```

끝난 뒤 `dist/`는 이 모양이어야 한다:

```
dist/
├─ 통계조사관임금계산_vX.Y.exe
├─ 변경이력.txt
├─ 임금계산_로직_안내(vX.Y).txt
├─ config.json          ← 지우지 않는다
└─ _old_versions/       ← 이전 exe들
```

`dist/config.json`은 **기본 설정 씨앗**이다. 설정은 `%APPDATA%`에 저장되지만
(`core/config.py`), 새 경로가 비어 있으면 exe 옆의 이 파일에서 읽어 최초 1회 이전한다
(`legacy_config_path`). 지우면 담당자가 조사종류·요율·공휴일을 처음부터 다시 넣어야 한다.

빌드 후 exe를 한 번 실행해 창이 뜨는지 확인한다(백그라운드로 띄우고 `tasklist`로 생존 확인).

`build/`와 `dist/`는 gitignore 대상이라 커밋되지 않는다. 배포는 내부저장소 공유문서함에
**exe + 변경이력 + 로직 안내문 세 파일을 함께** 올리는 것으로 끝난다.

## 계산 로직에서 조심할 것

- 급여·만근 판정은 종별 문자열이 아니라 `LeaveEvent`의 두 축이 정한다 —
  `unpaid`(그 시간·일수를 급여에서 깎는가), `breaks`(그날을 실근무 0분으로 보는가).
  규칙이 채우는 값과 확인 화면에서 사람이 채우는 값이 같은 모양이라야 엔진이 둘을 구분하지 않는다.
- **확인 화면의 답은 `classified`를 덮어쓰지 않는다.** 덮어쓰면 `연가`의 잔량 소진이 사라진다
  (`leave_usage_minutes`가 `classified == "연가"`로 판정한다). 미인식 종별만 표시용으로 바꾼다.
- 인식 종별은 `core/mapping.py`의 `KNOWN_CATEGORIES` 9종 + `ALIASES`(반일연가 오전/오후)뿐이다.
  **키워드 규칙으로 넓히지 않는다** — 예전에 그랬다가 `조퇴`가 `기타`와 같은 분류가 되어
  "기타는 연가로 상계하지 않는다"를 표현할 수 없었다. 새 표기가 나오면 `ALIASES`에 **명시**하거나,
  그대로 두어 확인 화면에서 사람이 판단하게 한다.
- 출력물의 `근무상황(기간제)` 시트는 보관용이 아니라 **다음 달 계산의 입력**이다.
  열 구성을 바꾸면 `core/parser.load_previous_status_rows()`도 같이 고쳐야 한다.

설계 배경은 `docs/superpowers/specs/`에 있다. 이어서 작업할 때 먼저 읽는다.
