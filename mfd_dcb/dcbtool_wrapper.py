# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Module for dcbtool."""

import logging
import re
from typing import Any, TYPE_CHECKING
from mfd_common_libs import log_levels
from mfd_const.qos import LOCAL_ETS, LOCAL_PFC
from .exceptions import DcbExecutionError, DcbExecutionProcessError

if TYPE_CHECKING:
    from mfd_connect import RPyCConnection

logger = logging.getLogger(__name__)


class DcbTool:
    """DcbTool class provide check and set DCB configuration using dcbtool/lldptool tools."""

    def __init__(self, interface_name: str, connection: "RPyCConnection"):
        """Initialize class parameters.

        :param interface_name: tested interface
        :param connection: connection
        """
        self.interface_name = interface_name
        self._connection = connection

    @staticmethod
    def _execute_qos_command_and_check_output(connection: "RPyCConnection", cmd_list: list[str] | str) -> str:
        """Execute QoS command(s) and check output for known problems, trying to recover from them.

        :param connection: connection used to execute the commands
        :param cmd_list: list of commands (or a single command) to execute
        :returns: stdout of the last executed command
        :raises DcbExecutionError: for non zero return code other than known errors
        """
        lldpad_fail_recovery_cmd_list = [
            "systemctl stop lldpad",
            "systemctl stop lldpad.socket",
            "systemctl reset-failed lldpad.service",
            "systemctl start lldpad.socket",
            "systemctl start lldpad",
        ]
        problems_list = [
            "lldpad.socket failed",
            "Connection refused",
            "command timed out",
            "Device not capable",
        ]
        rerun_cmd_after_problem_list = ["Connection refused", "command timed out"]
        cmd_list = cmd_list if isinstance(cmd_list, list) else [cmd_list]
        for cmd in cmd_list:
            cli_out = connection.execute_command(cmd, expected_return_codes={})
            out = cli_out.stdout
            if any(problem in out for problem in problems_list):
                if "lldpad.socket failed" in out:
                    raise DcbExecutionError("lldpad.socket failed Exception")
                elif "Connection refused" in out:
                    logger.log(
                        level=log_levels.MODULE_DEBUG,
                        msg="Connection refused, stop and start lldp.",
                    )
                    print("Connection refused, stop and start lldp.")
                elif "Device not capable" in out:
                    raise DcbExecutionError("Please check/update driver")
                for recovery_cmd in lldpad_fail_recovery_cmd_list:
                    connection.execute_command(
                        recovery_cmd,
                        custom_exception=DcbExecutionError,
                        expected_return_codes={0, 1},
                    )
                for problem in rerun_cmd_after_problem_list:
                    if problem in out:
                        logger.log(
                            level=log_levels.MODULE_DEBUG,
                            msg=f"Rerun command {cmd} after recovery action, when {problem} occurred.",
                        )
                        out += connection.execute_command(
                            cmd,
                            custom_exception=DcbExecutionError,
                            expected_return_codes={0},
                        ).stdout
            if cli_out.return_code != 0:
                raise DcbExecutionError(f"Exception from Unknown Error: {out}")
        return out

    def set_ets(
        self,
        user_priority_mapping: list[tuple],
        bandwidth_per_traffic_class: list[int],
        mode: str = "ieee",
    ) -> None:
        """Set ETS via lldptool (ieee) / dcbtool (cee).

        :param user_priority_mapping: User Priority mapping to Traffic Classes
        :param bandwidth_per_traffic_class: bandwidth percentage per Traffic Class
        :param mode: DCBX mode version - ieee|cee
        :raises DcbExecutionError: when a wrong mode is specified or the command return code is unexpected
        """
        if mode.lower() == "ieee":
            up2tc = ""
            tcbw = ",".join(map(str, bandwidth_per_traffic_class))
            tsa = ",".join([f"{i}:ets" for i in range(len(user_priority_mapping))])
            command_list = [
                f"lldptool -Ti {self.interface_name} -V ETS-CFG enableTx=yes willing=no "
                f"up2tc={up2tc} tcbw={tcbw} tsa={tsa}",
                f"lldptool -Ti {self.interface_name} -V ETS-REC enableTx=yes up2tc={up2tc} tcbw={tcbw} tsa={tsa}",
            ]
        elif mode.lower() == "cee":
            pgid_list = [0] * 8
            pgpct_list = [0] * 8
            for tc, priorities in enumerate(user_priority_mapping):
                for prio in priorities:
                    pgid_list[prio] = tc
                pgpct_list[tc] = bandwidth_per_traffic_class[tc]
            pgid = "".join(map(str, pgid_list))
            pgpct = ",".join(map(str, pgpct_list))
            command_list = [f"dcbtool sc {self.interface_name} pg w:0 e:1 a:1 pgid:{pgid} pgpct:{pgpct}"]
        else:
            raise DcbExecutionError(f"Incorrect mode: {mode}, expected modes: ieee or cee")
        self._execute_qos_command_and_check_output(self._connection, command_list)

    def set_pfc(self, pfc_per_priority: list[bool], mode: str = "ieee") -> None:
        """Set PFC via lldptool (ieee) / dcbtool (cee).

        :param pfc_per_priority: list of 8 Bool values for each priority, True is for PFC ON
        :param mode: DCBX mode version - ieee|cee
        :raises DcbExecutionError: when a wrong mode is specified or the command return code is unexpected
        """
        if mode.lower() == "ieee":
            enabled_list = [priority for priority, pfc in enumerate(pfc_per_priority) if pfc]
            enabled = ",".join(map(str, enabled_list))
            command = f"lldptool -Ti {self.interface_name} -V PFC enabled={enabled} enableTx=yes willing=no"
        elif mode.lower() == "cee":
            pfcup = "".join(str(int(priority)) for priority in pfc_per_priority)
            command = f"dcbtool sc {self.interface_name} pfc w:0 e:1 a:1 pfcup:{pfcup}"
        else:
            raise DcbExecutionError(f"Incorrect mode: {mode}, expected modes: ieee or cee")
        self._execute_qos_command_and_check_output(self._connection, command)

    def get_dcb(self) -> dict[str, dict[str, Any]]:
        """Get complete DCB configuration for ETS, PFC and APP TLVs, local and remote.

        :return: Dictionary of QoS configuration
        """
        qos = {}
        qos.update(self.get_ets())
        qos.update(self.get_pfc())
        return qos

    def get_ets(self, from_cache: bool = False) -> dict[str, dict[str, Any]]:
        """Get local ETS TLV configuration of the interface_name.

        :param from_cache: use current configuration output
        :return: Dictionary of local ETS TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(check_type="pg")
        return self._parse_qos(LOCAL_ETS)

    def get_pfc(self, from_cache: bool = False) -> dict[str, bool]:
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

    def _parse_qos(self, key: str) -> dict[str, dict[str, Any]]:
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
    def _parse_line(line: str, pattern: str) -> list[int]:
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
                ets_config[current_tc] = {
                    "TSA": "ETS",
                    "Bandwidth": bw,
                    "Priorities": [],
                }

    @staticmethod
    def _set_up_config(tc_list: list, ets_config: dict) -> None:
        """To set user priority data in ets_config.

        :param tc_list: list with user priority
        :param ets_config: ets config data
        """
        for up, tc in enumerate(tc_list):
            ets_config[str(tc)]["Priorities"].append(up)
