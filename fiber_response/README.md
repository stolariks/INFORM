# Get fiber responses

Use load experiment files and use them for fiber simulations


## How to install?

To install everything necessary for the `fiber_response` module first run:
```sh
uv sync --group platform
```

## How to start compute server?

After successuful installation, compute server can be started by running:
```sh
uv run fastapi run fiber_response/app.py
```
which will start the application on `localhost:8000` on default

## Data source

10.5281/zenodo.22229593

experiment file copied from:
../Median nerve/experiments/block_10_segment_1_nerve_morphology_1/cross/experiment_trial_cross.pkl"

