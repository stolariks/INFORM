from pathlib import Path
import pickle
import numpy as np
import io
import numpy as np

from fastapi import (
    HTTPException, status
)

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

def check_experiment_init(
    experiment: Experiment|None
):
    if experiment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Experiment not initialized"
        )

def to_npz(**arrays) -> bytes:
    buf = io.BytesIO()
    np.savez(buf, **arrays)
    return buf.getvalue()

def validate_response(
    response: dict
) -> dict:
    """Make sure that returned dictionary is valid type to be passed in rest"""
    for field in response:
        if isinstance(response[field], np.ndarray):
            response[field]=response[field].tolist()
    return response

