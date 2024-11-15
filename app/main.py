# app/main.py

from fastapi import FastAPI
from app.services.rabbitmq_service import RabbitMQService
from loguru import logger
import asyncio

app = FastAPI(title="Mimir - Transaction Comparator Microservice")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Mimir - Transaction Comparator Microservice...")
    rabbitmq_service = RabbitMQService()
    await rabbitmq_service.connect_async()
    asyncio.create_task(rabbitmq_service.consume_messages_async())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Mimir - Transaction Comparator Microservice...")

@app.get("/health")
async def health_check():
    return {"status": "Mimir is running smoothly."}