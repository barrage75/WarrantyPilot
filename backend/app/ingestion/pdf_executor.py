import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

PDF_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="warrantypilot-pdf")


async def run_pdf_task[T](function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    return await asyncio.get_running_loop().run_in_executor(
        PDF_EXECUTOR,
        partial(function, *args, **kwargs),
    )
