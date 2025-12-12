from fastapi import APIRouter, HTTPException
from ..models import AdminLogin
from ..db import master_db
from ..auth import verify_password, create_access_token

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/login")
async def admin_login(payload: AdminLogin):
    admin = await master_db["admins"].find_one({"email": payload.email})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(payload.password, admin["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "admin_id": str(admin["_id"]),
        "admin_email": admin["email"],
        "organization": admin["organization"]
    })

    return {"access_token": token, "token_type": "bearer"}
