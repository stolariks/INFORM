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
uv run fastapi run fiber_response/main.py
```

which will start the application on `localhost:8000` on default

## Usage

For examples on how to connect and use the platform programatically see examples located in:

`fiber_response/examples`

along with acording `README.md` file on how to use them.

## Data management

Data folder used by the platform to load and store experiment files is set using the `DATA_DIR` environment variable.
This can be set in two simple ways. First is directly using the variable name before starting the platform as follows:

```sh
DATA_DIR="../data" uv run fastapi fiber_response/main.py
```

The second option is using the `.env` file which should be placed in the project root folder.
Sample environment file is provided at:

`<project_root>/.env.example`

, this can be easily adapted by creating a copy:

```sh
cp .env.example .env
```

and then editing the `.env` file accordingly.

**Data source:**
The experiment data required to run simulation can be taken from the original publication:

*Zenodo:* `10.5281/zenodo.22229593`

Sample experiment file used in the examples is copied from:

`<DATA_DIR>/Median nerve/experiments/block_10_segment_1_nerve_morphology_1/cross/experiment_trial_cross.pkl`
