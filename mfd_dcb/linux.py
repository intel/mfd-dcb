# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Module for Linux OS."""

from __future__ import annotations

import logging
import re
from typing import List, Union, Dict, TYPE_CHECKING, Any
import time

from mfd_common_libs import add_logging_level, log_levels, os_supported
from mfd_typing import OSName
from mfd_ethtool import Ethtool

from .exceptions import DcbExecutionError
from .data_structures import State
from .mfd_dcb import Dcb
import mfd_dcb.dcbnl_wrapper
import mfd_dcb.dcbtool_wrapper


if TYPE_CHECKING:
    from mfd_connect import RPyCConnection
    from mfd_switchmanagement.base import Switch

logger = logging.getLogger(__name__)
add_logging_level("MODULE_DEBUG", log_levels.MODULE_DEBUG)


class LinuxDcb(Dcb):
    """Class to handle Dcb in Linux."""

    @os_supported(OSName.LINUX)
    def __init__(self, *, connection: "RPyCConnection") -> None:
        """Initialize Linux DCB."""
        super().__init__(connection=connection)
        # create object for mfd Ethtool
        self.ethtool_obj = Ethtool(connection=connection)

    def _execute_qos_command_and_check_output(self, cmd_list: Union[List[str], str]) -> str:
        """
        Execute command and check output for unexpected problems and try to fix them.

        :param cmd_list: list of commands to execute
        :returns stdout
        :raises DcbExecutionError: for non zero return code other than known errors.
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
            cli_out = self._connection.execute_command(cmd, expected_return_codes={})
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
                    self._connection.execute_command(
                        recovery_cmd, custom_exception=DcbExecutionError, expected_return_codes={0, 1}
                    )
                for problem in rerun_cmd_after_problem_list:
                    if problem in out:
                        logger.log(
                            level=log_levels.MODULE_DEBUG,
                            msg=f"Rerun command {cmd} after recovery action, when {problem} occurred.",
                        )
                        out += self._connection.execute_command(
                            cmd, custom_exception=DcbExecutionError, expected_return_codes={0}
                        ).stdout
            if cli_out.return_code != 0:
                raise DcbExecutionError(f"Exception from Unknown Error: {out}")
        return out

    def set_ets(
        self,
        user_priority_mapping: List[(int)],
        bandwidth_per_traffic_class: List[int],
        interface_name: str,
        mode: str = "ieee",
    ) -> None:
        """Set ETS configuration based on User Priority mapping to Traffic Classes and given bandwidth.

        :param user_priority_mapping: User Priority mapping to Traffic Classes, list of tuples, each tuple is a next
        Traffic Class with given User Priorities as integer values
        user_priority_mapping = [(0, 1), (2, 3), (5, 4), (6, 7)]
        :param bandwidth_per_traffic_class: List of bandwidth percentage values, each integer value is a bandwidth for
        next Traffic Class
        bandwidth_per_traffic_class = [25, 25, 25, 25]
        :param mode: DCBX mode version - ieee|cee
        :param interface_name: Network adapter
        :raises DcbExecutionError: when user_priority_mapping is less or equal to 1 or it is not the same length as
        bandwidth_per_traffic_class or wrong mode is specified
        :raises DcbExecutionError: when return code of bash command is unexpected
        """
        if not isinstance((user_priority_mapping and bandwidth_per_traffic_class), list):
            raise DcbExecutionError("user_priority_mapping and bandwidth_per_traffic_class must be list")
        if len(user_priority_mapping) != len(bandwidth_per_traffic_class):
            raise DcbExecutionError(
                "Number of Traffic Classes for User Priority mapping and bandwidth percentage lists must " "be the same"
            )
        if mode.lower() == "ieee":
            up2tc_list = []
            up2tc = ",".join(up2tc_list)
            tcbw = ",".join(map(str, bandwidth_per_traffic_class))
            tsa = [",".join([f"{i}:ets" for i in range(len(user_priority_mapping))])][0]
            command_list = [
                f"lldptool -Ti {interface_name} -V ETS-CFG enableTx=yes willing=no up2tc={up2tc} tcbw={tcbw} tsa={tsa}",
                f"lldptool -Ti {interface_name} -V ETS-REC enableTx=yes up2tc={up2tc} tcbw={tcbw} tsa={tsa}",
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
            command_list = [f"dcbtool sc {interface_name} pg w:0 e:1 a:1 pgid:{pgid} pgpct:{pgpct}"]
        else:
            raise DcbExecutionError(f"Incorrect mode: {mode}, expected modes: ieee or cee")
        self._execute_qos_command_and_check_output(command_list)

    def set_pfc(
        self,
        interface_name: str,
        pfc_per_priority: List[bool],
        mode: str = "ieee",
    ) -> None:
        """Turn ON or OFF Priority Flow Control for each User Priority.

        :param interface_name: Network adapter
        :param pfc_per_priority: List of 8 Bool values for each priority, True is for PFC ON
        :param mode: DCBX mode version - ieee|cee
        :raises DcbExecutionError: when pfc_per_priority list length is not equal to 8 or wrong mode is specified
        :raises DcbExecutionError: when return code of bash command is unexpected
        """
        if len(pfc_per_priority) != 8:
            raise DcbExecutionError(
                f"Unexpected length for pfc_per_priority. " f"Expected: 8, actual length: {len(pfc_per_priority)}"
            )
        if mode.lower() == "ieee":
            enabled_list = []
            for priority, pfc in enumerate(pfc_per_priority):
                if pfc:
                    enabled_list.append(priority)
            enabled = ",".join(map(str, enabled_list))
            command = f"lldptool -Ti {interface_name} -V PFC enabled={enabled} enableTx=yes willing=no"
        elif mode.lower() == "cee":
            pfcup_list = [int(priority) for priority in pfc_per_priority]
            pfcup = "".join(map(str, pfcup_list))
            command = f"dcbtool sc {interface_name} pfc w:0 e:1 a:1 pfcup:{pfcup}"
        else:
            raise DcbExecutionError(f"Incorrect mode: {mode}, expected modes: ieee or cee")
        self._execute_qos_command_and_check_output(command)

    def restart_lldpad(self, action: str = "default") -> None:
        """Restart/stop lldpad service and lldp agent daemon.

        :param action: action to do, default(means stop and restart), start, restart or stop
        :raise DcbExecutionError: For incorrect action
        """
        if action == "default":
            actions = ["stop", "restart"]
        elif action in ("restart", "start", "stop"):
            actions = [action]
        else:
            raise DcbExecutionError(f"Incorrect action: {action}, expected actions: restart, start, stop or default")
        cmd_list = [
            "lldpad -k",
            "lldpad -s",
        ]
        self._execute_qos_command_and_check_output(cmd_list)
        for _action in actions:
            cmd_list = [
                f"systemctl {_action} lldpad",
                f"systemctl {_action} lldpad.socket",
                f"systemctl {_action} lldpad.service",
            ]
            self._execute_qos_command_and_check_output(cmd_list)

    def set_sw_dcb(self, interface_name: str, enable: bool = False, dcbx_mode: str = "ieee") -> None:
        """Turn ON or OFF software DCB.

        :param interface_name: Network adapter
        :param enable: Enable or Disable software DCB
        :param dcbx_mode: DCBX mode version - ieee|cee
        :raises DcbExecutionError: when wrong mode is specified
        """
        if dcbx_mode == "ieee":
            sw_dcb = "rxtx" if enable else "disabled"
            command = f"lldptool -li {interface_name} adminStatus={sw_dcb}"
        elif dcbx_mode == "cee":
            sw_dcb = "on" if enable else "off"
            command = f"dcbtool sc {interface_name} dcb {sw_dcb}"
        else:
            raise DcbExecutionError(f"Incorrect mode: {dcbx_mode}, expected modes: ieee or cee")
        self._execute_qos_command_and_check_output(command)

    def set_dcbx_mode(self, interface_name: str, mode: str = "", fw_lldp: bool = False) -> None:
        """Set adapter DCB to given DCBX mode.

        :param interface_name: Network adapter
        :param mode: DCBX mode version - ieee|cee
        :param fw_lldp: FW-LLDP status
        :raises DcbExecutionError: when wrong mode is specified
        """
        if not fw_lldp:
            self.set_sw_dcb(enable=True, dcbx_mode=mode, interface_name=interface_name)
        cmd_list = [f"dcbtool sc {interface_name} dcb on"]
        force_cee = ""
        enable_tx = ""
        if mode == "ieee":
            enable_tx = "no"
        elif mode == "cee":
            force_cee = "force-"
            enable_tx = "yes"
        else:
            raise DcbExecutionError(f"Incorrect mode: {mode}, expected modes: ieee or cee")
        cmd_list = [
            f"dcbtool sc {interface_name} dcb on",
            f"lldptool -Ti {interface_name} -V CEE-DCBX enableTx={enable_tx}",
            f"dcbtool sc dcbx v:{force_cee}cee",
        ]
        self._execute_qos_command_and_check_output(cmd_list)
        self.restart_lldpad()

    def is_sw_dcb_mode_enabled(
        self,
        interface_name: str,
        dcbx_mode: str = "ieee",
    ) -> bool:
        """Check software DCB status.

        :param dcbx_mode: DCBX mode version - ieee|cee
        :param interface_name: Network adapter
        :raises DcbExecutionError: when wrong mode is specified
        :raises DcbExecutionError: if cant read status
        """
        if dcbx_mode == "ieee":
            command = f"lldptool -li {interface_name} adminStatus"
            regex = r"adminStatus=(\S*)"
        elif dcbx_mode == "cee":
            command = f"dcbtool gc {interface_name} dcb"
            regex = r"DCB State:\s*(\S*)"
        else:
            raise DcbExecutionError(f"Incorrect mode: {dcbx_mode}, expected modes: ieee or cee")
        out = self._execute_qos_command_and_check_output(command)
        status = re.search(regex, out)
        if status:
            return bool(status.group(1) == "on" or status.group(1) == "rxtx")
        else:
            raise DcbExecutionError("Can't get actual DCB status!")

    def set_willing(
        self,
        interface_name: str,
        enable: bool,
        mode: str = "ieee",
        is_fwlldp_enabled: bool = True,
    ) -> None:
        """
        Turn ON or OFF Willing of remote DCB configuration on the server.

        :param interface_name: Network adapter
        :param enable: Enable or Disable Willing
        :param mode: DCBX mode version - ieee|cee
        :param is_fwlldp_enabled: interface_flag
        :raises DcbExecutionError: when wrong mode is specified
        :raises DcbExecutionError: when return code of bash command is unexpected
        """
        if mode == "ieee":
            willing = "yes" if enable else "no"
            cmd_list = [f"lldptool -Ti {interface_name} -V CEE-DCBX enableTx=no", "dcbtool sc dcbx v:cee"]
            if not is_fwlldp_enabled:
                lldptool_tlv = f"lldptool -Ti {interface_name} -V"
                cmd_list.extend(
                    [
                        f"{lldptool_tlv} ETS-CFG enableTx=yes willing={willing}",
                        f"{lldptool_tlv} ETS-REC enableTx=yes",
                        f"{lldptool_tlv} PFC enable=yes willing={willing} enableTx=yes",
                    ]
                )
        elif mode == "cee":
            willing = "1" if enable else "0"
            cmd_list = [f"lldptool -Ti {interface_name} -V CEE-DCBX enableTx=yes", "dcbtool sc dcbx v:force-cee"]
            if not is_fwlldp_enabled:
                cmd_list.extend(
                    [
                        f"dcbtool sc {interface_name} pg w:0 e:0 a:0",
                        f"dcbtool sc {interface_name} pfc w:0 e:0 a:0",
                        f"dcbtool sc {interface_name} pg w:{willing} e:1 a:1",
                        f"dcbtool sc {interface_name} pfc w:{willing} e:1 a:1",
                    ]
                )
        else:
            raise DcbExecutionError(f"Incorrect mode: {mode}, expected modes: ieee or cee")
        self._execute_qos_command_and_check_output(cmd_list)

    def _get_frame_list(
        self,
        priority: int,
        is_10g_adapter: bool = False,
        is_40g_adapter: bool = False,
    ) -> List[str]:
        """Get frame list based on detected adapter.

        :param priority: priority number to create proper frame
        :param is_10g_adapter: Network adapter
        :param is_40g_adapter: Network adapter.
        :raises ValueError: If user input priority value is invalid
        :returns: list of frame_types
        """
        if priority not in range(8):
            raise ValueError("Invalid priority value, must be from 0 - 7")
        if is_10g_adapter:
            return [
                f"tx_pb_{priority}_pxon",
                f"tx_pb_{priority}_pxoff",
                f"rx_pb_{priority}_pxon",
                f"rx_pb_{priority}_pxoff",
            ]
        elif is_40g_adapter:
            return ["xon_tx", "xoff_tx", "xon_rx", "xoff_rx", "xon_2_xoff"]
        else:
            return [
                f"tx_priority_{priority}_xon_nic",
                f"tx_priority_{priority}_xoff_nic",
                f"rx_priority_{priority}_xon_nic",
                f"rx_priority_{priority}_xoff_nic",
            ]

    def _get_pfc_counter_dict(
        self,
        out: str,
        pfc_counters: Dict[str, str],
        priority: List[int],
        frame_list: List[bool],
        adapter_10G: bool = False,
    ) -> Dict[str, Dict[str, str]]:
        """
        pfc_counters dict.

        :param out: cli out
        :param pfc_counters: pfc_counters dict
        :param priority: priority counters
        :param frame_list: frame_list
        :param adapter_10G: to check the frame type.
        :raise DcbExecutionError for No match frame_type
        :return: Dictionary for frame_type with its counter value.
        """
        for frame_type in frame_list:
            xframeregex = rf"{frame_type}(?:._*)\[?'(?P<frame_value>\d+)?'\]"
            match = re.search(xframeregex, out, re.MULTILINE)
            if not match:
                raise DcbExecutionError(f"No match found for {frame_type} for _get_pfc_counter_dict")
            frame_type_10g = [("tx_pb", "pxon"), ("tx_pb", "pxoff"), ("rx_pb", "pxon"), ("rx_pb", "pxoff")]
            frame_type_non_10g = [
                ("tx_priority", "xon"),
                ("tx_priority", "xoff"),
                ("rx_priority", "xon"),
                ("rx_priority", "xoff"),
            ]
            if adapter_10G:
                ftype = frame_type_10g
            else:
                ftype = frame_type_non_10g
            if all(tx_rx in frame_type for tx_rx in ftype[0]):
                frame_type = "xon_tx"
            elif all(tx_rx in frame_type for tx_rx in ftype[1]):
                frame_type = "xoff_tx"
            elif all(tx_rx in frame_type for tx_rx in ftype[2]):
                frame_type = "xon_rx"
            elif all(tx_rx in frame_type for tx_rx in ftype[3]):
                frame_type = "xoff_rx"
            pfc_counters[priority][frame_type] = int(match.group("frame_value"))
        return pfc_counters

    def get_pfc_counters(
        self,
        interface_name: str,
        is_10g_adapter: bool = False,
        is_40g_adapter: bool = False,
    ) -> Dict[str, Dict[str, str]]:
        """Get PFC counters values for all User Priorities.

        :param interface_name: Name of the Network adapter under Test.
        :param is_10g_adapter: Indication whether network interface supports 10G speed
        :param is_40g_adapter: Indication whether network interface supports 40G speed
        :return: Dictionary of frame_type and value for pfc counters with user Priorities.
        """
        out = self.ethtool_obj.get_statistics_xonn_xoff(device_name=f"{interface_name}")

        pfc_counters = {}
        for priority in range(8):
            pfc_counters[priority] = {}
            frame_list = self._get_frame_list(priority, is_10g_adapter, is_40g_adapter)
            if is_10g_adapter:
                pfc_counters = self._get_pfc_counter_dict(
                    str(out), pfc_counters, priority, frame_list, adapter_10G=True
                )
            elif is_40g_adapter:
                for frame_type in frame_list:
                    xframeregex = rf".*priority_{priority}_{frame_type}(?:._*)\w+=\[?'(?P<frame_value>\d)?'\]"
                    match = re.search(xframeregex, str(out), re.MULTILINE)
                    if match:
                        pfc_counters[priority][frame_type] = int(match.group("frame_value"))
            else:
                pfc_counters = self._get_pfc_counter_dict(str(out), pfc_counters, priority, frame_list)
        return pfc_counters

    def remove_lldpad_conf(self) -> None:
        """
        Remove lldpad conf file to restore settings.

        lldpad configat /var/lib/lldpad/lldpad.conf
        """
        self.restart_lldpad(action="stop")
        logger.log(level=log_levels.MODULE_DEBUG, msg="Remove lldpad.conf file.")
        command = "rm -rf /var/lib/lldpad/lldpad.conf"
        self._connection.execute_command(command)
        self.restart_lldpad(action="start")

    def get_dcb(
        self,
        interface_name: str,
        tool_name: str = "dcbnl",
    ) -> Dict[str, Dict[str, str]]:
        """Get complete DCB configuration for ETS, PFC and APP TLVs, local and remote.

        :param tool_name: name of tool, dcbnl/dcbtool to get DCB config.
        :param interface_name: Name of the Network Interface under Test.
        :return: Dictionary of QoS configuration.
        """
        self.tool = self._get_tool(tool_name=tool_name, interface_name=interface_name)
        return self.tool.get_dcb()

    def get_ets(
        self,
        interface_name: str,
        tool_name: str = "dcbnl",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get local ETS TLV configuration of the interface.

        :param interface_name: Name of the Network Interface under Test.
        :param tool_name: name of tool, dcbnl/dcbtool to get local ETS TLV config.
        :return: Dictionary of local ETS TLV configuration
        """
        self.tool = self._get_tool(tool_name=tool_name, interface_name=interface_name)
        return self.tool.get_ets()

    def _get_tool(
        self,
        interface_name: str,
        tool_name: str = "dcbnl",
    ) -> object:
        """Produce particular tool based on tool name.

        :param tool_name: name of tool, dcbtool / dcbnl.
        :param interface_name: Name of the Network Interface under Test.
        :return: instance of tool type
        """
        if "dcbtool" in tool_name:
            return mfd_dcb.dcbtool_wrapper.DcbTool(interface_name, self._connection)
        else:
            return mfd_dcb.dcbnl_wrapper.Dcbnl(interface_name, self._connection)

    def get_app(
        self,
        interface_name: str,
        tool_name: str = "dcbnl",
    ) -> Dict[str, Dict[str, Any]]:
        """Get local APP TLV configuration of the Interface.

        :param tool_name: name of tool (dcbnl/dcbtool) to get local APP TLV config.
        :param interface_name: Name of the Network Interface under Test.
        :raises DcbExecutionError: for dcbtool: not implemented
        :return: Dictionary of local APP TLV configuration
        """
        if tool_name == "dcbtool":
            raise DcbExecutionError("get_app not implemented in dcbtool")
        self.tool = self._get_tool(tool_name=tool_name, interface_name=interface_name)
        return self.tool.get_app()

    def get_pfc(
        self,
        interface_name: str,
        tool_name: str = "dcbnl",
    ) -> Dict[str, Dict[str, Any]]:
        """Get local PFC TLV configuration of the adapter.

        :param tool_name: name of tool, dcbtool/dcbtool
        :param interface_name: Name of the Network Interface under Test.
        :return: instance of tool type
        """
        self.tool = self._get_tool(tool_name=tool_name, interface_name=interface_name)
        return self.tool.get_pfc()

    def verify_dcb(
        self,
        interface_name: str,
        dcb_map: dict[str, dict[str, str]],
        dcb_config: dict[str, str] | None = None,
        retry: int | None = 6,
        interval: int | None = 10,
        switch: "Switch | None" = None,
        switch_port: str | None = None,
    ) -> bool:
        """Verify if DCB configuration is correct.

        :param interface_name: Name of the Network Interface under Test.
        :param dcb_map: Reference DCB configuration.
            DCB_MAP = {
                "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
                },
                "LOCAL_PFC": [False, False, False, True, True, False, False, False],
                "LOCAL_APP": {"3260": {"Priority": 4, "Protocol": "TCP"}},
            }
        :param dcb_config: DCB configuration. If None, get current configuration from adapter. Defaults to None.
        dcb_config = {"ETS": {0}, "PFC": {True}}
        :param retry: Number of retries for verifying DCB configuration. Defaults to 6.
        :param interval: Interval between verifying DCB configuration. Defaults to 10.
        :param switch: Executor of all switch methods. Defaults to None.
        :param switch_port: Switch port e.g., Te 1/25. Defaults to None.
        :raises DcbExecutionError: for dcbtool: not implemented
        :return: bool: True if DCB configuration is correct, False otherwise.
        """
        for attempt in range(retry + 1):
            try:
                dcb_config = dcb_config or self.get_dcb(interface_name)
                ets_correct = self.verify_ets(interface_name, dcb_map, ets_config=dcb_config.get("LOCAL_ETS"))
                pfc_correct = self.verify_pfc(interface_name, dcb_map, pfc_config=dcb_config.get("LOCAL_PFC"))
                app_correct = (
                    self.verify_app(interface_name, dcb_map, app_config=dcb_config.get("LOCAL_APP", {}))
                    if "LOCAL_APP" in dcb_map
                    else True
                )

                if ets_correct and pfc_correct and app_correct:
                    return True

            except DcbExecutionError as e:
                logger.log(level=log_levels.MODULE_DEBUG, msg=f"Could not verify DCB configuration\n{e}")

            if attempt < retry:
                self._retry_logic(switch, switch_port, interval, retry - attempt)

        return False

    def _retry_logic(
        self,
        switch: "Switch",
        switch_port: str,
        interval: int,
        retries_left: int,
    ) -> None:
        """Retry logic for verify_dcb method.

        :param switch: Executor of all switch methods.
        :param switch_port: Switch port e.g., Te 1/25.
        :param interval: Interval between retries.
        :param retries_left: Number of retries left.
        :return: None
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg="Restarting lldpad")
        self.restart_lldpad()
        if switch and switch_port:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg='Map did not load correctly, "shutdown",' f'and "no shutdown" port:{switch_port}.',
            )
            for status in [True, False]:
                switch.shutdown(status, switch_port)
                time.sleep(5)
        logger.log(level=log_levels.MODULE_DEBUG, msg=f"Retrying in {interval} seconds, {retries_left} tries remaining")
        time.sleep(interval)

    def verify_ets(
        self,
        interface_name: str,
        dcb_map: dict[str, dict[str, str]],
        ets_config: dict[str, dict[str, str]] | None = None,
    ) -> bool:
        """Verify if ETS configuration is correct.

        :param interface_name: Name of the Network Interface under Test.
        :param dcb_map: Reference DCB configuration.
            DCB_MAP = {
                "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
                },
                "LOCAL_PFC": [False, False, False, True, True, False, False, False],
                "LOCAL_APP": {"3260": {"Priority": 4, "Protocol": "TCP"}},
            }
        :param ets_config: ETS configuration. If None, get current configuration from adapter. Defaults to None.
        {'ETS': {'0': {'TSA': 'ETS', 'Bandwidth': 1000, 'Priorities': [0, 1, 2, 3, 4, 5, 6, 7]}}}
        :return: True if ETS configuration is correct, False otherwise.
        """
        ets_config = ets_config or self.get_ets(interface_name).get("LOCAL_ETS", {})
        # Extract expected and actual Traffic Classes (TC) configurations
        expected_tcs = list(dcb_map.get("LOCAL_ETS", {}).values())
        actual_tcs = list(ets_config.values())

        # Find missing TCs by comparing expected TCs against actual TCs
        missing_tcs = [tc for tc in expected_tcs if tc not in actual_tcs]

        # Log missing TCs
        for missing_tc in missing_tcs:
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Missing Traffic Class, Priorities {missing_tc['Priorities']}\
                 and bandwidth {missing_tc['Bandwidth']}",
            )

        # If there are no missing TCs, the configuration is correct
        logger.log(level=log_levels.MODULE_DEBUG, msg="Verify_ets success, no missing TC")
        return not missing_tcs

    def verify_pfc(
        self,
        interface_name: str,
        dcb_map: dict[str, dict[str, str]],
        pfc_config: dict[str, list[bool]] | None = None,
    ) -> bool:
        """Verify if PFC configuration is correct.

        :param interface_name: Name of the Network Interface under Test.
        :param dcb_map: Reference DCB configuration.
            DCB_MAP = {
                "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
                },
                "LOCAL_PFC": [False, False, False, True, True, False, False, False],
                "LOCAL_APP": {"3260": {"Priority": 4, "Protocol": "TCP"}},
            }
        :param pfc_config: PFC configuration. If None, get current configuration from adapter. Defaults to None.
        {'PFC': [True, False, True, False, True, False, True, False]}
        :return: True if PFC configuration is correct, False otherwise.
        """
        pfc_config = pfc_config or self.get_pfc(interface_name).get("LOCAL_PFC", {})
        # Check for any mismatch in PFC configuration
        mismatch_found = any(
            expected_pfc != pfc_config.get(up) for up, expected_pfc in enumerate(dcb_map.get("LOCAL_PFC", []))
        )

        # Log mismatches
        if mismatch_found:
            for up, expected_pfc in enumerate(dcb_map.get("LOCAL_PFC", [])):
                actual_pfc = pfc_config.get(up)
                if expected_pfc != actual_pfc:
                    logger.log(
                        level=log_levels.MODULE_DEBUG,
                        msg=f"PFC for User Priority {up} is {State.ENABLED if actual_pfc else State.DISABLED}\
                                and should be {State.ENABLED if expected_pfc else State.DISABLED}",
                    )
        logger.log(level=log_levels.MODULE_DEBUG, msg="Verify_pfc success, no mismatch found")
        return not mismatch_found

    def verify_app(
        self,
        interface_name: str,
        dcb_map: dict[str, dict[str, str]],
        app_config: dict[str, dict[str, str]] | None = None,
    ) -> bool:
        """Verify if APP TLV configuration is correct.

        :param interface_name: Name of the Network Interface under Test.
        :param dcb_map: Reference DCB configuration.
            DCB_MAP = {
                "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
                },
                "LOCAL_PFC": [False, False, False, True, True, False, False, False],
                "LOCAL_APP": {"3260": {"Priority": 4, "Protocol": "TCP"}},
            }
        :param app_config: APP TLV configuration. If None, get current configuration from adapter. Defaults to None.
        {'APP': {'0x8906': {'Priority': 3, 'Protocol': 'Ethertype'}, '3260': {'Priority': 34, 'Protocol': 'TCP'}}}
        :return: True if APP TLV configuration is correct, False otherwise.
        """
        if app_config is None:
            app_config = self.get_app(interface_name)["LOCAL_APP"]

        correct = True
        if "Linux" in self._connection.get_os_name():
            for _, local_app_table in app_config.items():
                correct = set(local_app_table.values()) == set(dcb_map["LOCAL_APP"].values())
        else:
            for port, expected in dcb_map["LOCAL_APP"].items():
                if port in app_config:
                    actual_priority = app_config[port]["Priority"]
                    expected_priority = expected["Priority"]
                    if actual_priority != expected_priority:
                        logger.log(
                            level=log_levels.MODULE_DEBUG,
                            msg=f"Port {port} is advertised on priority {actual_priority},\
                             expected priority {expected_priority}",
                        )
                        correct = False
                else:
                    logger.log(level=log_levels.MODULE_DEBUG, msg=f"Missing port {port} in APP TLV")
                    correct = False

        return correct
