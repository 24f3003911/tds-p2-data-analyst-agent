"""
Minimal test app to isolate FastAPI issues.
"""
from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Test App")

@app.get("/")
def root():
    return {"message": "Hello World", "status": "working"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("Starting minimal test app...")
    uvicorn.run(app, host="127.0.0.1", port=8000)