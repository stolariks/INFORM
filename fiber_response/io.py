from pathlib import Path
import pickle
import numpy as np

from nerve_model.experiment import Experiment

def load_pickle(path: Path):
    with open(path, "rb") as file:
        return pickle.load(file)

def save_pickle(path: Path, obj):
    with open(path, "wb") as file:
        pickle.dump(obj, path)


def load_experiment(
    pickle_path: Path
) -> Experiment:
    with open(pickle_path, "rb") as file:
        return pickle.load(file)

def validate_response(
    response: dict
) -> dict:
    """Make sure that returned dictionary is valid type to be passed in rest"""
    for field in response:
        if isinstance(response[field], np.ndarray):
            response[field]=response[field].tolist()
    return response

