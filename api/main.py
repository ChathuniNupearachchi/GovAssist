from fastapi import FastAPI

from app.api import auth, cases, chat, plans, requirements, services, studios

app = FastAPI(title="GovAssist API")

app.include_router(chat.router)
app.include_router(cases.router)
app.include_router(services.router)
app.include_router(requirements.router)
app.include_router(studios.router)
app.include_router(auth.router)
app.include_router(plans.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
