import dill as pickle
import os
import psutil
import logging
import time
import re

from app import run

def put_anndata(name, data):
    if 'adata' in data.keys():
        import anndata as ad
        filename, ext = os.path.splitext(name)
        filename = f'{filename}.h5ad'
        try:
            ad.AnnData.write(data['adata'], filename)
        except TypeError:
            print('cannot convert anndata to h5ad, skipping')
    else:
        return

def get(name):
    filename, ext = os.path.splitext(name)
    filename = f'{filename}.pickle'
    with open(filename, "rb") as infile:
        data = pickle.load(infile)
        return data

def put(name, data):
    filename, ext = os.path.splitext(name)
    filename = f'{filename}.pickle'
    with open(filename, "wb") as outfile:
        pickle.dump(data, outfile)

if __name__ == '__main__':
    env = os.environ.get("VIRTUAL_ENV", None)
    if env is None:
        env = os.environ.get("CONDA_PREFIX", None)
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    start_time = time.time()
    logger.info(f'current env: {env}')
    if env:
        parts = re.split(r'[\\/]+', env)
        env_short = os.sep.join(parts[-2:])
    else:
        env_short = "None"
    try:
        result = run(**get(__file__))
        process = psutil.Process()
        memory_info = process.memory_info()
        end_time = time.time()
        logger.info(
            f"Memory usage: RSS={memory_info.rss / (1024 * 1024):.2f} MB, "
            f"VMS={memory_info.vms / (1024 * 1024):.2f} MB, "
            f"PATH={env_short}, "
            f"TIME={end_time - start_time:.2f} seconds"
            f"Start time={time.strftime('%H:%M:%S', time.localtime(start_time))} "
            f"End time={time.strftime('%H:%M:%S', time.localtime(end_time))} "
        )

        if not (result and len(result.keys()) > 0):
            exit(2)

        put(__file__, result)
        put_anndata(__file__, result)
    except Exception as e:
        raise e
