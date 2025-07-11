# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Module for dcbtool."""

import re
from typing import List, Dict, Any, TYPE_CHECKING
from mfd_const.qos import LOCAL_ETS, LOCAL_PFC
from .exceptions import DcbExecutionError, DcbExecutionProcessError

if TYPE_CHECKING:
    from mfd_connect import RPyCConnection


class DcbTool:
    """DcbTool class provide check DCB configuration using dcbtool tool."""

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
        qos.update(self.get_pfc())
        return qos

    def get_ets(self, from_cache: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get local ETS TLV configuration of the interface_name.

        :param from_cache: use current configuration output
        :return: Dictionary of local ETS TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(check_type="pg")
        return self._parse_qos(LOCAL_ETS)

    def get_pfc(self, from_cache: bool = False) -> Dict[str, bool]:
        """Get local PFC TLV configuration of the interface_name.

        :param from_cache: use current configuration output
        :return: Dictionary of local PFC TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(check_type="pfc")
        return self._parse_qos(LOCAL_PFC)

    def _read_qos_configuration(self, check_type: str) -> None:
        """Run dcbtool tool for given interface_name and store it in self._qos_output for future use.

        :param check_type: for checking dcbtool type - pg/ pfc
        :raises DcbExecutionProcessError: when return code of bash command is unexpected
        """
        command = f"dcbtool go {self.interface_name} {check_type}"
        output = self._connection.execute_command(command, custom_exception=DcbExecutionProcessError)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing dcbnl {command}: {output.stderr}")
        self._qos_output = output.stdout

    def _parse_qos(self, key: str) -> Dict[str, Dict[str, Any]]:
        """Get local or remote QoS traffic classes as dictionary.

        :param key: key in configuration dictionary for ETS & PFC
        :return: Dictionary of QoS traffic classes configuration
        """
        config_ets = {}
        config_pfc = []
        for line in self._qos_output.splitlines():
            self._parse_lines(key, line, config_ets, config_pfc)
        configs = {LOCAL_PFC: config_pfc, LOCAL_ETS: config_ets}
        return {key: configs[key]}

    def _parse_lines(
        self,
        key: str,
        line: str,
        config_ets: dict,
        config_pfc: list,
    ) -> None:
        """Parse and updates in-place config_pfc and config_ets.

        :param key: key in configuration dictionary for ETS or PFC
        :param line: Each entries from dcbtool go interface <checkType(pg/pfc)>
        :param config_ets: ets config data
        :param config_pfc: pfc config data
        """
        bw_pattern = r"\s+(\d{1,3})%\s"
        tc_pattern = r"pgid:\s+(\d\s)*\d"
        pattern = r"pfcup:\s+(\d\s)*\d"
        if "ETS" in key and (("pgid" in line) or ("pgpct" in line) or ("uppct" in line)):
            line = line.strip()
            bw_list = self._parse_line(line, bw_pattern)
            if bw_list:
                self._set_bw_config(bw_list, config_ets)
            tc_list = self._parse_line(line, tc_pattern)
            if tc_list:
                self._set_up_config(tc_list, config_ets)
            if not (tc_list or bw_list):
                raise DcbExecutionError("No match found for ETS")
        elif "PFC" in key and "pfc" in line:
            pfc_list = self._parse_line(line, pattern)
            if pfc_list:
                for pfc in pfc_list:
                    config_pfc.append(bool(not (pfc)))
            else:
                raise DcbExecutionError("No match found for PFC")

    @staticmethod
    def _parse_line(line: str, pattern: str) -> List[int]:
        """To parse line and return dict with data.

        :param line: line to search
        :param pattern: regex pattern
        :return: list of data with bw_pattern/tc_pattern
        """
        data = []
        if "%" in line:
            data = list(map(int, (re.findall(pattern, line))))
        else:
            match = re.compile(pattern).match(line)
            if match:
                for idx in range(re.compile(pattern).groups):
                    data.append(int(match.group(idx + 1)))
        return data

    @staticmethod
    def _set_bw_config(bw_list: list, ets_config: dict) -> None:
        """To set bandwidth data in ets_config.

        :param bw_list: list with bandwidth data
        :param ets_config: ets config data
        """
        for up, bw in enumerate(bw_list):
            if bw > 0:
                current_tc = str(up)
                ets_config[current_tc] = {"TSA": "ETS", "Bandwidth": bw, "Priorities": []}

    @staticmethod
    def _set_up_config(tc_list: list, ets_config: dict) -> None:
        """To set user priority data in ets_config.

        :param tc_list: list with user priority
        :param ets_config: ets config data
        """
        for up, tc in enumerate(tc_list):
            ets_config[str(tc)]["Priorities"].append(up)
