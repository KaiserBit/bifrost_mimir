# test_rabbitmq_message.py

import json
import asyncio
from aio_pika import connect_robust, Message
from app.utils.config import settings

async def send_test_message():
    connection = await connect_robust(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        login=settings.rabbitmq_user,
        password=settings.rabbitmq_password
    )
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(settings.rabbitmq_queue, durable=True)
        message = {
            "action": "process_account",
            "user_id": "1",
            "account_id": "ca6258ba-5acb-4e5f-81ba-abc07c5e874b"
        }
        await channel.default_exchange.publish(
            Message(body=json.dumps(message).encode()),
            routing_key=queue.name
        )
        print("Test message sent.")

if __name__ == "__main__":
    asyncio.run(send_test_message())