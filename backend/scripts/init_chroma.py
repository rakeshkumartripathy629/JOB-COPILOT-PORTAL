import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def init_chroma():
    import chromadb
    client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    try:
        client.get_or_create_collection("jobs")
        logger.info("Chroma collection 'jobs' initialized")
    except Exception as e:
        logger.error(f"Failed to init Chroma: {e}")


if __name__ == "__main__":
    asyncio.run(init_chroma())
