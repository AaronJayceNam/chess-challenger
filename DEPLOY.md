# Chess Challenger — 웹사이트로 배포하기

이 앱은 Python 백엔드 + **Stockfish 엔진**이 필요해서, GitHub Pages 같은 정적
호스팅에는 못 올립니다. 두 가지 길이 있습니다.

---

## 옵션 A. 지금 바로 공유 (계정·비용 없음, 가장 쉬움)

내 PC에서 돌고 있는 앱을 **임시 공개 주소**로 공유합니다. 친구에게 링크를 보내
바로 써보게 할 때 좋습니다.
한계: **내 PC가 켜져 있어야** 하고, 주소는 실행할 때마다 바뀝니다.

1. Cloudflare 터널 설치 (한 번만):
   ```powershell
   winget install Cloudflare.cloudflared
   ```
2. 앱이 켜져 있는지 확인 (바탕화면 **Chess Challenger** 아이콘).
3. 새 터미널에서:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
   → `https://무작위이름.trycloudflare.com` 같은 **공개 주소**가 출력됩니다.
   이 주소를 누구에게나 보내면 접속됩니다. (창을 닫으면 주소도 닫힘)

> ngrok( https://ngrok.com )도 같은 방식입니다: `ngrok http 8000`.

---

## 옵션 B. 정식 배포 — 항상 켜진 진짜 웹사이트

클라우드에 올려 **24시간 켜진 고정 URL**을 만듭니다. 계정이 필요하고, 무료
등급은 느리거나 잠들 수 있습니다(유료 등급은 빠릿함).

이 저장소에는 배포에 필요한 파일이 이미 들어 있습니다:
`Dockerfile`, `.dockerignore`, `render.yaml`.

### B-1. 코드를 GitHub에 올리기 (최초 1회)
1. https://github.com 가입 → 새 저장소(repository) 생성 (예: `chess-challenger`).
2. 이 폴더를 올립니다:
   ```powershell
   cd C:\Users\jayce\chess-coach
   git remote add origin https://github.com/<your-id>/chess-challenger.git
   git branch -M main
   git push -u origin main
   ```

### B-2. Render.com에 배포 (추천 — 가장 쉬움)
1. https://render.com 가입 → GitHub 연결.
2. **New +** → **Blueprint** → 위 저장소 선택 → **Apply**.
   (`render.yaml`을 읽어 Docker로 Stockfish까지 자동 설치합니다.)
3. 몇 분 뒤 `https://chess-challenger.onrender.com` 같은 **공개 URL**이 생깁니다.

> 무료 등급은 메모리·CPU가 작아 분석이 느리고, 일정 시간 미사용 시 잠들어서 첫
> 접속이 느립니다. 쾌적하게 쓰려면 Render의 **Starter**(월 몇 달러)로 올리세요.
> 더 빠르게 하려면 환경변수 `CC_WORKERS`, `CC_ENGINE_THREADS`, `CC_ENGINE_HASH_MB`
> 를 올려 주세요(서버가 클수록 크게).

### 대안 호스트
- **Railway** ( https://railway.app ): GitHub 연결 후 Dockerfile 자동 감지. 환경변수만
  위와 같이 넣으면 됩니다.
- **Fly.io** ( https://fly.io ): `flyctl launch` (Dockerfile 사용) → GitHub 없이 로컬에서
  바로 배포 가능. 신용카드 등록 필요.

---

## 운영 메모
- `/api/health` 로 상태 확인(헬스체크에 사용).
- 분석은 CPU를 많이 씁니다. 동시 사용자가 많으면 인스턴스를 키우거나
  `CC_MAX_CONCURRENT`(동시 분석 수)·`CC_WORKERS`를 조절하세요.
- 인증/계정 기능은 없습니다(누구나 접속해 분석·대국). 공개해도 저장되는 개인정보는
  없지만, 비용이 드는 호스트라면 접근을 제한하고 싶을 수 있습니다 — 필요하면 간단한
  비밀번호 게이트를 추가해 드릴 수 있습니다.
