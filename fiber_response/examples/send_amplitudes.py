"""
@file: send_amplitudes.py
@author: Samuel Stolarik
@description:
    Example file showing how connections
    to the platform API can be made and
    how the simulation request response
    should be processed
"""

import io

import httpx
import numpy as np
from fiber_response.examples.init_experiment import (
    DEFAULT_FILENAME, send_load_request
)

BASE_URL="http://127.0.0.1:8000"

if __name__=="__main__":
    # Load an experiment file (for more see: examples/init_experiment.py)
    msg = send_load_request(DEFAULT_FILENAME)
    print(f"Load experiment result:\n\t{msg}")

    # Example amplitude values
    # you must ensure that the number
    # of amplitude values sent is equal
    # to the number of active sites
    amplitudes = [10, 10, 10, 10,
                  10, 10, 10, 10]

    request = httpx.put(
        # /compute/simulate is the simulation endpoint of the platoform
        f"{BASE_URL}/compute/simulate",
        # simulation request parameters
        json={"amplitudes": amplitudes},
        # increase timeout to allow simulation computing time (default: 5s)
        timeout=300
    )

    if request.status_code != 200:  # 200 stands for OK
        raise RuntimeError(f"Server returned {request.status_code}: {request.text}")


    # Recreate numpy arrays from received binary data
    buf = io.BytesIO(request.content)  # create buffer containing received data
    with np.load(buf, allow_pickle=False) as data:
        # Separate the request binary into respective result arrays
        recruitments =  data["recruitments"]
        activations =   data["activations"]
        potentials =    data["potentials"]

    print("recruitments:", recruitments.shape, recruitments.dtype)
    print("activations: ", activations.shape, activations.dtype)
    print("potentials:  ", potentials.shape, potentials.dtype)

