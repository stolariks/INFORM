"""Motor fiber population utilities for INFORM nerve models."""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.stats import multivariate_normal
from tqdm.auto import tqdm


DEFAULT_DIAMETER_LIMS = (12.0, 20.0)  # micrometers, A-alpha range
DEFAULT_FEM_LENGTH_MM = 20.0
DEFAULT_PROPAGATION_NODES = 10
MRG_COMPARTMENTS_PER_INTERNODE = 11


class MotorFiberPopulation:
    """Population of motor fibers organized into functional clusters.

    Parameters
    ----------
    n_internodes : int
        Number of internodes in each modeled fiber.
    diameters : ndarray, shape (n_fibers,)
        Fiber diameters in micrometers.
    locs : ndarray, shape (n_fibers, 2)
        Fiber locations in the nerve transverse section, in millimeters.
    cluster_ids : ndarray, optional
        Cluster identifier for each fiber. If omitted, all fibers are assigned
        to a single cluster.
    cluster_locs : ndarray, optional
        Cluster center locations in the nerve transverse section, in millimeters.
    cluster_std : ndarray, optional
        Isotropic spatial standard deviation of each cluster, in millimeters.
    cluster_num : ndarray, optional
        Number of fibers in each cluster.
    central_node_z : {"zero", "random"}
        Generation mode for the longitudinal location of the Ranvier node
        closest to z = 0.
    nerve_topography : object, optional
        Nerve section object used to sample points and store fascicle metadata.
    central_z : ndarray, optional
        Predefined central-node z offsets for each fiber, in micrometers.
    cc : bool
        If True and cluster features are not provided, estimate cluster centers,
        dispersions, and counts from the provided fiber locations and labels.
    """

    def __init__(
        self,
        n_internodes: int,
        diameters: np.ndarray,
        locs: np.ndarray,
        cluster_ids: np.ndarray | None = None,
        cluster_locs: np.ndarray | None = None,
        cluster_std: np.ndarray | None = None,
        cluster_num: np.ndarray | None = None,
        central_node_z: Literal["zero", "random"] = "random",
        nerve_topography=None,
        central_z: np.ndarray | None = None,
        n_groups: int = 1,
        cc: bool = False,
    ) -> None:
        diameters = np.asarray(diameters)
        locs = np.asarray(locs)

        if diameters.shape[0] != locs.shape[0]:
            raise ValueError(
                "Dimension mismatch between diameters and locs: "
                f"diameters has first dimension {diameters.shape[0]}, "
                f"while locs has first dimension {locs.shape[0]}."
            )
        if locs.ndim != 2 or locs.shape[1] != 2:
            raise ValueError("locs must have shape (n_fibers, 2).")
        if central_node_z not in {"zero", "random"}:
            raise ValueError("central_node_z must be either 'zero' or 'random'.")

        self._n_groups = n_groups
        self._n_internodes = int(n_internodes)
        self._diameters = diameters.astype(float)
        self._locs = locs.astype(float)
        self.central_z = central_z

        if cluster_ids is None:
            self._cluster_ids = np.zeros(self.n_fibers, dtype=int)
        else:
            self._cluster_ids = np.asarray(cluster_ids).astype(int)
            if self._cluster_ids.shape[0] != self.n_fibers:
                raise ValueError("cluster_ids must have one entry per fiber.")

        self._n_groups = np.unique(self._cluster_ids).size

        if cluster_locs is None and cc:
            cluster_locs, cluster_std, cluster_num = self._estimate_cluster_features()

        self._cluster_locs = cluster_locs
        self._cluster_std = cluster_std
        self._cluster_num = cluster_num

        self._nerve_topography = nerve_topography
        self._n_fascicles = getattr(nerve_topography, "n_fascicles", None)
        self._central_node_z = central_node_z

        self._fiber_ids = None
        self._node_locs = None
        self._node_ids = None
        self._fem_node_locs = None
        self._fem_node_fiber_ids = None

        self.n_lbound = None
        self.n_fem = None
        self.n_prop = None
        self.n_ubound = None
        self.locs_ranvier = None
        self.fem_node_lims = None

        self.generate_mrg_node_locs()

    def __repr__(self) -> str:
        group_word = "group" if self.n_groups == 1 else "groups"
        out = (
            f"MotorFiberPopulation containing {self.n_fibers} fibers, "
            f"divided into {self.n_groups} {group_word}\n"
        )

        if self.cluster_locs is not None:
            for i in range(self.n_groups):
                out += f"* Group {i}:\n"
                out += f"    - group location: {self.cluster_locs[i]}\n"
                out += f"    - group dispersion: {self.cluster_std[i]}\n"
                out += f"    - group numerosity: {self.cluster_num[i]}\n"
        return out

    def _estimate_cluster_features(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Estimate cluster centers, dispersions, and counts from fiber labels."""
        ids = np.sort(np.unique(self.cluster_ids))
        cluster_locs = np.zeros((ids.size, 2))
        cluster_std = np.zeros(ids.size)
        cluster_num = np.zeros(ids.size, dtype=int)

        for out_idx, cluster_id in enumerate(ids):
            cluster_locs_i = self.locs[self.cluster_ids == cluster_id]
            cluster_locs[out_idx] = np.mean(cluster_locs_i, axis=0)
            cluster_std[out_idx] = np.mean(np.std(cluster_locs_i, axis=0))
            cluster_num[out_idx] = cluster_locs_i.shape[0]

        return cluster_locs, cluster_std, cluster_num

    @classmethod
    def from_clusters(  # TODO: maybe this could be used with cluster_locs sampled inside fascicles
        cls,
        n_internodes: int,
        diameter_lims: tuple[float, float],
        cluster_locs: np.ndarray,
        cluster_std: np.ndarray,
        cluster_num: np.ndarray,
        central_node_z: Literal["zero", "random"] = "zero",
    ) -> "MotorFiberPopulation":
        """Create a population by sampling Gaussian clusters in 2D space."""
        _validate_cluster_features(cluster_locs, cluster_std, cluster_num)

        cluster_num = np.asarray(cluster_num, dtype=int)
        group_lims = np.concatenate(([0], np.cumsum(cluster_num)))
        n_fibers = int(np.sum(cluster_num))
        n_groups = cluster_locs.shape[0]

        locs = np.zeros((n_fibers, 2))
        cluster_ids = np.zeros(n_fibers, dtype=int)
        diameters = np.zeros(n_fibers)

        for i in range(n_groups):
            start, stop = group_lims[i], group_lims[i + 1]
            locs[start:stop, :] = multivariate_normal.rvs(
                mean=cluster_locs[i],
                cov=cluster_std[i] ** 2,
                size=cluster_num[i],
            )
            cluster_ids[start:stop] = i
            diameters[start:stop] = _sample_uniform_diameters(cluster_num[i], diameter_lims)

        return cls(
            n_internodes=n_internodes,
            diameters=diameters,
            locs=locs,
            cluster_ids=cluster_ids,
            cluster_locs=cluster_locs,
            cluster_std=cluster_std,
            cluster_num=cluster_num,
            central_node_z=central_node_z,
        )

    @classmethod
    def from_fascicles_and_clusters(
        cls,
        n_internodes: int,
        diameter_lims: tuple[float, float],
        cluster_locs: np.ndarray,
        cluster_std: np.ndarray,
        cluster_num: np.ndarray,
        nerve_topography,
        central_node_z: Literal["zero", "random"] = "zero",
        admissible_locs: np.ndarray | None = None,
        n_admissible: int = 100_000,
        return_identities: bool = False,
    ):
        """Create a population by sampling Gaussian clusters inside fascicles."""
        _validate_cluster_features(cluster_locs, cluster_std, cluster_num)

        cluster_num = np.asarray(cluster_num, dtype=int)
        n_fibers = int(np.sum(cluster_num))
        n_groups = cluster_locs.shape[0]

        locs = np.zeros((n_fibers, 2))
        cluster_ids = np.zeros(n_fibers, dtype=int)
        diameters = np.zeros(n_fibers)
        identities = np.zeros(n_fibers, dtype=int)

        if admissible_locs is None:
            admissible_locs = nerve_topography.sample_points_in_fascicles(
                n_points=n_admissible
            )
        else:
            admissible_locs = np.asarray(admissible_locs)
            n_admissible = admissible_locs.shape[0]

        group_lims = np.concatenate(([0], np.cumsum(cluster_num)))
        for i in range(n_groups):
            start, stop = group_lims[i], group_lims[i + 1]
            location_prob = _gaussian_sampling_probabilities(
                points=admissible_locs,
                mean=cluster_locs[i],
                std=cluster_std[i],
            )
            idx = np.random.choice(
                a=n_admissible,
                size=cluster_num[i],
                p=location_prob,
                replace=False,
            )
            identities[start:stop] = idx
            locs[start:stop, :] = admissible_locs[idx, :]
            cluster_ids[start:stop] = i
            diameters[start:stop] = _sample_uniform_diameters(cluster_num[i], diameter_lims)

        obj = cls(
            n_internodes=n_internodes,
            diameters=diameters,
            locs=locs,
            cluster_ids=cluster_ids,
            cluster_locs=cluster_locs,
            cluster_std=cluster_std,
            cluster_num=cluster_num,
            nerve_topography=nerve_topography,
            central_node_z=central_node_z,
        )

        if return_identities:
            return obj, identities
        return obj

    @classmethod
    def from_existing_population(
        cls,
        fiber_population: "MotorFiberPopulation",
        group_ids=None,
        cluster_locs: np.ndarray | None = None,
        cluster_std: np.ndarray | None = None,
        cluster_num: np.ndarray | None = None,
    ):
        """Create a subset or resampled population from an existing population.

        Either ``group_ids`` or the cluster features ``cluster_locs``,
        ``cluster_std``, and ``cluster_num`` must be provided.
        """
        if group_ids is not None:
            return cls._from_existing_group_ids(fiber_population, group_ids)

        if cluster_locs is None or cluster_std is None or cluster_num is None:
            raise ValueError(
                "Provide either group_ids or all of cluster_locs, "
                "cluster_std, and cluster_num."
            )

        _validate_cluster_features(cluster_locs, cluster_std, cluster_num)
        cluster_num = np.asarray(cluster_num, dtype=int)
        n_groups = cluster_locs.shape[0]
        n_fibers = int(np.sum(cluster_num))

        locs = np.zeros((n_fibers, 2))
        cluster_ids = np.zeros(n_fibers, dtype=int)
        diameters = np.zeros(n_fibers)
        identities = np.zeros(n_fibers, dtype=int)
        central_z = np.zeros(n_fibers)

        group_lims = np.concatenate(([0], np.cumsum(cluster_num)))
        for i in range(n_groups):
            start, stop = group_lims[i], group_lims[i + 1]
            location_prob = _gaussian_sampling_probabilities(
                points=fiber_population.locs,
                mean=cluster_locs[i],
                std=cluster_std[i],
            )
            idx = np.random.choice(
                a=fiber_population.n_fibers,
                size=cluster_num[i],
                p=location_prob,
                replace=False,
            )
            identities[start:stop] = idx
            locs[start:stop, :] = fiber_population.locs[idx, :]
            cluster_ids[start:stop] = i
            diameters[start:stop] = fiber_population.diameters[idx]
            central_z[start:stop] = fiber_population.central_z[idx]

        obj = cls(
            n_internodes=fiber_population.n_internodes,
            diameters=diameters,
            locs=locs,
            cluster_ids=cluster_ids,
            cluster_locs=cluster_locs,
            cluster_std=cluster_std,
            cluster_num=cluster_num,
            nerve_topography=fiber_population.nerve_topography,
            central_z=central_z,
        )
        return obj, identities

    @classmethod
    def _from_existing_group_ids(cls, fiber_population, group_ids):
        group_ids = np.atleast_1d(group_ids)
        n_groups = len(group_ids)

        locs_list = []
        diameters_list = []
        identities_list = []
        cluster_ids_list = []

        for new_id, old_id in enumerate(group_ids):
            mask = fiber_population.cluster_ids == old_id
            locs_i = fiber_population.locs[mask, :]
            diameters_i = fiber_population.diameters[mask]
            identities_i = np.flatnonzero(mask)

            locs_list.append(locs_i)
            diameters_list.append(diameters_i)
            identities_list.append(identities_i)
            cluster_ids_list.append(np.full(locs_i.shape[0], new_id, dtype=int))

        locs = np.vstack(locs_list)
        diameters = np.hstack(diameters_list)
        identities = np.hstack(identities_list).astype(int)
        cluster_ids = np.hstack(cluster_ids_list)
        cluster_num = np.array([locs_i.shape[0] for locs_i in locs_list], dtype=int)

        obj = cls(
            n_internodes=fiber_population.n_internodes,
            diameters=diameters,
            locs=locs,
            cluster_ids=cluster_ids,
            cluster_locs=fiber_population.cluster_locs[group_ids, :]
            if fiber_population.cluster_locs is not None
            else None,
            cluster_std=fiber_population.cluster_std[group_ids]
            if fiber_population.cluster_std is not None
            else None,
            cluster_num=cluster_num,
            nerve_topography=fiber_population.nerve_topography,
            central_z=fiber_population.central_z[identities],
            n_groups=n_groups,
        )
        return obj, identities

    @classmethod
    def from_fascicles(
        cls,
        nerve_topography,
        n_internodes: int,
        mode: Literal["random", "fascicular", "unique"] = "random",
        n_fibers: int | None = None,
        density: float | None = None,
        n_clusters: int | None = None,
    ) -> "MotorFiberPopulation":
        """Create a population by sampling points within nerve fascicles."""
        if density is not None:
            n_fibers = int(np.round(nerve_topography.total_area * density))

        if mode in {"fascicular", "unique"}:
            locs, cluster_ids = nerve_topography.sample_points_in_fascicles(
                n_points=n_fibers
            )
        elif mode == "random":
            if n_clusters is None:
                raise ValueError("n_clusters must be provided when mode='random'.")
            cluster_locs, cluster_std, cluster_num = generate_random_cluster_features(
                n_clusters=n_clusters,
                nerve_radius=nerve_topography.nerve_radius,
                std_lims=(0.05, 0.35),
                num_lims=(100, 200),
            )
            return cls.from_fascicles_and_clusters(
                n_internodes=n_internodes,
                cluster_locs=cluster_locs,
                cluster_std=cluster_std,
                cluster_num=cluster_num,
                diameter_lims=DEFAULT_DIAMETER_LIMS,
                nerve_topography=nerve_topography,
            )
        else:
            raise ValueError(
                "Parameter mode can only have values 'random', 'fascicular', "
                "or 'unique'."
            )

        if mode == "unique":
            cluster_ids = None

        diameters = _sample_uniform_diameters(n_fibers, DEFAULT_DIAMETER_LIMS)
        return cls(
            n_internodes=n_internodes,
            diameters=diameters,
            locs=locs,
            cluster_ids=cluster_ids,
        )

    @staticmethod
    def plot_mrg_internode_spacing(
        spacing_internode,
        # Values taken from code bellow in generate_mrg_node_locs
        length_ranvier=1.0,
        length_mysa=3.0,
        length_flut=50.0,
        length_stin=219.46,
    ):
        """Plots the physical compartments of an MRG repeat unit alongside the center-to-center

        spacing distances (`spacing_internode`).
        """
        import matplotlib.pyplot as plt
        # 1. Define ordered compartment sequence and their physical lengths
        # (11 compartments total: Node -> MYSA -> FLUT -> 6x STIN -> FLUT -> MYSA -> Node)
        comp_names = [
            "Node",
            "MYSA",
            "FLUT",
            "STIN 1",
            "STIN 2",
            "STIN 3",
            "STIN 4",
            "STIN 5",
            "STIN 6",
            "FLUT",
            "MYSA",
            "Node 2",
        ]
        comp_lengths = [
            length_ranvier,
            length_mysa,
            length_flut,
            length_stin,
            length_stin,
            length_stin,
            length_stin,
            length_stin,
            length_stin,
            length_flut,
            length_mysa,
            length_ranvier,
        ]

        # Color palette for distinct compartment types
        color_map = {
            "Node": "#2b5c8f",
            "MYSA": "#1f1f1f",
            "FLUT": "#d95f02",
            "STIN": "#e6ab02",
        }

        # 2. Calculate physical boundaries and midpoints along the z-axis
        comp_boundaries = np.zeros(len(comp_lengths) + 1)
        comp_boundaries[1:] = np.cumsum(comp_lengths)

        # Shift so that the first Node center is at z = 0
        comp_boundaries -= length_ranvier / 2
        comp_centers = (comp_boundaries[:-1] + comp_boundaries[1:]) / 2

        # Setup plot
        fig, (ax_fiber, ax_spacing) = plt.subplots(
            2, 1, figsize=(14, 7), sharex=True, gridspec_kw={"height_ratios": [1, 2]}
        )

        # ---------------------------------------------------------
        # Top Subplot: Drawn Fiber Compartments with Name Labels
        # ---------------------------------------------------------
        for i, name in enumerate(comp_names):
            start = comp_boundaries[i]
            width = comp_lengths[i]
            c_type = name.split()[0]
            color = color_map.get(c_type, "#999999")

            # Draw cylinder box representing compartment
            ax_fiber.barh(
                y=0,
                width=width,
                left=start,
                height=0.4,
                color=color,
                edgecolor="black",
                linewidth=0.8,
            )

            # Plot compartment midpoint
            ax_fiber.plot(comp_centers[i], 0, "r.", markersize=4)

            # Annotate compartment name above/below to prevent overlap for narrow segments
            is_narrow = width < 20.0
            text_y = 0.35 if is_narrow and (i % 2 == 0) else 0.28
            rotation = 90 if is_narrow else 0
            font_size = 7 if is_narrow else 8.5
            text_color = "black"

            ax_fiber.text(
                comp_centers[i],
                text_y,
                name,
                ha="center",
                va="bottom",
                fontsize=font_size,
                fontweight="bold",
                color=text_color,
                rotation=rotation,
            )

        ax_fiber.set_yticks([])
        ax_fiber.set_title("MRG Fiber Compartment Anatomy", fontsize=12, fontweight="bold")
        ax_fiber.set_ylim(-0.4, 0.9)

        # ---------------------------------------------------------
        # Bottom Subplot: Center-to-Center Spacing Steps
        # ---------------------------------------------------------
        for i, dist in enumerate(spacing_internode):
            z_start = comp_centers[i]
            z_end = comp_centers[i + 1]
            z_mid = (z_start + z_end) / 2

            # Draw step horizontal line connecting adjacent midpoints
            ax_spacing.hlines(
                y=dist,
                xmin=z_start,
                xmax=z_end,
                colors="#2b5c8f",
                linewidth=2,
                label="spacing_internode" if i == 0 else "",
            )
            ax_spacing.plot([z_start, z_end], [dist, dist], "o", color="#2b5c8f", markersize=4)

            # Annotate distance values above steps
            y_offset = max(spacing_internode) * 0.03
            ax_spacing.text(
                z_mid,
                dist + y_offset,
                f"{dist:.1f} µm",
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=45 if dist < 50 else 0,
            )

        ax_spacing.set_ylabel("Spacing Distance (µm)", fontsize=10)
        ax_spacing.set_xlabel("Fiber Axial Position z (µm)", fontsize=10)
        ax_spacing.set_title(
            "Center-to-Center Spacing (`spacing_internode`) Between Midpoints",
            fontsize=12,
            fontweight="bold",
        )
        ax_spacing.grid(True, linestyle="--", alpha=0.5)

        plt.tight_layout()
        plt.savefig("internodes.svg")


    def generate_mrg_node_locs(self) -> None:
        #breakpoint()
        # TODO: understand if the generated node locations contain randomized delta offset
        """Generate MRG node locations and FEM node indexing for all fibers."""
        length_mysa = 3.0  # MYelin Sheet Attachment
        length_ranvier = 1.0  # Node of ranvier
        n_nodes_per_fiber = self.n_nodes

        node_ids = np.zeros((self.n_fibers, n_nodes_per_fiber))  # TODO: seems to be categorical array maping where fem is calculated? see bellow
        n_lbound = np.zeros(self.n_fibers, dtype=int)
        n_fem = np.zeros(self.n_fibers, dtype=int)
        n_prop = np.zeros(self.n_fibers, dtype=int)
        n_ubound = np.zeros(self.n_fibers, dtype=int)
        locs_all_nodes = np.zeros((self.n_fibers, n_nodes_per_fiber))
        locs_fem_nodes = []
        fem_node_fiber_ids = []
        locs_ranvier = []

        self.fem_node_lims = np.zeros((self.n_fibers, 2))
        ind_first_node = 0
        central_z = np.zeros(self.n_fibers)

        #breakpoint()
        for i in tqdm(range(self.n_fibers), desc=""):
            length_internode = 969.3 * np.log(self.diameters[i]) - 1144.6  # total node-to-node length (repeat length), which includes the nodal gap plus all myelinated/paranodal segments between two nodes
            # length_internode = node + 2*MYSA + 2*FLUT + 6*STIN

            length_flut = 2.5811 * self.diameters[i] + 19.59
            length_stin = (  # length of one of the six STIN sub-compartments (STIN = Stereotyped Internode)
                # the substractions remove everything else and leave just the length of six internodal segments (6xSTIM) so it then needs to be devided by 6
                length_internode
                - length_ranvier
                - (2 * length_mysa)
                - (2 * length_flut)
            ) / 6

            # see also image at: (see picture https://wmglab-duke.github.io/pyfibers/fiber_models.html#construction-of-model-fibers)
            spacing_internode = np.array(
                [
                    (length_ranvier + length_mysa) / 2,
                    (length_mysa + length_flut) / 2,
                    (length_flut + length_stin) / 2,
                    length_stin,
                    length_stin,
                    length_stin,
                    length_stin,
                    length_stin,
                    (length_stin + length_flut) / 2,
                    (length_flut + length_mysa) / 2,
                    (length_mysa + length_ranvier) / 2,
                ]
            )

            # added for debug
            # MotorFiberPopulation.plot_mrg_internode_spacing(spacing_internode)
            # #breakpoint()
            # kill the code after breakpoint

            n_fem_theor = int(np.floor(DEFAULT_FEM_LENGTH_MM * 1000 / length_internode))  # ~ 13 => Theoretical number of internodes (nodes of Ranvier) that fit inside the 3D finite element simulation domain length (DEFAULT_FEM_LENGTH_MM).
            n_bound_theor = (  # ~9 => leftover nodes that are not part of the active FEM area or propagation area, divided by 2 to split them equally between the left boundary (n_lbound) and right boundary (n_ubound).
                (self.n_internodes + 1) - n_fem_theor - DEFAULT_PROPAGATION_NODES
            ) / 2
            n_lbound_theor = int(np.ceil(n_bound_theor))

            spacing_fiber = np.tile(spacing_internode, self.n_internodes)  # repeat internode spacing array for n_internode times => for 40 internodes this makes 440 compartments
            locs_fiber = np.concatenate(([0], np.cumsum(spacing_fiber)))  # positions of each fiber compartment placed on one axis => 0 and 440 values => [441,]
            locs_fiber -= length_internode * (
                n_lbound_theor + np.floor(n_fem_theor / 2)
            )  # z = 0 corresponds to the center of the FEM electrode/model region

            if self.central_z is None:
                if self.central_node_z == "random":
                    central_z[i] = np.random.rand() * length_internode - length_internode / 2  # introduce random delta z
                else:
                    central_z[i] = 0.0
            else:
                central_z[i] = self.central_z[i]

            locs_nodes_mm = (locs_fiber + central_z[i]) / 1000
            locs_all_nodes[i, :] = locs_nodes_mm
            locs_ranvier.append(locs_nodes_mm[0::MRG_COMPARTMENTS_PER_INTERNODE])  # every MRG_COM..INTERNODE node is set as ranvier

            node_ids[i, locs_nodes_mm <= -DEFAULT_FEM_LENGTH_MM / 2] = 0
            is_fem_region = np.logical_and(
                locs_nodes_mm > -DEFAULT_FEM_LENGTH_MM / 2,
                locs_nodes_mm <= DEFAULT_FEM_LENGTH_MM / 2,
            )
            node_ids[i, is_fem_region] = 1

            last_fem_node = np.min(np.nonzero(locs_nodes_mm > DEFAULT_FEM_LENGTH_MM / 2))
            node_ids[i, last_fem_node : last_fem_node + DEFAULT_PROPAGATION_NODES] = 2
            node_ids[i, last_fem_node + DEFAULT_PROPAGATION_NODES :] = 3

            ranvier_node_ids = node_ids[i, 0::MRG_COMPARTMENTS_PER_INTERNODE]
            n_lbound[i] = np.sum(ranvier_node_ids == 0)
            n_fem[i] = np.sum(ranvier_node_ids == 1)
            n_prop[i] = np.sum(ranvier_node_ids == 2)
            n_ubound[i] = np.sum(ranvier_node_ids == 3)

            new_fem_nodes = locs_all_nodes[i, node_ids[i, :] == 1]  # select fiber nodes in the FEM region
            n_new_fem_nodes = new_fem_nodes.size
            new_fem_nodes = np.hstack(  # these are the fiber compartments in the FEM region
                (
                    np.tile(self.locs[i, :], [n_new_fem_nodes, 1]), # xy coordinates along the FEM PARTITION of the fiber (constant) <= therefore repeat self.locs[i, ] for number of nodes
                    np.expand_dims(new_fem_nodes, 1), # z coordinates changing along the nerve ONLY IN THE FEM PARTITION
                )
            )
            locs_fem_nodes.append(new_fem_nodes)
            fem_node_fiber_ids.append(np.full(n_new_fem_nodes, i, dtype=int))  # assign all created nodes an index (fiber index)
            self.fem_node_lims[i, :] = [
                ind_first_node,
                ind_first_node + n_new_fem_nodes,
            ]
            ind_first_node += n_new_fem_nodes

        self._node_locs = locs_all_nodes
        self._node_ids = node_ids
        self._fem_node_locs = np.vstack(locs_fem_nodes)
        #breakpoint()
        self._fem_node_fiber_ids = np.hstack(fem_node_fiber_ids) # when new fibers are generated, different number of nodes is included in the FEM partition
        self.n_lbound = n_lbound
        self.n_fem = n_fem
        self.n_prop = n_prop
        self.n_ubound = n_ubound
        self.locs_ranvier = np.vstack(locs_ranvier)
        self.central_z = central_z

    def plot(self, ax, groups=-1, color_list=None, show_fascicles: bool = True) -> None:
        """Plot fiber locations by cluster.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Axis where the fiber locations are plotted.
        groups : int or iterable, default=-1
            Cluster(s) to plot. Use -1 to plot all clusters.
        color_list : sequence, optional
            Optional colors for each cluster.
        show_fascicles : bool
            Kept for backward compatibility; fascicles are not plotted here.
        """
        _ = show_fascicles
        if groups == -1:
            groups = range(self.n_groups)
        elif np.isscalar(groups):
            groups = [groups]

        for i in groups:
            idx = np.where(self.cluster_ids == i)
            if color_list is not None:
                ax.scatter(self.locs[idx, 0], self.locs[idx, 1], alpha=0.1, c=color_list[i])
            else:
                ax.scatter(self.locs[idx, 0], self.locs[idx, 1], alpha=0.1)

    def plot_node_locs(self, ax, length_fem: float, n_fibers_to_show: int = 10) -> None:
        """Plot Ranvier node locations for a subset of fibers."""
        ax.axvline(x=-length_fem / 2, color="red", linestyle="--")
        ax.axvline(x=length_fem / 2, color="red", linestyle="--")
        for i in range(n_fibers_to_show):
            ax.scatter(self.locs_ranvier[i], np.ones(self.n_internodes + 1) * i, color="black")
            idx_fem_nodes = np.arange(self.n_lbound[i], self.n_lbound[i] + self.n_fem[i])
            ax.scatter(
                self.locs_ranvier[i][idx_fem_nodes],
                np.ones(self.n_fem[i]) * i,
                color="red",
            )

    def generate_fem_node_lims(self) -> np.ndarray:
        """Regenerate start-stop FEM node indices for each fiber."""
        current_node = 0
        fem_node_lims = np.zeros((self.n_fibers, 2))
        for i in tqdm(range(self.n_fibers), desc="Generating FEM node limits"):
            new_identities = np.nonzero(self.fem_node_fiber_ids == i)
            n_fem_nodes_current_fiber = new_identities[0].size
            fem_node_lims[i, :] = [current_node, current_node + n_fem_nodes_current_fiber]
            current_node += n_fem_nodes_current_fiber
        self.fem_node_lims = fem_node_lims
        return fem_node_lims

    @property
    def n_fibers(self) -> int:
        return self.locs.shape[0]

    @property
    def locs(self) -> np.ndarray:
        return self._locs

    @property
    def n_groups(self) -> int:
        return self._n_groups

    @property
    def cluster_ids(self) -> np.ndarray:
        return self._cluster_ids

    @property
    def n_internodes(self) -> int:
        return self._n_internodes

    @property
    def cluster_locs(self):
        return self._cluster_locs

    @property
    def cluster_std(self):
        return self._cluster_std

    @property
    def cluster_num(self):
        return self._cluster_num

    @property
    def nerve_topography(self):
        return self._nerve_topography

    @property
    def fiber_ids(self):
        return self._fiber_ids

    @property
    def node_locs(self):
        return self._node_locs

    @property
    def diameters(self):
        return self._diameters

    @property
    def n_fascicles(self):
        return self._n_fascicles

    @property
    def central_node_z(self):
        return self._central_node_z

    @property
    def n_nodes(self) -> int:
        return self.n_internodes * MRG_COMPARTMENTS_PER_INTERNODE + 1

    @property
    def node_ids(self):
        return self._node_ids

    @property
    def fem_node_locs(self):
        return self._fem_node_locs

    @property
    def fem_node_fiber_ids(self):
        return self._fem_node_fiber_ids

    @property
    def n_fem_nodes(self) -> int:
        return self.fem_node_locs.shape[0]


def compute_locs_inside_fascicles(
    candidate_fiber_locs: np.ndarray,
    circular_fascicles: np.ndarray,
) -> np.ndarray:
    """Return candidate fiber locations falling inside at least one fascicle.

    Parameters
    ----------
    candidate_fiber_locs : ndarray, shape (n_candidates, 2)
        Candidate transverse fiber locations.
    circular_fascicles : ndarray, shape (n_fascicles, 3)
        Circular fascicle definitions. Columns are x center, y center, radius.
    """
    candidate_fiber_locs = np.asarray(candidate_fiber_locs)
    circular_fascicles = np.asarray(circular_fascicles)

    distances = np.sqrt(
        (candidate_fiber_locs[:, None, 0] - circular_fascicles[None, :, 0]) ** 2
        + (candidate_fiber_locs[:, None, 1] - circular_fascicles[None, :, 1]) ** 2
    )
    is_inside = distances <= circular_fascicles[None, :, 2]
    admissible_fiber_idx = np.any(is_inside, axis=1)
    return candidate_fiber_locs[admissible_fiber_idx]


def generate_random_cluster_features(
    n_clusters: int,
    nerve_radius: float,
    std_lims: tuple[float, float],
    num_lims: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample random Gaussian cluster features within a circular nerve section."""
    cluster_rho = np.sqrt(np.random.rand(n_clusters)) * nerve_radius
    cluster_theta = np.random.rand(n_clusters) * 2 * np.pi
    cluster_locs = np.column_stack(
        (cluster_rho * np.cos(cluster_theta), cluster_rho * np.sin(cluster_theta))
    )
    cluster_std = np.random.rand(n_clusters) * (std_lims[1] - std_lims[0]) + std_lims[0]
    cluster_num = np.random.randint(low=num_lims[0], high=num_lims[1] + 1, size=n_clusters)
    return cluster_locs, cluster_std, cluster_num


def _validate_cluster_features(
    cluster_locs: np.ndarray,
    cluster_std: np.ndarray,
    cluster_num: np.ndarray,
) -> None:
    """Validate compatible cluster feature dimensions."""
    if (
        cluster_locs.shape[0] != cluster_std.shape[0]
        or cluster_std.shape[0] != cluster_num.shape[0]
    ):
        raise ValueError(
            "Dimension mismatch between cluster_locs, cluster_std, and cluster_num: "
            f"cluster_locs has first dimension {cluster_locs.shape[0]}, "
            f"cluster_std has first dimension {cluster_std.shape[0]}, "
            f"and cluster_num has first dimension {cluster_num.shape[0]}."
        )


def _sample_uniform_diameters(
    n_fibers: int,
    diameter_lims: tuple[float, float] = DEFAULT_DIAMETER_LIMS,
) -> np.ndarray:
    """Sample fiber diameters uniformly within the provided limits."""
    return np.random.rand(n_fibers) * (diameter_lims[1] - diameter_lims[0]) + diameter_lims[0]


def _gaussian_sampling_probabilities(
    points: np.ndarray,
    mean: np.ndarray,
    std: float,
) -> np.ndarray:
    """Compute normalized Gaussian sampling probabilities over candidate points."""
    location_score = multivariate_normal.pdf(x=points, mean=mean, cov=std**2)
    normalization = np.sum(location_score)
    if normalization == 0:
        normalization = 1e-10
    return location_score / normalization
