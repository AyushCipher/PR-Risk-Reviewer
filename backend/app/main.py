from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analyze_pr, fetch_pr

load_dotenv()

app = FastAPI(title="PR Risk Reviewer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_pr.router)
app.include_router(fetch_pr.router)


@app.get("/health")
def health():
    return {"status": "ok"}
