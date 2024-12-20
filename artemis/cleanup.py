import datetime
import json
import time

from karton.core.backend import KartonBackend
from karton.core.config import Config as KartonConfig

from artemis import utils

logger = utils.build_logger(__name__)

DONT_CLEANUP_TASKS_FRESHER_THAN__DAYS = 3
DELAY_BETWEEN_CLEANUPS__SECONDS = 24 * 3600


def _cleanup_tasks_not_in_queues() -> None:
    # Until https://github.com/CERT-Polska/karton/issues/262 gets fixed, let's have our own cleanup routine
    backend = KartonBackend(config=KartonConfig())

    keys = backend.redis.keys()
    tasks = set()
    for key in keys:
        if key.startswith(b"karton.task"):
            tasks.add(key.split(b":")[1])

    queued_tasks = set()
    for key in keys:
        if key.startswith(b"karton.queue"):
            for task in backend.redis.lrange(key, 0, -1):
                queued_tasks.add(task)

    num_tasks_cleaned_up = 0
    for item in tasks - queued_tasks:
        key = b"karton.task:" + item
        value = backend.redis.get(key)
        if not value:
            continue

        task = json.loads(value)
        if datetime.datetime.utcfromtimestamp(task["last_update"]) < datetime.datetime.now() - datetime.timedelta(
            days=DONT_CLEANUP_TASKS_FRESHER_THAN__DAYS
        ):
            num_tasks_cleaned_up += 1
            backend.redis.delete(key)
    logger.info("Tasks cleaned up: %d", num_tasks_cleaned_up)


def cleanup() -> None:
    _cleanup_tasks_not_in_queues()


if __name__ == "__main__":
    while True:
        try:
            cleanup()
            time.sleep(DELAY_BETWEEN_CLEANUPS__SECONDS)
        except Exception:
            logger.exception("Error during cleanup")
