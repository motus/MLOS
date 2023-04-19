#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
Base class for an interface between the benchmarking framework
and mlos_core optimizers.
"""

import logging
from typing import Dict, Optional, Sequence, Tuple, Union
from abc import ABCMeta, abstractmethod

from mlos_bench.service import Service
from mlos_bench.environment.status import Status
from mlos_bench.tunables.tunable_groups import TunableGroups

_LOG = logging.getLogger(__name__)


class Optimizer(metaclass=ABCMeta):
    """
    An abstract interface between the benchmarking framework and mlos_core optimizers.
    """

    def __init__(self, tunables: TunableGroups, service: Optional[Service], config: dict):
        """
        Create a new optimizer for the given configuration space defined by the tunables.

        Parameters
        ----------
        tunables : TunableGroups
            The tunables to optimize.
        config : dict
            Free-format key/value pairs of configuration parameters to pass to the optimizer.
        """
        _LOG.info("Create optimizer for: %s", tunables)
        _LOG.debug("Optimizer config: %s", config)
        self._config = config.copy()
        self._tunables = tunables
        self._service = service
        self._iter = 1
        self._max_iter = int(self._config.pop('max_iterations', 10))
        self._opt_target: str
        _opt_target = self._config.pop('maximize', None)
        if _opt_target is None:
            self._opt_target = self._config.pop('minimize', 'score')
            self._opt_sign = 1
        else:
            self._opt_target = _opt_target
            if 'minimize' in self._config:
                raise ValueError("Cannot specify both 'maximize' and 'minimize'.")
            self._opt_sign = -1

    def __repr__(self) -> str:
        opt_direction = 'min' if self._opt_sign > 0 else 'max'
        return f"{self.__class__.__name__}:{opt_direction}({self._opt_target})"

    @property
    def target(self) -> str:
        """
        The name of the target metric to optimize.
        """
        return self._opt_target

    @abstractmethod
    def bulk_register(self, configs: Sequence[dict], scores: Sequence[Optional[float]],
                      status: Optional[Sequence[Status]] = None) -> bool:
        """
        Pre-load the optimizer with the bulk data from previous experiments.

        Parameters
        ----------
        configs : Sequence[dict]
            Records of tunable values from other experiments.
        scores : Sequence[float]
            Benchmark results from experiments that correspond to `configs`.
        status : Optional[Sequence[float]]
            Status of the experiments that correspond to `configs`.

        Returns
        -------
        is_not_empty : bool
            True if there is data to register, false otherwise.
        """
        _LOG.info("Warm-up the optimizer with: %d configs, %d scores, %d status values",
                  len(configs or []), len(scores or []), len(status or []))
        if len(configs or []) != len(scores or []):
            raise ValueError("Numbers of configs and scores do not match.")
        if status is not None and len(configs or []) != len(status or []):
            raise ValueError("Numbers of configs and status values do not match.")
        return bool(configs and scores)

    @abstractmethod
    def suggest(self) -> TunableGroups:
        """
        Generate the next suggestion.

        Returns
        -------
        tunables : TunableGroups
            The next configuration to benchmark.
            These are the same tunables we pass to the constructor,
            but with the values set to the next suggestion.
        """

    @abstractmethod
    def register(self, tunables: TunableGroups, status: Status,
                 score: Optional[Union[float, Dict[str, float]]] = None) -> Optional[float]:
        """
        Register the observation for the given configuration.

        Parameters
        ----------
        tunables : TunableGroups
            The configuration that has been benchmarked.
            Usually it's the same config that the `.suggest()` method returned.
        status : Status
            Final status of the experiment (e.g., SUCCEEDED or FAILED).
        score : Union[float, Dict[str, float]]
            A scalar or a dict with the final benchmark results.
            None if the experiment was not successful.

        Returns
        -------
        value : float
            The scalar benchmark score extracted (and possibly transformed) from the dataframe that's being minimized.
        """
        _LOG.info("Iteration %d :: Register: %s = %s score: %s",
                  self._iter, tunables, status, score)
        if status.is_succeeded == (score is None):  # XOR
            raise ValueError("Status and score must be consistent.")
        return self._get_score(status, score)

    def _get_score(self, status: Status, score: Optional[Union[float, Dict[str, float]]]) -> Optional[float]:
        """
        Extract a scalar benchmark score from the dataframe.
        Change the sign if we are maximizing.

        Parameters
        ----------
        status : Status
            Final status of the experiment (e.g., SUCCEEDED or FAILED).
        score : Union[float, Dict[str, float]]
            A scalar or a dict with the final benchmark results.
            None if the experiment was not successful.

        Returns
        -------
        score : float
            A scalar benchmark score to be used as a primary target for MINIMIZATION.
        """
        if not status.is_succeeded:
            return None
        assert score is not None
        if isinstance(score, dict):
            score = score[self._opt_target]
        return float(score) * self._opt_sign

    def not_converged(self) -> bool:
        """
        Return True if not converged, False otherwise.
        Base implementation just checks the iteration count.
        """
        return self._iter <= self._max_iter

    @abstractmethod
    def get_best_observation(self) -> Union[Tuple[float, TunableGroups], Tuple[None, None]]:
        """
        Get the best observation so far.

        Returns
        -------
        (value, tunables) : Tuple[float, TunableGroups]
            The best value and the corresponding configuration.
            (None, None) if no successful observation has been registered yet.
        """
