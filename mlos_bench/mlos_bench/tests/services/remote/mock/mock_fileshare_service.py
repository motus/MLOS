#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
A collection Service functions for mocking file share ops.
"""

import logging

from mlos_bench.services.base_fileshare import FileShareService
from mlos_bench.services.types.fileshare_type import SupportsFileShareOps

_LOG = logging.getLogger(__name__)


class MockFileShareService(FileShareService, SupportsFileShareOps):
    """
    A collection Service functions for mocking file share ops.
    """

    def download(self, params: dict, remote_path: str, local_path: str, recursive: bool = True) -> None:
        pass

    def upload(self, params: dict, local_path: str, remote_path: str, recursive: bool = True) -> None:
        pass
