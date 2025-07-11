# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Module for dcbnl."""

import re

from typing import Dict, TYPE_CHECKING, Any
from mfd_const.qos import LOCAL_ETS, LOCAL_PFC, LOCAL_APP, DCB_TOOL_PATH_LNX
from .exceptions import DcbExecutionError, DcbExecutionProcessError

if TYPE_CHECKING:
    from mfd_connect import RPyCConnection


class Dcbnl:
    """Dcbnl class provides DCB configuration using dcbnl python script."""

    def __init__(self, interface_name: str, connection: "RPyCConnection"):
        """Initialize class parameters.

        :param interface_name: tested interface
        :param connection: connection
        """
        self.interface_name = interface_name
        self._connection = connection

    def get_dcb(self) -> Dict[str, Dict[str, Any]]:
        """Get complete DCB configuration for ETS, PFC and APP TLVs, local and remote.

        :return: Dictionary of QoS configuration
        """
        qos = {}
        qos.update(self.get_ets())
        qos.update(self.get_pfc(from_cache=True))
        qos.update(self.get_app(from_cache=True))
        return qos

    def get_ets(self, from_cache: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get local ETS TLV configuration of the interface_name.

        :param from_cache: use current configuration output
        :return: Dictionary of local ETS TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration()
        return self._parse_ets(LOCAL_ETS)

    def get_pfc(self, from_cache: bool = False) -> Dict[str, bool]:
        """Get local PFC TLV configuration of the interface_name.

        :param from_cache: use current configuration output
        :return: Dictionary of local PFC TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration()
        return self._parse_pfc(LOCAL_PFC)

    def get_app(self, from_cache: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get local APP TLV configuration of the interface_name.

        :param from_cache: use current configuration output
        :return: Dictionary of local APP TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration()
        return self._parse_app(LOCAL_APP)

    def _read_qos_configuration(self) -> None:
        """Run dcbnl.py script for given interface_name and store it in self._qos_output for future use.

        dcbnl.py - Netlink message generation/parsing - DCB_TOOL_PATH_LNX = /tmp/tools/dcb
        :raises DcbExecutionError: when return code of bash command is unexpected
        """
        dcbnl_path = self._connection.path(DCB_TOOL_PATH_LNX, "dcbnl.py")
        command = f"{self._connection.modules().sys.executable} {dcbnl_path} {self.interface_name}"
        output = self._connection.execute_command(
            command, custom_exception=DcbExecutionProcessError, expected_return_codes=[0]
        )
        if output.stderr:
            raise DcbExecutionError(f"Error while executing dcbnl {command}: {output.stderr}")
        self._qos_output = output.stdout

    def _parse_ets(self, key: str) -> Dict[str, Dict[str, int]]:
        """Get local or remote QoS traffic classes as dictionary.

        :param key: key in configuration dictionary for ETS
        :return: Dictionary of QoS traffic classes configuration
        """
        ets_config = {}
        current_tc = ""
        for line in self._qos_output.splitlines():
            line = line.strip()
            exp = re.compile(r"tc: (?P<tc>[0-7]) tsa: (?P<tsa>ets|strict)(?:, bw: (?P<bw>\d+)%)")
            match = exp.match(line)
            if match:
                current_tc = match.group("tc")
                ets_config[current_tc] = {
                    "TSA": match.group("tsa").upper(),
                    "Bandwidth": int(match.group("bw") or "0"),
                    "Priorities": [],
                }
                continue
            match = re.match(r"up:\s+(?P<up>[0-7])", line)
            if match:
                up = int(match.group("up"))
                ets_config[current_tc]["Priorities"].append(up)
                continue
        return {key: ets_config}

    def _parse_pfc(self, key: str) -> Dict[str, bool]:
        """Get operational or remote QoS flow control as dictionary.

        :param key: key in configuration dictionary for PFC
        :return: Dictionary of QoS flow control configuration
        """
        pfc_config = [False] * 8
        match = re.search(r"pfc_enable:\s+(?P<pfc>0x[0-9a-fA-F]+)", self._qos_output)
        if match:
            pfc_bin = int(match.group("pfc"), 16)
            for i in range(8):
                pfc_config[i] = pfc_bin & (pow(2, i)) > 0
        return {key: pfc_config}

    def _parse_app(self, key: str) -> Dict[str, Dict[str, str]]:
        """Get operational or remote QoS apps table.

        :param key: key in configuration dictionary for PFC
        :return: Dictionary of QoS flow control configuration
        """
        app_config = {}
        no = 0
        for line in self._qos_output.splitlines():
            line = line.strip()
            exp = re.compile(r"selector: (?P<selector>\d+) priority: (?P<priority>\d+) protocol: (?P<protocol>\S*)")
            match = exp.match(line)
            if match:
                app_config[no] = {
                    "selector": int(match.group("selector")),
                    "priority": int(match.group("priority")),
                    "protocol": match.group("protocol"),
                }
                no += 1
        return {key: app_config}
