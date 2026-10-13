from fastapi import (
    APIRouter, Request, HTTPException,
    status, Response
)

import numpy as np

from fiber_response.schema import ComputeRequest
from fiber_response.core.io import check_experiment_init, to_npz
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
    check_experiment_init(experiment)

    stimulation_protocol = prepare_stim_protocol(
        compute_request.amplitudes
    )
    result = simulate_fibers(
        experiment=experiment,
        stimulation_protocol=stimulation_protocol
    )

    return Response(
       to_npz(
           recruitments=result["recruitments"],
           activations=result['activations'],
           potentials=result['potentials']
       ),
       media_type="application/octet-stream"
    )

