"""Run the demo: python -m emporio  (then open http://localhost:8000)."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("emporio.api:create_app", factory=True, host="127.0.0.1", port=8000)
