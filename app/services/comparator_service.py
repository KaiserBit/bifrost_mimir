# app/services/comparator_service.py

from typing import List, Dict, Optional
from pymongo import MongoClient
from loguru import logger
import hashlib
import base64
from app.utils.config import settings
from app.services.sync_status_service import SyncStatusService

class ComparatorService:
    def __init__(self, mapping_service, account_mapping_service):
        self.mapping_service = mapping_service
        self.account_mapping_service = account_mapping_service
        self.sync_status_service = SyncStatusService()
        self.client = MongoClient(settings.mongodb_uri)
        self.nordigen_db = self.client.fenrir
        self.freyr_db = self.client.freyr

    def fetch_nordigen_transactions(self, account_id: str) -> List[Dict]:
        transactions = list(self.nordigen_db.transactions.find({"account_id": account_id}))
        logger.info(f"Fetched {len(transactions)} Nordigen transactions for account {account_id}.")
        return transactions

    def fetch_freyr_transactions(self, ynab_account_id: str) -> List[Dict]:
        # Connect to the Freyr database
        transactions_collection = self.freyr_db.transactions

        # Fetch transactions for the given ynab_account_id
        transactions = list(transactions_collection.find({"account_id": ynab_account_id}))
        logger.info(f"Fetched {len(transactions)} Freyr transactions for YNAB account {ynab_account_id}.")
        return transactions

    def process_account(self, nordigen_account_id: str):
        field_mapping = self.mapping_service.get_field_mapping(nordigen_account_id)

        if not field_mapping:
            logger.error(f"No field mappings found for account {nordigen_account_id}.")
            return

        # Fetch Nordigen transactions using nordigen_account_id
        nordigen_transactions = self.fetch_nordigen_transactions(nordigen_account_id)

        # Get ynab_account_id using the account mapping
        mapping = self.account_mapping_service.get_mapping(nordigen_account_id)
        if not mapping:
            logger.error(f"No account mapping found for Nordigen account {nordigen_account_id}.")
            return

        ynab_account_id = mapping["ynab_account_id"]

        # Fetch Freyr transactions using ynab_account_id
        freyr_transactions = self.fetch_freyr_transactions(ynab_account_id)

        # Map and prepare Nordigen transactions for YNAB
        prepared_transactions = []
        for txn in nordigen_transactions:
            mapped_txn = self.prepare_transaction_for_ynab(txn, field_mapping)
            if mapped_txn:
                prepared_transactions.append(mapped_txn)

        unmatched_transactions = self.compare_transactions(
            nordigen_account_id,
            prepared_transactions,
            freyr_transactions,
            field_mapping
        )
        return unmatched_transactions

    def prepare_transaction_for_ynab(self, transaction: Dict, field_mapping: Dict[str, str]) -> Optional[Dict]:
        mapped_txn = {}
        try:
            # Map fields
            for nordigen_field, ynab_field in field_mapping.items():
                value = transaction
                for key in nordigen_field.split('.'):
                    value = value.get(key, {})
                if isinstance(value, dict) and not value:
                    value = ""
                
                # **Handle array fields**
                if isinstance(value, list):
                    value = " ".join(value)

                mapped_txn[ynab_field] = value

            # Include additional required fields and format amounts
            mapped_txn["account_id"] = transaction.get("account_id")
            mapped_txn["date"] = mapped_txn.get("date")
            amount = float(mapped_txn.get("amount", 0))
            mapped_txn["amount"] = int(amount * 1000)
            mapped_txn["cleared"] = "cleared"
            mapped_txn["approved"] = False

            # Generate import_id for idempotency
            import_id = self.generate_import_id(mapped_txn)
            mapped_txn["import_id"] = import_id

            # Include the original Nordigen transaction ID
            mapped_txn["transactionId"] = transaction.get("transactionId")

            # Keep only the necessary fields
            mapped_txn = {key: mapped_txn[key] for key in [
                "account_id", "date", "amount", "payee_name", "memo", "cleared", "approved", "import_id", "transactionId"
            ] if key in mapped_txn}
            return mapped_txn
        except Exception as e:
            logger.error(f"Error preparing transaction for YNAB: {e}")
            return None
        
    def compare_transactions(self, account_id: str, nordigen_transactions: List[Dict], freyr_transactions: List[Dict], field_mapping: Dict[str, str]) -> List[Dict]:
        unmatched = []

        # Generate a set of composite keys for Freyr transactions
        freyr_keys = set()
        for txn in freyr_transactions:
            key = self.generate_transaction_key(txn, field_mapping.values())
            freyr_keys.add(key)

        for txn in nordigen_transactions:
            key_fields = list(field_mapping.values())
            key = self.generate_transaction_key(txn, key_fields)
            if key not in freyr_keys:
                transaction_id = txn.get("transactionId")
                if not self.sync_status_service.is_transaction_synced(account_id, transaction_id):
                    unmatched.append(txn)
                    logger.debug(f"Unmatched transaction: {key}")
                else:
                    logger.debug(f"Transaction {transaction_id} already synced.")
            else:
                logger.debug(f"Transaction key {key} exists in Freyr.")

        logger.info(f"Found {len(unmatched)} unmatched transactions.")
        return unmatched

    def generate_transaction_key(self, transaction: Dict, key_fields: List[str]) -> str:
        key_values = []
        for field in key_fields:
            value = transaction.get(field, "")
            if isinstance(value, list):
                value = " ".join(value)
            if isinstance(value, str):
                value = value.strip().lower()
            key_values.append(str(value))
        return "|".join(key_values)

    def generate_import_id(self, transaction: Dict) -> str:
        unique_string = f"{transaction['account_id']}_{transaction['date']}_{transaction['amount']}"
        import_id_hash = hashlib.md5(unique_string.encode()).digest()
        base64_hash = base64.urlsafe_b64encode(import_id_hash).decode().rstrip('=')
        import_id = f"YNAB:{base64_hash}"
        return import_id