# app/services/rabbitmq_service.py

from typing import Dict, List
import aio_pika
import asyncio
import json
from app.services.comparator_service import ComparatorService
from app.services.sync_status_service import SyncStatusService
from app.services.account_mapping_service import AccountMappingService
from app.utils.config import settings
from app.services.mapping_service import MappingService
from loguru import logger

class RabbitMQService:
    def __init__(self):
        # Existing attributes
        self.connection = None
        self.channel = None
        self.queue = None

        # Instantiate dependencies
        self.mapping_service = MappingService()
        self.account_mapping_service = AccountMappingService()
        self.sync_status_service = SyncStatusService()

        # Correctly instantiate ComparatorService with required dependencies
        self.comparator_service = ComparatorService(
            self.mapping_service,
            self.account_mapping_service
        )

    async def connect_async(self):
        try:
            self.connection = await aio_pika.connect_robust(
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                login=settings.rabbitmq_user,
                password=settings.rabbitmq_password
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            self.queue = await self.channel.declare_queue(settings.rabbitmq_queue, durable=True)
            logger.info(f"Connected to RabbitMQ on {settings.rabbitmq_host}:{settings.rabbitmq_port}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise e

    async def consume_messages_async(self):
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        task = json.loads(message.body.decode())
                        await self.handle_task(task)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

    async def handle_task(self, task: dict):
        action = task.get("action")
        user_id = task.get("user_id")
        nordigen_account_id = task.get("account_id")

        if action == "process_account":
            unmatched_transactions = self.comparator_service.process_account(nordigen_account_id)
            if unmatched_transactions:
                mapping = self.account_mapping_service.get_mapping(nordigen_account_id)
                if not mapping:
                    logger.error(f"No account mapping found for Nordigen account {nordigen_account_id}.")
                    return

                ynab_budget_id = mapping["ynab_budget_id"]
                ynab_account_id = mapping["ynab_account_id"]

                # Assign YNAB account ID to each transaction
                for txn in unmatched_transactions:
                    txn["nordigen_account_id"] = txn.get("account_id")
                    txn["account_id"] = ynab_account_id

                # Send transactions in batches
                batch_size = 50  # YNAB API limit
                for i in range(0, len(unmatched_transactions), batch_size):
                    batch = unmatched_transactions[i:i + batch_size]
                    message = {
                        "action": "create_transactions",
                        "user_id": user_id,
                        "budget_id": ynab_budget_id,
                        "transactions_data": batch
                    }
                    # Send the message to Freyr
                    await self.send_message_to_freyr(message)

                    # **Update sync status for each transaction in the batch**
                    for txn in batch:
                        account_id = txn.get("nordigen_account_id")
                        transaction_id = txn.get("transactionId")
                        self.sync_status_service.update_sync_status(account_id, transaction_id)

                logger.info("Processed unmatched transactions and updated sync status.")
            else:
                logger.info("No unmatched transactions found.")
        else:
            logger.warning(f"Unknown action: {action}")

    async def send_message_to_freyr(self, message: dict):
        try:
            # Log the message content at DEBUG level
            logger.debug(f"Sending message to Freyr: {message}")

            await self.channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(message).encode()),
                routing_key="ynab_tasks"  # Updated queue name
            )
            logger.info("Sent message to Freyr's ynab_tasks queue.")
        except Exception as e:
            logger.error(f"Failed to send message to Freyr: {e}")