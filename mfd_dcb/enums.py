# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Enums for DCBmodule."""

from enum import Enum, IntEnum


class WindowsDcbMode(Enum):
    """Enum class for Windows DCB Features."""

    SWITCH = "Switch Settings"
    OS = "OS Controlled"
    ENABLED = "Enabled"
    DISABLED = "Disabled"


class PfcType(Enum):
    """Enum class for PFC Type."""

    LOCAL = "local"
    REMOTE = "remote"


class PfcMode(IntEnum):
    """Enum class for PFC Mode."""

    VLAN = 0
    DSCP = 1
