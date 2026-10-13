"""
@file: init_experiment.py
@author: Samuel Stolarik
@description:
    Example file whowing how to
    load and initialize an
    experiment from an chosen
    pickle file available on
    the server
"""

from pathlib import Path
import httpx

BASE_URL="http://127.0.0.1:8000"
DEFAULT_FILENAME = "experiment_trial_cross.pkl"


def send_load_request(
    filename: Path
):
    # This is a request with parameters encoded
    # in the URL not send as data section,
    # therefore use parameter "params"
    request = httpx.post(
        f"{BASE_URL}/exp/experiment",
        params={"filename": filename}
    )

    if request.status_code != 201: # Load success
        raise RuntimeError(f"File not created correctly")
    return request.text

if __name__=="__main__":
    msg = send_load_request(
        DEFAULT_FILENAME
    )
    print(msg)

