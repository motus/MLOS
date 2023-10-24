#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
A collection Service functions for mocking local exec.
"""

import logging
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Tuple, TYPE_CHECKING

from mlos_bench.services.local.temp_dir_context import TempDirContextService
from mlos_bench.services.types.local_exec_type import SupportsLocalExec

if TYPE_CHECKING:
    from mlos_bench.tunables.tunable import TunableValue

_LOG = logging.getLogger(__name__)


class MockLocalExecService(TempDirContextService, SupportsLocalExec):
    """
    Mock methods for LocalExecService testing.
    """

    def _local_service_methods(self, local_methods: Optional[List[Callable]] = None) -> Dict[str, Callable]:
        return super()._local_service_methods([
            self.local_exec,
        ])

    def local_exec(self, script_lines: Iterable[str],
                   env: Optional[Mapping[str, "TunableValue"]] = None,
                   cwd: Optional[str] = None) -> Tuple[int, str, str]:
        return (0, "", "")
