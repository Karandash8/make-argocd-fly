import asyncio
from dataclasses import dataclass


@dataclass
class RuntimeLimits:
  app_sem: asyncio.Semaphore
  subproc_sem: asyncio.Semaphore
  io_sem: asyncio.Semaphore
