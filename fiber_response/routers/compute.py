from fastapi import (
    APIRouter, Request, HTTPException,
    status
)

import numpy as np
import numpy2 as np2

from fiber_response.schema import ComputeRequest
from fiber_response.core.simulate import (
    prepare_stim_protocol,
    simulate_fibers
)

router = APIRouter(
    prefix="/compute",
    tags=["Compute"]
)


@router.put("/simulate")
async def run_simulation(
    compute_request: ComputeRequest,
    request: Request
):
    experiment = request.app.state.experiment
    if experiment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Experiment is not initialized"
        )
    stimulation_protocol = prepare_stim_protocol(
        compute_request.amplitudes
    )
    result = simulate_fibers(
        experiment=experiment,
        stimulation_protocol=stimulation_protocol
    )

    # TODO: binarize named arrays with np.savez and send over
    for key in result:
        if isinstance(result[key], np.ndarray):
            result[key] = np2.serialize(result[key])

    return result

