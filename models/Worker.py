import shutil
import os
import uuid
import json
import pickle
import subprocess
import logging
from os import cpu_count, getenv
from functools import partial
from multiprocessing import Process

from spex_common.models.Status import TaskStatus
from spex_common.modules.logging import get_logger
from spex_common.modules.aioredis import create_aioredis_client
from spex_common.modules.database import db_instance
from spex_common.services.Utils import getAbsoluteRelative
from spex_common.modules.aioredis import send_event
from spex_common.models.OmeroImageFileManager import OmeroImageFileManager

from models.Constants import collection, Events
from utils import (
    get_task_with_status,
    get_parent_task_status,
    update_status as update_status_original,
    add_to_waiting_table as add_to_waiting_table_original,
    already_in_waiting_table,
    del_from_waiting_table,
    get_from_waiting_table,
    get_tasks,
    get_parent_tasks,
)

update_status = partial(update_status_original, collection, 'job_manager_runner')
add_to_waiting_table = partial(add_to_waiting_table_original, login='job_manager_catcher')


def get_platform_venv_params(script, part):
    env_path = os.getenv("SCRIPTS_ENVS_PATH", f"~/scripts_envs")
    env_path = os.path.expanduser(env_path)

    script_copy_path = os.path.join(env_path, "scripts", script, part)
    os.makedirs(script_copy_path, exist_ok=True)

    env_path = os.path.join(env_path, "envs", script)
    os.makedirs(env_path, exist_ok=True)
    env_path = os.path.join(env_path, part)

    not_posix = os.name != "posix"

    executor = "python" if not_posix else "python3"
    start_script = "source" if not_posix else "."
    create_venv = f"{executor} -m venv {env_path} --system-site-packages"

    activate_venv = f"{start_script} {os.path.join(env_path, 'bin', 'activate')}"
    if not_posix:
        activate_venv = os.path.join(env_path, "Scripts", "activate.bat")

    return {
        "env_path": env_path,
        "script_copy_path": script_copy_path,
        "create_venv": create_venv,
        "activate_venv": activate_venv,
        "executor": executor
    }


def get_image_from_omero(a_task) -> str or None:
    image_id = a_task["omeroId"]
    file = OmeroImageFileManager(image_id)
    author = a_task.get("author").get("login")

    if file.exists():
        return file.get_filename(), 0

    what_awaits = f"{Events.IMAGE_DOWNLOADED}:{image_id}"
    waiter_type = 'task'
    waiter_id = a_task.get("id")

    update_status(TaskStatus.pending.value, a_task)

    if already_in_waiting_table(what_awaits, waiter_id, waiter_type):
        return None, TaskStatus.pending.value

    value = {"id": image_id, "override": False, "user": author}
    send_event(Events.IMAGE_DOWNLOAD, value)

    add_to_waiting_table(
        waiter_id=waiter_id,
        waiter_type=waiter_type,
        what_awaits=what_awaits,
    )

    return None, TaskStatus.pending.value


def get_pool_size(env_name) -> int:
    value = getenv(env_name, 'cpus')
    if value.lower() == 'cpus':
        value = cpu_count()
    return max(2, int(value))


def enrich_task_data(a_task):
    parent_jobs = db_instance().select(
        "pipeline_direction",
        "FILTER doc._to == @value",
        value=f"jobs/{a_task['parent']}",
    )

    if not parent_jobs:
        return {}

    data = {}
    jobs_ids = [item["_from"][5:] for item in parent_jobs]

    tasks = db_instance().select(
        "tasks",
        "FILTER doc.parent in @value "
        'and doc.result != "" '
        "and doc.result != Null ",
        value=jobs_ids,
    )

    for item in tasks:
        if item['omeroId'] == a_task['omeroId']:
            filename = getAbsoluteRelative(item["result"], True)
            with open(filename, "rb") as outfile:
                current_file_data = pickle.load(outfile)
                data = {**data, **current_file_data}

    return data


def get_path(job_id, task_id):
    path = os.path.join(os.getenv("DATA_STORAGE"), "jobs", job_id, task_id)
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

    return path


