from fastapi import FastAPI
from .routers import orgs, auth
from .db import master_db
import uvicorn

app = FastAPI(title="Organization Management Service")

app.include_router(orgs.router)
app.include_router(auth.router)

@app.on_event("startup")
async def startup_event():
    names = await master_db.list_collection_names()
    if "organizations" not in names:
        await master_db.create_collection("organizations")
    if "admins" not in names:
        await master_db.create_collection("admins")

@app.get("/")
async def root():
    return {"ok": True, "message": "Organization Management Service"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
