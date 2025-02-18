from multiprocessing import freeze_support
from spex_common.config import load_config
from spex_common.modules.logging import get_logger
from models.Worker import Worker, get_pool_size
from models.ArangoWorker import Worker as ArangoWorker
from models.ArangoWorker import GarbageWorker
from models.RestartWorker import RestartWorker

def start_workers():
    logger = get_logger('spex.ms-job-manager')
    logger.info('Starting')
    workers = []

    worker = ArangoWorker(0)
    workers.append(worker)
    worker.start()

    worker1 = GarbageWorker(0)
    workers.append(worker1)
    worker1.start()

    restart_worker = RestartWorker(0)
    workers.append(restart_worker)
    restart_worker.start()

    for index in range(get_pool_size('WORKERS_POOL')):
        worker = Worker(index)
        workers.append(worker)
        worker.start()

    try:
        for worker in workers:
            worker.join()
    except KeyboardInterrupt:
        pass

    logger.info('Finished')

if __name__ == "__main__":
    freeze_support()
    load_config()
    start_workers()
