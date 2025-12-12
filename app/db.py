from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

# create a Motor client and expose master_db
client = AsyncIOMotorClient(settings.MONGO_URI)
master_db = client[settings.MASTER_DB]
