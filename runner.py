from app import run
import dill as pickle
import os


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
    print(f'current env: {env}')
    try:
        result = run(**get(__file__))

        if not (result and len(result.keys()) > 0):
            exit(2)

        put(__file__, result)
        put_anndata(__file__, result)
    except Exception as e:
        raise e
