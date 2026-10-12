"""
@file: get_fiber_info.py
@author: Samuel Stolarik
@description:
    Example file showing how to
    get fiber information such
    as diameter or cluster belongings

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

    request = httpx.get(
        # same can be done for /exp/fiber/clusters
        f"{BASE_URL}/exp/fiber/diameters"
    )

    if request.status_code != 200:
        raise RuntimeError(f"Server returned {request.status_code}: {request.text}")

    # For more detailed explanation of the following code see:
    # examples/send_amplitudes.py
    buf = io.BytesIO(request.content)
    with np.load(buf, allow_pickle=False) as data:
        fiber_diameters = data["diameters"]

    print("diameters:", fiber_diameters.shape, fiber_diameters.dtype)

