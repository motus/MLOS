#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""Setup instructions for the mlos_viz package."""

# pylint: disable=duplicate-code

import os
import re
from itertools import chain
from logging import warning
from typing import Dict, List

from setuptools import setup

PKG_NAME = "mlos_viz"

try:
    ns: Dict[str, str] = {}
    with open(f"{PKG_NAME}/version.py", encoding="utf-8") as version_file:
        exec(version_file.read(), ns)  # pylint: disable=exec-used
    VERSION = ns["VERSION"]
except OSError:
    VERSION = "0.0.1-dev"
    warning(f"version.py not found, using dummy VERSION={VERSION}")

try:
    from setuptools_scm import get_version

    version = get_version(root="..", relative_to=__file__, fallback_version=VERSION)
    if version is not None:
        VERSION = version
except ImportError:
    warning("setuptools_scm not found, using version from version.py")
except LookupError as e:
    warning(f"setuptools_scm failed to find git version, using version from version.py: {e}")


# A simple routine to read and adjust the README.md for this module into a format
# suitable for packaging.
# See Also: copy-source-tree-docs.sh
# Unfortunately we can't use that directly due to the way packaging happens inside a
# temp directory.
# Similarly, we can't use a utility script outside this module, so this code has to
# be duplicated for now.
def _get_long_desc_from_readme(base_url: str) -> dict:
    pkg_dir = os.path.dirname(__file__)
    readme_path = os.path.join(pkg_dir, "README.md")
    if not os.path.isfile(readme_path):
        return {
            "long_description": "missing",
        }
    jsonc_re = re.compile(r"```jsonc")
    link_re = re.compile(r"\]\(([^:#)]+)(#[a-zA-Z0-9_-]+)?\)")
    with open(readme_path, mode="r", encoding="utf-8") as readme_fh:
        lines = readme_fh.readlines()
        # Tweak the lexers for local expansion by pygments instead of github's.
        lines = [link_re.sub(f"]({base_url}" + r"/\1\2)", line) for line in lines]
        # Tweak source source code links.
        lines = [jsonc_re.sub(r"```json", line) for line in lines]
        return {
            "long_description": "".join(lines),
            "long_description_content_type": "text/markdown",
        }


extra_requires: Dict[str, List[str]] = {}

# construct special 'full' extra that adds requirements for all built-in
# backend integrations and additional extra features.
extra_requires["full"] = list(set(chain(*extra_requires.values())))

extra_requires["full-tests"] = extra_requires["full"] + [
    "pytest",
    "pytest-forked",
    "pytest-xdist",
    "pytest-cov",
    "pytest-local-badge",
]

setup(
    version=VERSION,
    install_requires=[
        "mlos-bench==" + VERSION,
        "dabl>=0.2.6",
        "matplotlib<3.9",  # FIXME: https://github.com/dabl/dabl/pull/341
        "seaborn>=0.12.2",
    ],
    extras_require=extra_requires,
    **_get_long_desc_from_readme("https://github.com/microsoft/MLOS/tree/main/mlos_viz"),
)
