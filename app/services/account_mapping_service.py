# app/services/account_mapping_service.py

from typing import Dict, Optional
from pymongo import MongoClient
from app.utils.config import settings
from loguru import logger

class AccountMappingService:
    def __init__(self):
        self.client = MongoClient(settings.mongodb_uri)
        self.db = self.client.mimir
        self.mapping_collection = self.db.account_mappings

    def get_mapping(self, nordigen_account_id: str) -> Optional[Dict]:
        mapping = self.mapping_collection.find_one({"nordigen_account_id": nordigen_account_id})
        if mapping:
            logger.debug(f"Retrieved mapping for Nordigen account {nordigen_account_id}.")
            return mapping
        logger.warning(f"No mapping found for Nordigen account {nordigen_account_id}.")
        return None

    def store_mapping(self, mapping_data: Dict):
        self.mapping_collection.update_one(
            {"nordigen_account_id": mapping_data["nordigen_account_id"]},
            {"$set": mapping_data},
            upsert=True
        )
        logger.info(f"Stored mapping for Nordigen account {mapping_data['nordigen_account_id']}.")