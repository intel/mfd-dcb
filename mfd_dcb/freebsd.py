# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Module for DCB support for FreeBSD OS."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple

from mfd_common_libs import add_logging_level, log_levels, os_supported
from mfd_typing import OSName
from mfd_sysctl.freebsd import FreebsdSysctl
from mfd_connect.exceptions import ConnectionCalledProcessError
from .mfd_dcb import Dcb
from .enums import PfcMode
from .exceptions import DcbException


if TYPE_CHECKING:
    from mfd_connect import RPyCConnection

logger = logging.getLogger(__name__)
add_logging_level("MODULE_DEBUG", log_levels.MODULE_DEBUG)


class FreeBsdDcb(Dcb):
    """Class to handle DCB in FreeBSD."""

    @os_supported(OSName.FREEBSD)
    def __init__(self, *, connection: "RPyCConnection") -> None:
        """Initialize FreeBSD DCB."""
        super().__init__(connection=connection)
        self._sysctl = FreebsdSysctl(connection=connection)

    def dscp_apply_map(self, interface_name: str, dscpmap: List[int]) -> None:
        """Configure DSCP2TC map on the interface.

        :param interface_name: name of the network interface
        :param dscpmap: DSCP2TC map for setting on the interface
        :raises DcbException: when DSCP map failed to apply (wrong number of elements or invalid values).
        :raises ConnectionCalledProcessError: when sysctl failed and returned an unexpected error code.
        """

        def _apply_range(device_oid: str, values: list, start: int) -> None:
            command = f"sysctl {device_oid}.dscp2tc_map.{start}-{start + 7}={','.join(map(str, values))}"
            try:
                self._connection.execute_command(command, expected_return_codes=[0])
            except ConnectionCalledProcessError as e:
                if "returned unexpected exit status 1" in str(e):
                    raise DcbException(f"Failed to apply DSCP map for range {start}-{start + 7}")
                else:
                    raise e

        device_oid = (
            f"dev.{self._sysctl.get_driver_name(interface_name)}."
            f"{self._sysctl.get_driver_interface_number(interface_name)}"
        )
        logger.log(
            level=log_levels.MODULE_DEBUG,
            msg=f"Applying DSCP map: {dscpmap} on interface {interface_name}",
        )
        # apply DSCP map in parts (8 elements for each sysctl variable)
        for r in range(0, 64, 8):
            _apply_range(device_oid, dscpmap[r : r + 8], r)

    def dscp_read_map(self, interface_name: str) -> List[int]:
        """Read DSCP2TC map from the interface.

        :param interface_name: name of the network interface
        :return: DSCP map that is configured on the interface
        """

        def _read_range(device_oid: str, start: int) -> Tuple[int]:
            full_oid = f"{device_oid}.dscp2tc_map.{start}-{start + 7}"
            result = self._sysctl.get_sysctl_value(full_oid)
            return tuple(map(int, str(result).split(",")))

        device_oid = (
            f"dev.{self._sysctl.get_driver_name(interface_name)}."
            f"{self._sysctl.get_driver_interface_number(interface_name)}"
        )
        m = []
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Reading DSCP map on interface {interface_name}")
        # read DSCP map in chunks (8 elements each) and add them to a list
        for r in range(0, 64, 8):
            m.extend(_read_range(device_oid, r))
        return m

    def dscp_verify_map(self, interface_name: str, dscpmap: List[int]) -> bool:
        """Check that the interface has the same DSCP2TC map.

        :param interface_name: Network interface
        :param dscpmap: DSCP2TC map to compare
        :return: True if the interface has the same dscp2tc map
        """
        current_dscpmap = self.dscp_read_map(interface_name)
        return current_dscpmap == dscpmap

    def set_pfc_mode(self, interface_name: str, mode: PfcMode) -> None:
        """Enable/disable DSCP mode on the interface.

        :param interface_name: Network interface
        :param mode: Enable (PfcMode.DSCP) or disable (PfcMode.VLAN) DSCP mode on the interface
        """
        oid = (
            f"dev.{self._sysctl.get_driver_name(interface_name)}."
            f"{self._sysctl.get_driver_interface_number(interface_name)}.pfc_mode"
        )
        self._sysctl.set_sysctl_value(oid, value=str(mode.value))

    def get_pfc_mode(self, interface_name: str) -> PfcMode:
        """Get the current PFC mode on the interface.

        :param interface_name: Name of the network interface
        :return: Current PFC mode (VLAN/DSCP) on the interface
        """
        oid = (
            f"dev.{self._sysctl.get_driver_name(interface_name)}."
            f"{self._sysctl.get_driver_interface_number(interface_name)}.pfc_mode"
        )
        return PfcMode(int(self._sysctl.get_sysctl_value(oid)))

    def set_ets_min_rate(self, interface_name: str, ets: List[int]) -> None:
        """Configure ETS on an interface.

        :param interface_name: Network interface
        :param ets: ETS bandwidth table (list of 8 elements of ints)
        """
        oid = (
            f"dev.{self._sysctl.get_driver_name(interface_name)}."
            f"{self._sysctl.get_driver_interface_number(interface_name)}.ets_min_rate"
        )
        self._sysctl.set_sysctl_value(oid, value=str(",".join(map(str, ets))))

    def get_ets_min_rate(self, interface_name: str) -> List[int]:
        """Read current ETS bandwidth table.

        :param interface_name: Name of the network interface
        :return: Current ETS bandwidth table configured on the interface
        """
        oid = (
            f"dev.{self._sysctl.get_driver_name(interface_name)}."
            f"{self._sysctl.get_driver_interface_number(interface_name)}.ets_min_rate"
        )
        return list(map(int, str(self._sysctl.get_sysctl_value(oid)).split(",")))
