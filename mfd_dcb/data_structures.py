# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for DCB common data structures."""

from enum import Enum


class State(Enum):
    """States."""

    ENABLED = "enabled"
    DISABLED = "disabled"
