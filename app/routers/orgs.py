from fastapi import APIRouter, HTTPException, Header
from ..models import OrgCreate, OrgGet, OrgUpdate
from ..db import master_db
from ..utils import sanitize_collection_name
from ..auth import hash_password, decode_token
from bson.objectid import ObjectId

router = APIRouter(prefix="/org", tags=["org"])

MASTER_ORG_COLL = "organizations"

@router.post("/create")
async def create_org(payload: OrgCreate):
    org_name = payload.organization_name.strip()
    coll_name = sanitize_collection_name(org_name)

    # check duplicate
    existing = await master_db[MASTER_ORG_COLL].find_one({"organization_name": org_name})
    if existing:
        raise HTTPException(status_code=400, detail="Organization already exists")

    # create tenant collection (initial doc to ensure creation)
    tenant_coll = master_db[coll_name]
    await tenant_coll.insert_one({"_init": True, "created_at": __import__("datetime").datetime.utcnow()})

    # create admin user in master DB (store hashed password)
    hashed = hash_password(payload.password)
    admin_doc = {
        "email": payload.email,
        "password": hashed,
        "organization": org_name,
        "created_at": __import__("datetime").datetime.utcnow()
    }
    admin_res = await master_db["admins"].insert_one(admin_doc)

    # store org metadata
    org_meta = {
        "organization_name": org_name,
        "collection_name": coll_name,
        "admin_user_id": str(admin_res.inserted_id),
        "admin_email": payload.email,
        "created_at": __import__("datetime").datetime.utcnow()
    }
    res = await master_db[MASTER_ORG_COLL].insert_one(org_meta)
    org_meta["_id"] = str(res.inserted_id)
    return {"ok": True, "organization": org_meta}

@router.get("/get")
async def get_org(organization_name: str):
    org = await master_db[MASTER_ORG_COLL].find_one({"organization_name": organization_name})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # serialize _id
    org["_id"] = str(org["_id"])
    return org

@router.put("/update")
async def update_org(payload: OrgUpdate):
    org = await master_db[MASTER_ORG_COLL].find_one({"organization_name": payload.organization_name})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # handle rename
    if payload.new_organization_name:
        new_name = payload.new_organization_name.strip()
        conflict = await master_db[MASTER_ORG_COLL].find_one({"organization_name": new_name})
        if conflict:
            raise HTTPException(status_code=400, detail="New organization name already exists")

        old_coll = org["collection_name"]
        new_coll = sanitize_collection_name(new_name)

        old = master_db[old_coll]
        new = master_db[new_coll]

        cursor = old.find({})
        async for doc in cursor:
            doc.pop("_id", None)
            await new.insert_one(doc)

        # drop old collection
        await master_db.drop_collection(old_coll)

        # update metadata
        await master_db[MASTER_ORG_COLL].update_one(
            {"_id": org["_id"]},
            {"$set": {"organization_name": new_name, "collection_name": new_coll}}
        )

        # update admins referencing org
        await master_db["admins"].update_many(
            {"organization": payload.organization_name},
            {"$set": {"organization": new_name}}
        )

    # update email/password if provided
    if payload.email or payload.password:
        update_fields = {}
        if payload.email:
            update_fields["email"] = payload.email
        if payload.password:
            update_fields["password"] = hash_password(payload.password)
        if update_fields:
            admin_id = org["admin_user_id"]
            await master_db["admins"].update_one(
                {"_id": ObjectId(admin_id)},
                {"$set": update_fields}
            )

    return {"ok": True, "message": "Organization updated"}

@router.delete("/delete")
async def delete_org(organization_name: str, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.split("Bearer ")[-1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    token_org = payload.get("organization")
    if token_org != organization_name:
        raise HTTPException(status_code=403, detail="Not allowed to delete this organization")

    org = await master_db[MASTER_ORG_COLL].find_one({"organization_name": organization_name})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # TODO: add rate-limiting + audit logging for destructive endpoints
    # TODO: use transactions when copying large collections in production

    coll_name = org["collection_name"]
    await master_db.drop_collection(coll_name)
    await master_db["admins"].delete_many({"organization": organization_name})
    await master_db[MASTER_ORG_COLL].delete_one({"_id": org["_id"]})

    return {"ok": True, "message": f"Organization '{organization_name}' deleted"}
