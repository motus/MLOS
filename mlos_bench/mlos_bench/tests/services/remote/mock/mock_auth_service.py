#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
A collection Service functions for mocking authentication.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from mlos_bench.services.base_service import Service
from mlos_bench.services.types.authenticator_type import SupportsAuth

_LOG = logging.getLogger(__name__)


class MockAuthService(Service, SupportsAuth):
    """
    A collection Service functions for mocking authentication ops.
    """

    def _local_service_methods(self, local_methods: Optional[List[Callable]] = None) -> Dict[str, Callable]:
        return super()._local_service_methods([
            self.get_access_token,
        ])

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 global_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[Service] = None):
        super().__init__(config, global_config, parent)

    def get_access_token(self) -> str:
        return "TOKEN"
