# TikaTuka Multi

티카투카 2인 멀티플레이 MVP입니다.

- 프론트엔드: 정적 HTML/CSS/JS
- 백엔드: FastAPI + WebSocket
- 방 코드: 4자리 숫자
- 게임 판정: 서버 권위 방식
- 저장소: MVP에서는 서버 메모리

## Deployed MVP

현재 Oracle Always Free 인스턴스에 배포되어 있습니다.

```text
http://161.33.14.219/
```

한 플레이어가 방을 만들면 4자리 번호가 생성되고, 다른 플레이어가 같은 번호로 입장하면 게임이 시작됩니다.

## Local run

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

다른 터미널에서 정적 파일을 열거나 간단한 HTTP 서버로 실행합니다.

```bash
cd frontend
python3 -m http.server 5173
```

브라우저:

```text
http://127.0.0.1:5173
```

## Tests

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-dev.txt
PYTHONPATH=server .venv/bin/python -m pytest -q
```

## Oracle deployment shape

Caddy가 `/var/www/tikatuka-multi`의 정적 프론트엔드를 서빙하고 `/api/*`, `/ws/*`, `/health`를 FastAPI로 프록시합니다.

```caddy
:80 {
    root * /var/www/tikatuka-multi

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /ws/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /health {
        reverse_proxy 127.0.0.1:8000
    }

    file_server
}
```

GitHub Pages에서 사용하려면 API 서버는 HTTPS/WSS 도메인이 필요합니다.

```html
<script>
  window.TIKATUKA_SERVER_URL = "https://your-api-domain.example";
</script>
```
