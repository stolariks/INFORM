from pathlib import Path
import io
import matplotlib.pyplot as plt

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response

from nerve_model.experiment import Experiment
from fiber_response.schema import ComputeRequest
from fiber_response.io import load_experiment, validate_response
from fiber_response.simulate import prepare_stim_protocol, simulate_fibers

DEFAULT_MODEL_FOLDER = Path("fiber_response")
experiment: Experiment|None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load default experiment file
    global experiment
    experiment = load_experiment(
        DEFAULT_MODEL_FOLDER / "experiment_trial_cross.pkl"
    )
    yield


app = FastAPI(lifespan=lifespan)

@app.put("/api/simulate")
async def run_simulation(request: ComputeRequest):
    stimulation_protocol = prepare_stim_protocol(
        request.amplitudes
    )
    result = simulate_fibers(
        experiment=experiment,
        stimulation_protocol=stimulation_protocol
    )

    result['diameters'] = experiment.fiber_population.diameters

    return validate_response(result)

@app.get("/api/experiment")
async def experiment_info():
    global experiment
    info = {
        "fibers": experiment.fiber_population.n_fibers,
        "groups": experiment.fiber_population.n_groups,
        "active_sites": experiment.implant.n_sites
    }
    return info

@app.get("/api/plot")
async def plot_experiment():
    global experiment
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot()
    experiment.plot(ax)
    experiment.fiber_population.plot(ax)

    img_buf = io.BytesIO()
    fig.savefig(img_buf, format='png')
    plt.close(fig)

    headers = {'Content-Disposition': 'inline; filename="out.png"'}
    return Response(img_buf.getvalue(), headers=headers, media_type='image/png')


if __name__=="__main__":
    exp_dir = Path("fiber_response")
    experiment = load_experiment(exp_dir / "experiment_trial_cross.pkl")
    amplitudes = [10] * experiment.implant.n_sites

    result = simulate_fibers(
        experiment, amplitudes
    )

    print(result)

