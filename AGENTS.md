# AGENTS.md

## 프로젝트 구조

- `frontend/`: 정적 HTML/CSS/JS, PC·모바일 UI, 애니메이션·사운드·이모티콘.
- `server/app/game_engine.py`: 서버 권위 게임 규칙.
- `server/app/main.py`: FastAPI, 방·랜덤 매칭·WebSocket·타이머·랭킹·SQLite.
- `tests/`: 게임 엔진과 서버 회귀 테스트.
- `README.md`: 개발·배포 명령과 상세 구조.

## 실행과 검증

```bash
PYTHONPATH=server .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
python3 -m http.server 5174 -d frontend
PYTHONPATH=server .venv/bin/python -m compileall -q server
PYTHONPATH=server .venv/bin/python -m pytest -q
git diff --check
```

## 공통 규칙

- Python은 `snake_case`, JS는 `camelCase`, 상수는 `UPPER_SNAKE_CASE`를 따른다.
- 게임 상태·주사위 RNG·행동 검증·승패·시간패는 항상 서버가 최종 권한을 가진다.
- 모바일의 “나=초록, 상대=빨강”은 표시 변환일 뿐 서버 player index를 바꾸지 않는다.
- 실드 알까기, 보너스 무연쇄, 홀드, 선공 실드, 승리 점수 차 타이브레이크를 임의로 되돌리지 않는다.
- 게임 중 나가기 예약과 실제 연결 종료의 탈주 패배 처리를 혼동하지 않는다.
- 기존 dirty worktree와 사용자 자산을 보존하고 파괴적 Git 명령을 사용하지 않는다.
- 프론트 변경 시 `frontend/index.html`의 캐시 버전을 올린다.
- 서버 배포는 사용자가 명시적으로 요청했을 때만 한다. 비밀번호·키를 저장소에 추가하지 않는다.

## 완료 기준

- 관련 회귀 테스트 추가 또는 갱신.
- 전체 pytest, compileall, `git diff --check` 통과.
- PC·모바일 영향 확인, README가 실제 동작과 다르면 함께 갱신.
- 배포 요청이 있었다면 공개 health, systemd, 실제 WebSocket 동작까지 확인.

## 반복 금지

- 이벤트 로그를 새 입장자에게 재생해 애니메이션을 중복시키지 않는다.
- 시계 갱신 때문에 모바일 전체 DOM을 반복 재생성하지 않는다.
- 랭킹/승패를 클라이언트 계산만 믿지 않는다.
- 사용자의 기존 변경을 reset·checkout·덮어쓰기 하지 않는다.
