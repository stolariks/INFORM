import scipy
import numpy as np

from nerve_model.experiment import Experiment

def prepare_stim_protocol(
    amplitudes: list
) -> np.ndarray:
    stimulation_protocol = scipy.linalg.block_diag(*amplitudes)
    return stimulation_protocol

def simulate_fibers(
    experiment: Experiment,
    stimulation_protocol: np.ndarray
) -> list:

    assert experiment.implant.n_sites==stimulation_protocol.shape[0], "Number of active does not match the number of amplitudes"

    activations, v_ext = experiment.predict_activations(
        stimulation_protocol,
        method="from_self",
        output_potential=True
    )
    recruitment = experiment.compute_recruitment_patterns_from_activations(
        activations
    )
    fiber_cluster_ids = experiment.fiber_population.cluster_ids

    simulation_result = {
        "recruitment":  recruitment,
        "activations":  activations,
        "potentials":   v_ext,
        "cluster_ids":  fiber_cluster_ids
    }

    return simulation_result

