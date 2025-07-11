# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Exceptions for module."""

from subprocess import CalledProcessError


class DcbConnectedOSNotSupported(Exception):
    """Handle Dcb unsupported os exceptions."""


class DcbException(Exception):
    """Handle Dcb exceptions."""


class DcbExecutionError(Exception):
    """Handle Dcb execution errors."""


class DcbExecutionProcessError(CalledProcessError):
    """Handle Dcb process execution errors."""