class Executor:
    def __init__(self, logger, task_id):
        self.logger = logger
        self.task_id = task_id

    def run(self):
        self.logger.info(f'run task: {self.task_id}')
        if not self.task_id:
            self.logger.info(f'task id is not empty: {self.task_id}')
            return

        a_task = get_task_with_status(self.task_id, TaskStatus.started.value)

        if not a_task:
            self.logger.info(f'task is not found: {self.task_id}')
            return

        self.logger.info(f'task in process: {self.task_id}')

        previous_task_status, previous_tasks_id = get_parent_task_status(self.task_id)

        if previous_task_status != TaskStatus.complete.value:
            add_to_waiting_table(
                waiter_id=self.task_id[6:],
                waiter_type='task',
                what_awaits=f'{Events.TASK_COMPLETED}:{previous_tasks_id}',
            )
            self.logger.info(f'task is moved to waiters: {self.task_id} ; reason await previous: {previous_tasks_id}')
            return

        a_task["params"] = {**enrich_task_data(a_task), **a_task["params"]}

        new_status = a_task.get("status")
        # download image tiff
        path = a_task["params"].get("image_path")
        if not (path and os.path.isfile(path)):
            if not a_task.get('omeroId', None) and len(a_task.get('params', {}).get('omeroIds', [])) > 0:
                a_task['omeroId'] = a_task.get('params', {}).get('omeroIds', [])[0]
            path, new_status = get_image_from_omero(a_task)

        if path is None:
            if new_status != TaskStatus.pending.value:
                self.logger.info(f'task status is set error: {self.task_id}')
                update_status(TaskStatus.error.value, a_task, error='image is not found')
            else:
                self.logger.info(f'task is moved to waiters: {self.task_id} ; reason await image: {a_task["omeroId"]}')
            return

        update_status(TaskStatus.in_work.value, a_task)

        script_path = getAbsoluteRelative(
            os.path.join(
                os.getenv("DATA_STORAGE"),
                "Scripts",
                f'{a_task["params"]["script"]}'
            )
        )

        filename = os.path.join(get_path(a_task["id"], a_task["parent"]), "result.pickle")

        error = f'path of image is not a file: {path}'
        if os.path.isfile(path):
            if a_task.get('name', '') == 'phenograph_cluster':
                a_task["params"].update(
                    data_storage=os.getenv("DATA_STORAGE"),
                    parent=a_task["parent"],
                    tasks_list=get_parent_tasks(a_task["parent"])
                )
            a_task["params"].update(
                image_path=path,
                folder=script_path,
            )

            try:
                result = self.start_scenario(**a_task["params"])
                if not result:
                    error = f'problems with scenario params {a_task["params"]}'
                    self.logger.error(error)
                else:
                    error = result.get('error')
                    result = {
                        key: result[key]
                        for key in result.keys() if key not in ("stderr", "stdout")
                    }

                    with open(filename, "wb") as outfile:
                        pickle.dump(result, outfile)
            except Exception as err:
                error = str(err)

        if os.path.isfile(filename):
            update_status(
                TaskStatus.failed.value if error else TaskStatus.complete.value,
                a_task,
                result=getAbsoluteRelative(filename, False),
                error=error,
            )
            self.logger.info(f"task is completed: {a_task['id']}")
        else:
            update_status(TaskStatus.failed.value, a_task, error=error)
            self.logger.info(f"task is uncompleted: {self.task_id}")
            self.logger.info(f"set status to failed: {TaskStatus.failed.value}")

        send_event(Events.TASK_COMPLETED, {'id': a_task['id']})

    def start_scenario(
        self,
        script: str = "",
        part: str = "",
        folder: str = "",
        **kwargs,
    ):
        manifest = os.path.join(folder, part, "manifest.json")

        if not os.path.isfile(manifest):
            return None

        with open(manifest) as meta:
            data = json.load(meta)

        if not data:
            return None

        self.logger.info(f"{script}-{part}")
        params = data.get("params")
        for key, item in params.items():
            if kwargs.get(key) is None:
                raise ValueError(
                    f"Not have param '{key}' in script: {script}, in part {part}"
                )

        self.check_create_install_lib(script, part, data.get("libs", []))
        return self.run_subprocess(folder, script, part, kwargs)

    def check_create_install_lib(self, script, part, libs):
        if not (isinstance(libs, list) and libs):
            return

        params = get_platform_venv_params(script, part)

        install_libs = f"pip install {' '.join(libs)}"

        if not os.path.isdir(params["env_path"]):
            command = params["create_venv"]
            self.logger.info(command)

            process = subprocess.run(
                command,
                shell=True,
                universal_newlines=True,
                stdout=subprocess.PIPE,
            )
            self.logger.debug(process.stdout.splitlines())

        command = f"{params['activate_venv']}" \
                  f" && {install_libs}"

        self.logger.info(command)

        process = subprocess.run(
            command,
            shell=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
        )

        self.logger.debug(process.stdout.splitlines())

    def run_subprocess(self, folder, script, part, data) -> dict:
        params = get_platform_venv_params(script, part)
        script_path = os.path.join(params["script_copy_path"], str(uuid.uuid4()))
        hist_data = {}

        try:
            shutil.copytree(os.path.join(folder, part), script_path)
            runner_path = os.path.join(script_path, "__runner__.py")
            shutil.copyfile(
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "runner.py"),
                runner_path,
            )

            filename = os.path.join(script_path, "__runner__.pickle")
            with open(filename, "wb") as infile:
                pickle.dump(data, infile)

            command = f"{params['activate_venv']} && {params['executor']} {runner_path}"
            self.logger.info(command)

            process = subprocess.run(
                command,
                shell=True,
                universal_newlines=True,
                capture_output=True,
                text=True,
            )
            hist_data = {
                "stderr": process.stderr if process.stderr else "",
                "stdout": process.stdout if process.stdout else "",
            }
            if process.stderr:
                self.logger.error(process.stderr)
            if process.stdout:
                self.logger.debug(process.stdout)

            if process.returncode:
                self.logger.error(f"return code: {process.returncode}")
                return {
                    **data,
                    **hist_data,
                    'error': f'process exit code: {process.returncode}\nstderr: {process.stderr}'
                }

            with open(filename, "rb") as outfile:
                result_data = pickle.load(outfile)
                return {
                    **data,
                    **result_data,
                    **hist_data
                }
        except Exception as e:
            return {
                **data,
                'error': str(e),
                **hist_data
            }
        finally:
            shutil.rmtree(script_path, ignore_errors=True)


