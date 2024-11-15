# app/services/sync_status_service.py

from typing import Dict
from pymongo import MongoClient
from app.utils.config import settings
from loguru import logger
from datetime import datetime

class SyncStatusService:
    def __init__(self):
        self.client = MongoClient(settings.mongodb_uri)
        self.db = self.client.mimir
        self.sync_status_collection = self.db.sync_status

    def update_sync_status(self, account_id: str, transaction_id: str):
        self.sync_status_collection.update_one(
            {"account_id": account_id, "transaction_id": transaction_id},
            {"$set": {"sync_date": datetime.utcnow()}},
            upsert=True
        )
        logger.info(f"Updated sync status for account {account_id}, transaction {transaction_id}.")

    def is_transaction_synced(self, account_id: str, transaction_id: str) -> bool:
        status = self.sync_status_collection.find_one(
            {"account_id": account_id, "transaction_id": transaction_id}
        )
        return status is not None