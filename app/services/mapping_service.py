# app/services/mapping_service.py

from typing import Dict
from pymongo import MongoClient
from app.utils.config import settings
from loguru import logger

class MappingService:
    def __init__(self):
        self.client = MongoClient(settings.mongodb_uri)
        self.db = self.client.mimir
        self.mapping_collection = self.db.field_mappings

    def get_field_mapping(self, account_id: str) -> Dict[str, str]:
        mapping = self.mapping_collection.find_one({"account_id": account_id})
        if mapping:
            logger.debug(f"Retrieved mapping for account {account_id}.")
            return mapping.get("field_mapping", {})
        logger.warning(f"No mapping found for account {account_id}.")
        return {}

    def store_field_mapping(self, account_id: str, field_mapping: Dict[str, str]):
        self.mapping_collection.update_one(
            {"account_id": account_id},
            {"$set": {"field_mapping": field_mapping}},
            upsert=True
        )
        logger.info(f"Stored mapping for account {account_id}.")