import logging
from multiprocessing import Process
from functools import partial

import spex_common.services.Task as TaskService
from spex_common.modules.aioredis import send_event
from spex_common.modules.logging import get_logger
from spex_common.services.Timer import every
from spex_common.models.Status import TaskStatus


from models.Constants import collection, Events
from utils import (
    update_status as update_status_original
)

update_status = partial(update_status_original, collection, 'job_manager_catcher')


def get_task():
    tasks = TaskService.select_tasks(
        search=f"FILTER ("
               f" doc.status == @ready"
               f" or doc.status == @error"
               f")"
               f" and doc.content like @value"
               f" LIMIT 1",
        value="%empty%",
        ready=TaskStatus.ready.value,
        error=TaskStatus.error.value
    )

    if tasks:
        return tasks[0]

    tasks = TaskService.select_tasks(
        search="FILTER doc.status == @status LIMIT 1",
        status=TaskStatus.ready.value
    )

    return tasks[0] if tasks else None


def worker(name):
    logger = get_logger(name)

    def listener():
        if a_task := get_task():
            update_status(TaskStatus.started.value, a_task)
            send_event(Events.TASK_START, {"task": a_task})
            logger.info(f'found a task, sent it to in work: {a_task.get("name")} / {a_task.get("id")}')

    try:
        logger.info('Starting')
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        every(5, listener)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f'catch exception: {e}')
    finally:
        logger.info('Closing')


class Worker(Process):
    def __init__(self, index=0):
        super().__init__(
            name=f'Spex.arango-job-catcher.Worker.{index + 1}',
            target=worker,
            args=(f'spex.ms-job-catcher.worker.{index + 1}',),
            daemon=True
        )
