"""
개발용 ASGI 실행 스크립트. `uvicorn app.main:app` 과 동일 역할.
"""

# ─── 모듈 임포트 ───
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
