from multiprocessing import freeze_support
from spex_common.config import load_config
from spex_common.modules.logging import get_logger
from models.Worker import Worker, get_pool_size
from models.ArangoWorker import Worker as ArangoWorker


def start_workers():
    logger = get_logger('spex.ms-job-manager')
    logger.info('Starting')
    workers = []

    worker = ArangoWorker(get_pool_size('WORKERS_POOL'))
    workers.append(worker)
    worker.start()

    for index in range(2):
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
