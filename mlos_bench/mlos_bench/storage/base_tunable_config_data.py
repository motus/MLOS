#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
Base interface for accessing the stored benchmark (tunable) config data.

Note: a configuration in this context is the set of tunable parameter values and can
be used by one or more trials.

See Also
--------
:py:mod:`mlos_bench.storage` :
    The base storage module for mlos_bench, which includes some basic examples in
    the documentation.
"""
from abc import ABCMeta, abstractmethod
from typing import Any

import pandas

from mlos_bench.storage.util import kv_df_to_dict
from mlos_bench.tunables.tunable_types import TunableValue


class TunableConfigData(metaclass=ABCMeta):
    """
    Base interface for accessing the stored experiment benchmark (tunable) config data.

    A configuration in this context is the set of tunable parameter values.
    """

    def __init__(self, *, tunable_config_id: int):
        self._tunable_config_id = tunable_config_id

    def __repr__(self) -> str:
        return f"TunableConfig :: {self._tunable_config_id}: {self.config_dict}"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._tunable_config_id == other._tunable_config_id

    @property
    def tunable_config_id(self) -> int:
        """Unique ID of the (tunable) configuration."""
        return self._tunable_config_id

    @property
    @abstractmethod
    def config_df(self) -> pandas.DataFrame:
        """
        Retrieve the trials' tunable configuration from the storage.

        Note: this corresponds to the Trial object's "tunables" property.

        Returns
        -------
        config : pandas.DataFrame
            A dataframe with the tunable configuration of the trial.
            It has two `str` columns, "parameter" and "value".
        """

    @property
    def config_dict(self) -> dict[str, TunableValue | None]:
        """
        Retrieve the trials' tunable configuration from the storage as a dict.

        Note: this corresponds to the Trial object's "tunables" property.

        Returns
        -------
        config : dict
        """
        return kv_df_to_dict(self.config_df)

    # TODO: add methods for retrieving
    # - trials by tunable config, even across experiments (e.g., for merging)
    # - trial config groups (i.e., all experiments' trials with the same tunable config)
