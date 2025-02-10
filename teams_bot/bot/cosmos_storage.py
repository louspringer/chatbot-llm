# flake8: noqa: E501
"""
# Ontology: cortexteams:CosmosStorage
# Implements: cortexteams:StorageImplementation
# Requirement: REQ-BOT-005 Azure Cosmos DB storage
# Guidance: guidance:BotPatterns#Storage
# Description: Azure Cosmos DB storage implementation

Azure Cosmos DB storage implementation for the Teams bot.
"""

from typing import Dict, Any, List, Optional, cast
import logging

from azure.cosmos.aio import CosmosClient, ContainerProxy, DatabaseProxy
from botbuilder.core import Storage

logger = logging.getLogger(__name__)


class CosmosStorage(Storage):
    """Azure Cosmos DB storage implementation."""

    def __init__(
        self, cosmos_uri: str, cosmos_key: str, database_id: str, container_id: str
    ) -> None:
        """Initialize the storage."""
        if not cosmos_uri:
            raise ValueError("cosmos_uri cannot be None or empty")
        if not cosmos_key:
            raise ValueError("cosmos_key cannot be None or empty")
        if not database_id:
            raise ValueError("database_id cannot be None or empty")
        if not container_id:
            raise ValueError("container_id cannot be None or empty")

        try:
            # Initialize Cosmos DB client
            self.client = CosmosClient(cosmos_uri, cosmos_key)
            self.database = self.client.get_database_client(database_id)
            self.container = self.database.get_container_client(container_id)
            logger.info("Initialized Cosmos DB storage")
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB storage: {e}")
            raise

    async def read(self, keys: List[str]) -> Dict[str, Any]:
        """Read items from storage."""
        if not keys:
            return {}

        try:
            result: Dict[str, Any] = {}
            for key in keys:
                try:
                    response = await self.container.read_item(
                        item=key, partition_key=key
                    )
                    if response:
                        result[key] = response
                except Exception as e:
                    logger.error(f"Failed to read item {key}: {e}")
            return result
        except Exception as e:
            logger.error(f"Failed to read items: {e}")
            return {}

    async def write(self, changes: Dict[str, Any]) -> None:
        """Write items to storage."""
        if not changes:
            return

        try:
            for key, item in changes.items():
                try:
                    if not isinstance(item, dict):
                        item = {"id": key, "data": item}
                    if "id" not in item:
                        item["id"] = key
                    await self.container.upsert_item(body=item)
                except Exception as e:
                    logger.error(f"Failed to write item {key}: {e}")
        except Exception as e:
            logger.error(f"Failed to write items: {e}")
            raise

    async def delete(self, keys: List[str]) -> None:
        """Delete items from storage."""
        if not keys:
            return

        try:
            for key in keys:
                try:
                    await self.container.delete_item(item=key, partition_key=key)
                except Exception as e:
                    logger.error(f"Failed to delete item {key}: {e}")
        except Exception as e:
            logger.error(f"Failed to delete items: {e}")
            raise

    async def close(self) -> None:
        """Close the client connection."""
        try:
            await self.client.close()
        except Exception as e:
            logger.error(f"Failed to close client: {e}")
            raise
