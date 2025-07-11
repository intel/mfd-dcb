# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Main module."""

import logging

from typing import TYPE_CHECKING
from mfd_typing import OSName
from mfd_common_libs import add_logging_level, log_levels
from .exceptions import DcbConnectedOSNotSupported

if TYPE_CHECKING:
    from mfd_connect import RPyCConnection

logger = logging.getLogger(__name__)
add_logging_level("MODULE_DEBUG", log_levels.MODULE_DEBUG)


class Dcb:
    """Class for Dcb methods."""

    def __new__(cls, connection: "RPyCConnection"):
        """
        Choose Dcb subclass based on provided connection object.

        :param connection: connection
        :return: instance of subclass
        """
        from .windows import WindowsDcb
        from .linux import LinuxDcb
        from .freebsd import FreeBsdDcb

        os_name = connection.get_os_name()
        os_name_to_class = {
            OSName.WINDOWS: WindowsDcb,
            OSName.LINUX: LinuxDcb,
            OSName.FREEBSD: FreeBsdDcb,
        }

        if os_name not in os_name_to_class.keys():
            raise DcbConnectedOSNotSupported(f"Not supported OS for Dcb: {os_name}")

        owner_class = os_name_to_class.get(os_name)
        return super().__new__(owner_class)

    def __init__(self, *, connection: "RPyCConnection") -> None:
        """Initialize DCB."""
        self._connection = connection
