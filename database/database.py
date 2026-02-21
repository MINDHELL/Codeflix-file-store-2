#Codeflix_Botz
#rohit_1888 on Tg

import motor.motor_asyncio
import pymongo
import logging
from config import DB_URI, DB_NAME
from datetime import datetime

logging.basicConfig(level=logging.INFO)

# Default structure for file-based verification
default_file_verify = {
    'is_verified': False,
    'verified_time': 0,
    'file_token': ""
}

class Rohit:

    def __init__(self, DB_URI, DB_NAME):
        self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
        self.database = self.dbclient[DB_NAME]

        # Collections
        self.user_data = self.database['users']
        self.file_verifications = self.database['file_verifications']  # new per-file verification
        self.admins_data = self.database['admins']
        self.banned_user_data = self.database['banned_user']
        self.del_timer_data = self.database['del_timer']
        self.fsub_data = self.database['fsub']
        self.rqst_fsub_Channel_data = self.database['request_forcesub_channel']

    # --------------------------
    # USER DATA
    # --------------------------
    async def present_user(self, user_id: int):
        found = await self.user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_user(self, user_id: int):
        await self.user_data.insert_one({'_id': user_id})
        return

    async def del_user(self, user_id: int):
        await self.user_data.delete_one({'_id': user_id})
        return

    # --------------------------
    # BAN USER DATA
    # --------------------------
    async def get_ban_users(self):
        users_docs = await self.banned_user_data.find().to_list(length=None)
        return [doc['_id'] for doc in users_docs]

    async def add_ban_user(self, user_id: int):
        if not await self.banned_user_data.find_one({'_id': user_id}):
            await self.banned_user_data.insert_one({'_id': user_id})

    async def del_ban_user(self, user_id: int):
        await self.banned_user_data.delete_one({'_id': user_id})

    # --------------------------
    # AUTO DELETE TIMER
    # --------------------------
    async def get_del_timer(self):
        data = await self.del_timer_data.find_one({})
        return data.get('value', 600) if data else 600

    async def set_del_timer(self, value: int):
        await self.del_timer_data.update_one({}, {'$set': {'value': value}}, upsert=True)

    # --------------------------
    # CHANNEL MANAGEMENT
    # --------------------------
    async def show_channels(self):
        docs = await self.fsub_data.find().to_list(length=None)
        return [doc['_id'] for doc in docs]

    async def get_channel_mode(self, channel_id: int):
        data = await self.fsub_data.find_one({'_id': channel_id})
        return data.get("mode", "off") if data else "off"

    async def set_channel_mode(self, channel_id: int, mode: str):
        await self.fsub_data.update_one({'_id': channel_id}, {'$set': {'mode': mode}}, upsert=True)

    # --------------------------
    # FILE VERIFICATION MANAGEMENT
    # --------------------------

    # Check if a user has verified a specific file
    async def is_file_verified(self, user_id: int, file_token: str) -> bool:
        doc = await self.file_verifications.find_one({'user_id': user_id, 'file_token': file_token})
        return doc.get("is_verified", False) if doc else False

    # Get file verification status
    async def get_file_verify_status(self, user_id: int, file_token: str):
        doc = await self.file_verifications.find_one({'user_id': user_id, 'file_token': file_token})
        return doc if doc else {'is_verified': False, 'verified_time': 0, 'file_token': file_token}

    # Mark a file as verified
    async def mark_file_verified(self, user_id: int, file_token: str):
        await self.file_verifications.update_one(
            {'user_id': user_id, 'file_token': file_token},
            {'$set': {'is_verified': True, 'verified_time': datetime.utcnow()}},
            upsert=True
        )

    # Add a verification record for a file
    async def add_file_verify_record(self, user_id: int, file_token: str):
        await self.file_verifications.update_one(
            {'user_id': user_id, 'file_token': file_token},
            {'$setOnInsert': {'is_verified': False, 'verified_time': 0}},
            upsert=True
        )

    # --------------------------
    # TOTAL VERIFICATIONS COUNT
    # --------------------------
    async def get_total_verify_count(self):
        pipeline = [{"$group": {"_id": None, "total": {"$sum": 1}}}]
        result = await self.file_verifications.aggregate(pipeline).to_list(length=1)
        return result[0]["total"] if result else 0

# Initialize DB
db = Rohit(DB_URI, DB_NAME)
