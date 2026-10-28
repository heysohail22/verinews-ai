"""One local inference at a time to limit memory pressure."""
import asyncio
inference_lock = asyncio.Lock()
