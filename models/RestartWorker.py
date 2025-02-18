
import logging
from spex_common.services.Timer import every
from functools import partial
from multiprocessing import Process

import spex_common.services.Task as TaskService
from spex_common.models.Status import TaskStatus
from spex_common.modules.logging import get_logger
from spex_common.modules.aioredis import send_event

from models.Constants import collection, Events
from utils import (
    update_status as update_status_original,
    add_to_waiting_table as add_to_waiting_table_original,
)

update_status = partial(update_status_original, collection, 'job_manager_runner')
add_to_waiting_table = partial(add_to_waiting_table_original, login='job_manager_catcher')


def get_failed_task():
    tasks = TaskService.select_tasks(
        search="FILTER doc.status == @error LIMIT 1",
        error=TaskStatus.failed.value
    )
    return tasks[0] if tasks else None


def should_retry(task):
    error_msg = task.get("error", "")
    if error_msg is None:
        return True
    return "already restarted" not in error_msg


def has_running_tasks():
    tasks = TaskService.select_tasks(
        search="FILTER doc.status IN @statuses LIMIT 1",
        statuses=[TaskStatus.started.value, TaskStatus.ready.value, TaskStatus.pending.value]
    )
    return bool(tasks)


def restart_worker(name):
    logger = get_logger(name)

    def retry_failed_tasks():
        if has_running_tasks():
            return

        while True:
            task = get_failed_task()
            if not task:
                break

            if should_retry(task):
                error_msg = task.get("error", "")
                new_error_msg = f"{error_msg} (already restarted)" if error_msg else "Task already restarted"
                update_status(TaskStatus.ready.value, task, error=new_error_msg)
                send_event(Events.TASK_START, {"task": task})
                logger.info(f"Restarted task: {task.get('id')}")

    try:
        logger.info("Starting RestartWorker")
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        every(10, retry_failed_tasks)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Exception in RestartWorker: {e}")
    finally:
        logger.info("Stopping RestartWorker")


class RestartWorker(Process):
    def __init__(self, index=0):
        super().__init__(
            name=f'Spex.restart-worker.{index + 1}',
            target=restart_worker,
            args=(f'spex.ms-restart-worker.{index + 1}',),
            daemon=True
        )
