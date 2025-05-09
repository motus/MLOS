#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""Functions to convert :py:class:`.TunableGroups` that :py:mod:`mlos_bench` uses to to
:py:class:`ConfigSpace.ConfigurationSpace` for use with the
:py:mod:`mlos_core.optimizers`.
"""

import enum
import logging
from collections.abc import Hashable

from ConfigSpace import (
    Beta,
    CategoricalHyperparameter,
    Configuration,
    ConfigurationSpace,
    EqualsCondition,
    Float,
    Integer,
    Normal,
    Uniform,
)
from ConfigSpace.hyperparameters import NumericalHyperparameter
from ConfigSpace.types import NotSet

from mlos_bench.tunables.tunable import Tunable
from mlos_bench.tunables.tunable_groups import TunableGroups
from mlos_bench.tunables.tunable_types import TunableValue
from mlos_bench.util import try_parse_val
from mlos_core.spaces.converters.util import (
    QUANTIZATION_BINS_META_KEY,
    monkey_patch_hp_quantization,
)

_LOG = logging.getLogger(__name__)


class TunableValueKind(enum.Enum):
    """Enum for the kind of the tunable value (special or not)."""

    SPECIAL = "special"
    RANGE = "range"


def _normalize_weights(weights: list[float]) -> list[float]:
    """Helper function for normalizing weights to probabilities."""
    total = sum(weights)
    return [w / total for w in weights]


def _tunable_to_configspace(
    tunable: Tunable,
    group_name: str | None = None,
    cost: int = 0,
) -> ConfigurationSpace:
    """
    Convert a single Tunable to an equivalent set of ConfigSpace Hyperparameter objects,
    wrapped in a ConfigurationSpace for composability.
    Note: this may be more than one Hyperparameter in the case of special value handling.

    Parameters
    ----------
    tunable : Tunable
        An mlos_bench Tunable object.
    group_name : str
        Human-readable id of the CovariantTunableGroup this Tunable belongs to.
    cost : int
        Cost to change this parameter (comes from the corresponding CovariantTunableGroup).

    Returns
    -------
    cs : ConfigSpace.ConfigurationSpace
        A ConfigurationSpace object that corresponds to the Tunable.
    """
    # pylint: disable=too-complex
    meta: dict[Hashable, TunableValue] = {"cost": cost}
    if group_name is not None:
        meta["group"] = group_name
    if tunable.is_numerical and tunable.quantization_bins:
        # Temporary workaround to dropped quantization support in ConfigSpace 1.0
        # See Also: https://github.com/automl/ConfigSpace/issues/390
        meta[QUANTIZATION_BINS_META_KEY] = tunable.quantization_bins

    if tunable.type == "categorical":
        return ConfigurationSpace(
            {
                tunable.name: CategoricalHyperparameter(
                    name=tunable.name,
                    choices=tunable.categories,
                    weights=_normalize_weights(tunable.weights) if tunable.weights else None,
                    default_value=tunable.default,
                    meta=meta,
                )
            }
        )

    distribution: Uniform | Normal | Beta | None = None
    if tunable.distribution == "uniform":
        distribution = Uniform()
    elif tunable.distribution == "normal":
        distribution = Normal(
            mu=tunable.distribution_params["mu"],
            sigma=tunable.distribution_params["sigma"],
        )
    elif tunable.distribution == "beta":
        distribution = Beta(
            alpha=tunable.distribution_params["alpha"],
            beta=tunable.distribution_params["beta"],
        )
    elif tunable.distribution is not None:
        raise TypeError(f"Invalid Distribution Type: {tunable.distribution}")

    range_hp: NumericalHyperparameter
    if tunable.type == "int":
        range_hp = Integer(
            name=tunable.name,
            bounds=(int(tunable.range[0]), int(tunable.range[1])),
            log=bool(tunable.is_log),
            distribution=distribution,
            default=(
                int(tunable.default)
                if tunable.in_range(tunable.default) and tunable.default is not None
                else None
            ),
            meta=meta,
        )
    elif tunable.type == "float":
        range_hp = Float(
            name=tunable.name,
            bounds=tunable.range,
            log=bool(tunable.is_log),
            distribution=distribution,
            default=(
                float(tunable.default)
                if tunable.in_range(tunable.default) and tunable.default is not None
                else None
            ),
            meta=meta,
        )
    else:
        raise TypeError(f"Invalid Parameter Type: {tunable.type}")

    monkey_patch_hp_quantization(range_hp)
    if not tunable.special:
        return ConfigurationSpace(space=[range_hp])

    # Compute the probabilities of switching between regular and special values.
    special_weights: list[float] | None = None
    switch_weights = [0.5, 0.5]  # FLAML requires uniform weights.
    if tunable.weights and tunable.range_weight is not None:
        special_weights = _normalize_weights(tunable.weights)
        switch_weights = _normalize_weights([sum(tunable.weights), tunable.range_weight])

    # Create three hyperparameters: one for regular values,
    # one for special values, and one to choose between the two.
    (special_name, type_name) = special_param_names(tunable.name)
    conf_space = ConfigurationSpace(
        space=[
            range_hp,
            CategoricalHyperparameter(
                name=special_name,
                choices=tunable.special,
                weights=special_weights,
                default_value=tunable.default if tunable.default in tunable.special else NotSet,
                meta=meta,
            ),
            CategoricalHyperparameter(
                name=type_name,
                choices=[TunableValueKind.SPECIAL.value, TunableValueKind.RANGE.value],
                weights=switch_weights,
                default_value=TunableValueKind.SPECIAL.value,
            ),
        ]
    )
    conf_space.add(
        [
            EqualsCondition(
                conf_space[special_name], conf_space[type_name], TunableValueKind.SPECIAL.value
            ),
            EqualsCondition(
                conf_space[tunable.name], conf_space[type_name], TunableValueKind.RANGE.value
            ),
        ]
    )
    return conf_space


def tunable_groups_to_configspace(
    tunables: TunableGroups,
    seed: int | None = None,
) -> ConfigurationSpace:
    """
    Convert TunableGroups to  hyperparameters in ConfigurationSpace.

    Parameters
    ----------
    tunables : TunableGroups
        A collection of tunable parameters.

    seed : int | None
        Random seed to use.

    Returns
    -------
    configspace : ConfigSpace.ConfigurationSpace
        A new ConfigurationSpace instance that corresponds to the input TunableGroups.
    """
    space = ConfigurationSpace(seed=seed)
    for tunable, group in tunables:
        space.add_configuration_space(
            prefix="",
            delimiter="",
            configuration_space=_tunable_to_configspace(
                tunable,
                group.name,
                group.get_current_cost(),
            ),
        )
    return space


def tunable_values_to_configuration(tunables: TunableGroups) -> Configuration:
    """
    Converts a TunableGroups current values to a ConfigSpace Configuration.

    Parameters
    ----------
    tunables : TunableGroups
        The TunableGroups to take the current value from.

    Returns
    -------
    ConfigSpace.Configuration
        A ConfigSpace Configuration.
    """
    values: dict[str, TunableValue] = {}
    for tunable, _group in tunables:
        if tunable.special:
            (special_name, type_name) = special_param_names(tunable.name)
            if tunable.value in tunable.special:
                values[type_name] = TunableValueKind.SPECIAL.value
                values[special_name] = tunable.value
            else:
                values[type_name] = TunableValueKind.RANGE.value
                values[tunable.name] = tunable.value
        else:
            values[tunable.name] = tunable.value
    configspace = tunable_groups_to_configspace(tunables)
    return Configuration(configspace, values=values)


def configspace_data_to_tunable_values(data: dict) -> dict[str, TunableValue]:
    """
    Remove the fields that correspond to special values in ConfigSpace.

    In particular, remove and keys suffixes added by `special_param_names`.
    """
    data = data.copy()
    specials = [special_param_name_strip(k) for k in data.keys() if special_param_name_is_temp(k)]
    for k in specials:
        (special_name, type_name) = special_param_names(k)
        if data[type_name] == TunableValueKind.SPECIAL.value:
            data[k] = data[special_name]
        if special_name in data:
            del data[special_name]
        del data[type_name]
    # May need to convert numpy values to regular types.
    data = {k: try_parse_val(v) for k, v in data.items()}
    return data


def special_param_names(name: str) -> tuple[str, str]:
    """
    Generate the names of the auxiliary hyperparameters that correspond to a tunable
    that can have special values.

    NOTE: ``!`` characters are currently disallowed in :py:class:`.Tunable` names in
    order handle this logic.

    Parameters
    ----------
    name : str
        The name of the tunable parameter.

    Returns
    -------
    special_name : str
        The name of the hyperparameter that corresponds to the special value.
    type_name : str
        The name of the hyperparameter that chooses between the regular and the special values.
    """
    return (name + "!special", name + "!type")


def special_param_name_is_temp(name: str) -> bool:
    """
    Check if name corresponds to a temporary ConfigSpace parameter.

    NOTE: ``!`` characters are currently disallowed in :py:class:`.Tunable` names in
    order handle this logic.

    Parameters
    ----------
    name : str
        The name of the hyperparameter.

    Returns
    -------
    is_special : bool
        True if the name corresponds to a temporary ConfigSpace hyperparameter.
    """
    return name.endswith("!type")


def special_param_name_strip(name: str) -> str:
    """
    Remove the temporary suffix from a special parameter name.

    NOTE: ``!`` characters are currently disallowed in :py:class:`.Tunable` names in
    order handle this logic.

    Parameters
    ----------
    name : str
        The name of the hyperparameter.

    Returns
    -------
    stripped_name : str
        The name of the hyperparameter without the temporary suffix.
    """
    return name.split("!", 1)[0]
