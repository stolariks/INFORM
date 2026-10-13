from pathlib import Path
from typing import Annotated
import matplotlib.pyplot as plt
import io

import numpy as np
import numpy2 as np2

from fastapi import (
    APIRouter, Depends, Request,
    status, HTTPException, Response
)

from fiber_response.dependencies import Settings, get_settings
from fiber_response.core.io import load_experiment

router = APIRouter(
    prefix="/exp",
    tags=["Experiment"]
)

@router.get("/experiment/",
            status_code=status.HTTP_200_OK,
            responses={
                status.HTTP_404_NOT_FOUND: {
                    "description": "Experiment not initialized"
                }
            }
)
async def get_experiment(request: Request):
    exp = request.app.state.experiment
    if exp is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Experiment not initialized"
        )

    info = {
        "fibers": exp.fiber_population.n_fibers,
        "groups": exp.fiber_population.n_groups,
        "active_sites": exp.implant.n_sites
    }
    return info

@router.post("/experiment",
            status_code=status.HTTP_201_CREATED
)
async def load_experiement(
    filename: Path,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)]
):
    ddir = settings.data_dir.resolve()
    if not (ddir/filename).exists():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"File not found {ddir/filename}"
        )

    experiment = load_experiment(ddir/filename)
    request.app.state.experiment = experiment

    return f"Experiment loaded successfully from {ddir/filename}" 


@router.get("/plot",
            status_code=status.HTTP_200_OK
)
async def plot_experiment(request: Request):
    exp = request.app.state.experiment
    if exp is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Experiment not initialized"
        )

    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot()
    exp.plot(ax)
    exp.fiber_population.plot(ax)

    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", dpi=300)
    plt.close(fig)

    headers = {'Content-Disposition': 'inline; filename="out.png"'}
    return Response(img_buf.getvalue(), headers=headers, media_type='image/png')


@router.get("/diameters",
            status_code=status.HTTP_200_OK
)
async def get_diameters(request: Request):
    exp = request.app.state.experiment
    if exp is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Experiment not initialized"
        )
    return np2.serialize(exp.fiber_population.diameters)