async def __executor(logger, event):
    a_task = event.data.get("task")

    if not a_task:
        return

    a_task = a_task["_id"]

    if not a_task:
        return

    executor = Executor(logger, a_task)

    try:
        executor.run()
    except Exception as err:
        logger.exception(err)


async def __executor_process_waiters(logger, event):
    item_id = event.data.get("id")

    if not item_id:
        return

    what_awaits = f"{event.type}:{item_id}"

    logger.info(f"process for what_awaits: {what_awaits}")

    items = get_from_waiting_table(what_awaits, 'task')

    logger.info(f"found waiters: {len(items)}")

    if not items:
        return

    waiters = [item.id for item in items]

    items = [item.waiter_id for item in items]

    items = get_tasks(items)

    for item in items:
        update_status(TaskStatus.ready.value, item)

    del_from_waiting_table(waiters)


def worker(name):
    logger = get_logger(name)
    redis_client = create_aioredis_client()

    @redis_client.event(Events.TASK_START)
    async def job_start(event):
        if event is None or event.is_viewed:
            return
        logger.debug(f'catch event: {event}')
        event.set_is_viewed()
        await __executor(logger, event)

    @redis_client.event(Events.IMAGE_DOWNLOADED)
    async def image_downloaded(event):
        if event is None or event.is_viewed:
            return
        logger.debug(f'catch event: {event}')
        event.set_is_viewed()
        await __executor_process_waiters(logger, event)

    @redis_client.event(Events.TASK_COMPLETED)
    async def job_completed(event):
        if event is None or event.is_viewed:
            return
        logger.debug(f'catch event: {event}')
        event.set_is_viewed()
        await __executor_process_waiters(logger, event)

    try:
        logger.info('Starting')
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        redis_client.run(5)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f'catch exception: {e}')
    finally:
        logger.info('Closing')
        redis_client.close()


class Worker(Process):
    def __init__(self, index=0):
        super().__init__(
            name=f'Spex.JM.Worker.{index + 1}',
            target=worker,
            args=(f'spex.ms-job-manager.worker.{index + 1}',),
            daemon=True
        )
