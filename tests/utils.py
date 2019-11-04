import os


def get_data_set_file():
    base_dir = os.path.dirname(__file__)
    filename = os.path.join(base_dir, 'data/dataset.yaml')

    return filename




