from fastapi import FastAPI

app = FastAPI(title="GovAssist API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}