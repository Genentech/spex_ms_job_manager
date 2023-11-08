import logging
import os.path
from multiprocessing import Process
from functools import partial

import spex_common.services.Task as TaskService
import spex_common.services.Utils as Utils
from spex_common.modules.aioredis import send_event
from spex_common.modules.logging import get_logger
from spex_common.services.Timer import every
from spex_common.models.Status import TaskStatus
import spex_common.services.Script as ScriptService
import pickle

from models.Constants import collection, Events
from utils import (
    update_status as update_status_original
)

update_status = partial(update_status_original, collection, 'job_manager_catcher')


def get_garbage_tasks():
    tasks = TaskService.select_tasks(
        search=f"FILTER ("
               f" doc.status < @complete"
               f" and doc.status > @ready"
               f")",
        complete=TaskStatus.complete.value,
        ready=TaskStatus.ready.value
    )

    if tasks:
        return tasks
    else:
        return None


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


def task_is_completed(task_json):
    result_path = task_json.get("result")
    if not result_path:
        return False
    absolute_path = Utils.getAbsoluteRelative(result_path, absolute=True)
    script_name = task_json.get("params", {}).get("script", "")
    part = task_json.get("params", {}).get("part", "")
    return_params = ScriptService.get_return_block_by_script_path(script_name, part)

    if not os.path.exists(absolute_path):
        return False
    with open(absolute_path, "rb") as infile:
        to_show_data = pickle.load(infile)
        for key in return_params.keys():
            if key not in to_show_data.keys():
                return False

    return True


def garbage_worker(name):
    logger = get_logger(name)

    def collect_unfinished_tasks():
        if tasks := get_garbage_tasks():
            for a_task in tasks:
                if task_is_completed(a_task):
                    logger.info(f'task is completed: {a_task.get("name")} / {a_task.get("id")}')
                    update_status(TaskStatus.complete.value, a_task)
    try:
        logger.info('Starting')
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        every(10, collect_unfinished_tasks)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f'catch exception: {e}')
    finally:
        logger.info('Closing')


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


class GarbageWorker(Process):
    def __init__(self, index=0):
        super().__init__(
            name=f'Spex.arango-garbage-job-catcher.Worker.{index + 1}',
            target=garbage_worker,
            args=(f'spex.ms-garbage-job-catcher.worker.{index + 1}',),
            daemon=True
        )
