import spex_common.services.Task as TaskService
from datetime import datetime
from spex_common.modules.database import db_instance
from spex_common.models.History import history
from spex_common.models.WaitTableEntry import wait_table_entry, WaitTableEntry
from spex_common.models.Status import TaskStatus


def add_history(login, parent, content, event_type: str = "job_manager_update"):
    db_instance().insert('history', history({
        'author': {
            'login': login,
            'id': '0'
        },
        'date': datetime.now().isoformat(),
        'content': content,
        'parent': parent,
        'event_type': event_type
    }).to_json())


def add_to_waiting_table(login, waiter_type, waiter_id, what_awaits):
    db_instance().insert('waiting_table', wait_table_entry({
        'author': {
            'login': login,
            'id': '0'
        },
        'date': str(datetime.now()),
        'waiter_id': waiter_id,
        'waiter_type': waiter_type,
        'what_awaits': what_awaits,
    }).to_json())


def already_in_waiting_table(what_awaits, waiter_type, waiter_id):
    last_records = db_instance().select(
        'waiting_table',
        f'FILTER doc.what_awaits == @what_awaits'
        f' and doc.waiter_type == @waiter_type'
        f' and doc.waiter_id == @waiter_id',
        what_awaits=what_awaits,
        waiter_type=waiter_type,
        waiter_id=waiter_id,
    )
    key_arr = [record["_key"] for record in last_records]

    if not key_arr:
        return False

    return True


def get_from_waiting_table(what_awaits, waiter_type) -> [WaitTableEntry]:
    last_records = db_instance().select(
        'waiting_table',
        'FILTER doc.what_awaits == @what_awaits and doc.waiter_type == @waiter_type',
        what_awaits=what_awaits,
        waiter_type=waiter_type,
    )

    return [wait_table_entry(item) for item in last_records] \
        if last_records \
        else []


def del_from_waiting_table(ids):
    db_instance().delete(
        'waiting_table',
        'FILTER doc._key in @ids',
        ids=ids
    )


def get_task_with_status(_id: str, status: int):
    tasks = TaskService.select_tasks(
        search="FILTER doc._id == @value and doc.status == @status LIMIT 1",
        value=_id,
        status=status
    )

    return tasks[0] if tasks else None


def get_parent_task_status(_id: str):
    task = TaskService.select(_id[6:])
    previous_task_id: str = ""
    parent_jobs = db_instance().select(
        "pipeline_direction",
        "FILTER doc._to == @value",
        value=f"jobs/{task.parent}",
    )

    if not parent_jobs:
        return TaskStatus.complete.value, previous_task_id

    jobs_ids = [item["_from"][5:] for item in parent_jobs]

    task_list = db_instance().select(
        "tasks",
        "FILTER doc.parent in @value ",
        value=jobs_ids,
    )

    previous_task_status: int = TaskStatus.complete.value

    if task_list:
        previous_task_status = task_list[0].get('status', 0)
        previous_task_id = task_list[0].get('_key', "")

    return previous_task_status, previous_task_id


def get_tasks(ids):
    return TaskService.select_tasks(condition='in', _key=ids)


def update_status(collection, login, status, a_task, result=None, error=None):
    search = "FILTER doc._key == @value LIMIT 1"
    data = {"status": status}

    if result:
        data.update({"result": result})

    if error:
        data.update({"error": error})

    db_instance().update(
        collection,
        data,
        search,
        value=a_task["id"]
    )
    add_history(
        login,
        f"jobs/{a_task['parent']}",
        f'status from: {a_task["status"]} to: {status}',
    )
