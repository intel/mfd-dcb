# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Module for WINDOWS OS."""

import json
import logging
import re
from mfd_common_libs import add_logging_level, log_levels, os_supported
from mfd_const.qos import LOCAL_ETS, LOCAL_PFC, LOCAL_APP, REMOTE_ETS, REMOTE_PFC, REMOTE_APP
from mfd_typing import OSName, DeviceID
from mfd_typing.utils import strtobool
from mfd_win_registry import WindowsRegistry
from typing import Dict, List, TYPE_CHECKING, Optional

from .const import PFC_STATS, QOS_ENABLED
from .enums import WindowsDcbMode, PfcType
from .exceptions import DcbException, DcbExecutionError
from .mfd_dcb import Dcb

if TYPE_CHECKING:
    from mfd_connect import RPyCConnection

logger = logging.getLogger(__name__)
add_logging_level("MODULE_DEBUG", log_levels.MODULE_DEBUG)


class WindowsDcb(Dcb):
    """Class to handle Dcb in Windows."""

    @os_supported(OSName.WINDOWS)
    def __init__(self, *, connection: "RPyCConnection") -> None:
        """Initialize Windows DCB."""
        super().__init__(connection=connection)
        # dcb variables
        self._enable_dcb_keyword = ""

        # create object for windows registry mfd
        self.winreg_obj = WindowsRegistry(connection=connection)

    def is_willing(self) -> bool:
        """Get Willing status of DCB configuration on the server.

        :raises DcbExecutionError: if command execution errored
        :return: True or False depends on willing status ON or OFF
        """
        command = "Get-NetQosDcbxSetting | select Willing"
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

        willing = output.stdout.splitlines()[3].strip()
        return strtobool(willing)

    def set_willing(self, *, enable: bool, is_40g_or_later: bool, adapter_name: str = "") -> None:
        """Turn ON or OFF Willing status of DCB configuration on the server.

        :param enable: Enable or Disable Willing
                       if Enable Switch Settings, else OS Controlled
        :param is_40g_or_later: Adapter is 40G and later or not
                                If False, Adapter name to be given
        :param adapter_name: Name of an adapter
        :raises DcbException: When adapter input is not provided.
                              Adapter input is mandatory when adapter capacity is lesser than 40G
        :raises DcbExecutionError: if command execution errored
        """
        enable_disable = 1 if enable else 0

        command = f"Set-NetQosDcbxSetting -Willing {enable_disable} -Confirm:$false"
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

        if not is_40g_or_later:
            if not adapter_name:
                raise DcbException("adapter_name input is mandatory when adapter capacity is lesser than 40G")
            else:
                switch_or_os = "Switch Settings" if enable else "OS Controlled"
                command = (
                    f"Set-IntelNetAdapterSetting -Name '{adapter_name}' -DisplayName 'DCB' "
                    f"-DisplayValue '{switch_or_os}'"
                )
                output = self._connection.execute_powershell(command)
                if output.stderr:
                    raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

    def set_policy(self, name: str, priority: int, parameters: str = "") -> None:
        """
        Create Quality of Service policy. Give it a name, assign the User Priority and apply additional parameters.

        :param name: Name of QoS policy
        :param priority: User Priority
        :param parameters: Additional parameters for a policy, like source IP address
        :raises DcbExecutionError: if command execution errored
        """
        command = f'New-NetQosPolicy -Name "{name}" -PriorityValue8021Action {priority} {parameters} -Confirm:$false'
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

    def remove_policy(self, name: str) -> None:
        """Remove Quality of Service policy with a given name.

        :param name: QoS policy name
        :raises DcbExecutionError: if command execution errored
        """
        command = f'Remove-NetQosPolicy -Name "{name}" -Confirm:$false'
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

    def get_policies(self) -> Dict:
        """Get all Quality of Service policies.

        :raises DcbExecutionError: if command execution errored
        :return: Dictionary of QoS policies with 'Name' as a key and value is a dictionary of other field-value pairs
        """
        command = "Get-NetQosPolicy"
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

        policies = {}
        current_policy = ""
        for out_line in output.stdout.splitlines():
            if ":" in out_line:
                key_value = out_line.split(":")
                key = key_value[0].strip()
                value = key_value[1].strip()

                if key == "Name":
                    current_policy = value
                    policies.update({current_policy: {}})
                else:
                    policies[current_policy].update({key: value})

        return policies

    def verify_policy(self, expected_policies: Dict, policies: Dict = None) -> bool:
        """Verify if NetQosPolicies are correct.

        :param expected_policies: reference policy configuration
        :param policies: policy configuration, if None, get current configuration from adapter
        """
        if policies is None:
            policies = self.get_policies()

        correct = True
        for name, expected_values in expected_policies.items():
            if name in policies:
                actual_priority = policies[name]["PriorityValue"]
                expected_priority = expected_values["PriorityValue"]
                if actual_priority != expected_priority:
                    logger.log(
                        level=log_levels.MODULE_DEBUG,
                        msg=f"Policy {name} is set to priority {actual_priority}, "
                        f"expected priority {expected_priority}",
                    )
                    correct = False
            else:
                logger.log(level=log_levels.MODULE_DEBUG, msg=f"Missing policy {name}")
                correct = False

        return correct

    def set_qos(self, adapter_name: str, enable: bool) -> None:
        """Turn ON or OFF Quality of Service on the adapter.

        :param adapter_name: Name of an adapter
        :param enable: Enable or Disable Quality of Service
        :raises DcbExecutionError: if command execution errored
        """
        enable_disable = "Enable" if enable else "Disable"

        command = f'{enable_disable}-NetAdapterQos "{adapter_name}" -Confirm:$false'
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

    def is_qos_enabled(self, adapter_name: str, from_cache: bool = False) -> bool:
        """Get QoS Enabled status.

        :param adapter_name: Name of an adapter
        :param from_cache: use current Get-NetAdapterQos output
        :return: Trus if QoS config enabled, else False
        """
        if not from_cache:
            self._read_qos_configuration(adapter_name)

        search = re.search(r"Enabled\s:\s(True|False)", self._qos_output)
        if search:
            return strtobool(search.group(1))
        else:
            return False

    def _read_qos_configuration(self, adapter_name: str) -> None:
        """Run Get-NetAdapterQos command for given adapter and store it in self._qos_output for future use.

        :param adapter_name: Name of an adapter
        :raises DcbExecutionError: if command execution errored
        """
        command = f'Get-NetAdapterQos "{adapter_name}"'
        output = self._connection.execute_powershell(command, expected_return_codes=[0])
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

        output = output.stdout.replace("\r", "")
        output = re.sub(" +", " ", output)

        self._qos_output = output

    def set_default_config(self) -> None:
        """
        Revert to default DCB settings - all User Priorities in Traffic Class 0 with bandwidth 100% and PFC disabled.

        :raises DcbExecutionError: if command execution errored
        """
        command = "Remove-NetQosTrafficClass -Confirm:$false"
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

        command = "Remove-NetQosPolicy -Confirm:$false"
        output = self._connection.execute_powershell(command)
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")
        self.set_pfc([False] * 8)

    def set_pfc(self, pfc_per_priority: list) -> None:
        """Turn ON or OFF Priority Flow Control for each User Priority.

        :param pfc_per_priority: List of 8 Bool values for each priority, True is for PFC ON
        :raises ValueError: when pfc_per_priority list length is not equal to 8
        :raises DcbExecutionError: if command execution errored
        """
        if len(pfc_per_priority) != 8:
            raise ValueError(
                f"Unexpected length for pfc_per_priority. Expected: 8, actual length: {len(pfc_per_priority)}"
            )

        enable_priority = []
        disable_priority = []

        for priority, enable in enumerate(pfc_per_priority):
            if enable:
                enable_priority.append(priority)
            else:
                disable_priority.append(priority)

        for action, priorities_list in [("Enable", enable_priority), ("Disable", disable_priority)]:
            if len(priorities_list) > 0:
                priorities = ",".join(str(i) for i in priorities_list)
                command = f"{action}-NetQosFlowControl -Priority {priorities} -Confirm:$false"
                output = self._connection.execute_powershell(command)
                if output.stderr:
                    raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

    def set_ets(self, user_priority_mapping: list, bandwidth_per_traffic_class: list) -> None:
        """
        Set ETS configuration based on User Priority mapping to Traffic Classes and given bandwidth.

        Traffic Class 0 for Windows is default and will have all User Priorities that were not used elsewhere and all
        available bandwidth left. keep dummy entry as first element in input list, as it is considered for unaltered
        default traffic class 0

        :param user_priority_mapping: User Priority mapping to Traffic Classes, list of tuples, each tuple is a next
        Traffic Class with given User Priorities as integer values
        :param bandwidth_per_traffic_class: List of bandwidth percentage values, each integer value is a bandwidth
        for next Traffic Class
        :raises ValueError: when user_priority_mapping is less or equal to 1 or it is not the same length as
        bandwidth_per_traffic_class
        """
        if len(user_priority_mapping) <= 1:
            raise ValueError("User Priority mapping for ETS must include more than 1 Traffic Class")

        if len(user_priority_mapping) != len(bandwidth_per_traffic_class):
            raise ValueError(
                "Number of Traffic Classes for User Priority mapping and bandwidth percentage lists must \
                be the same"
            )

        for tc, priorities in enumerate(user_priority_mapping):
            if tc == 0:
                continue

            priorities_string = ",".join(map(str, priorities))
            command = (
                f"New-NetQosTrafficClass -Name 'TC{tc}' -priority {priorities_string} -BandwidthPercentage "
                f"{bandwidth_per_traffic_class[tc]} -Algorithm ETS"
            )
            output = self._connection.execute_powershell(command)
            if output.stderr:
                raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")

    def get_dcb(self, adapter_name: str) -> Dict:
        """Get complete DCB configuration for ETS, PFC and APP TLVs, local and remote.

        :param adapter_name: Name of an adapter
        :return: Dictionary of QoS configuration
        """
        qos = {}

        qos.update(self.get_ets(adapter_name))
        qos.update(self.get_pfc(adapter_name, from_cache=True))
        qos.update(self.get_app(adapter_name, from_cache=True))
        qos.update(self.get_remote_ets(adapter_name, from_cache=True))
        qos.update(self.get_remote_pfc(adapter_name, from_cache=True))
        qos.update(self.get_remote_app(adapter_name, from_cache=True))

        return qos

    def get_ets(self, adapter_name: str, from_cache: bool = False) -> Dict:
        """Get local ETS TLV configuration of the adapter.

        :param adapter_name: Name of an adapter
        :param from_cache: use current Get-NetAdapterQos output
        :return: Dictionary of local ETS TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(adapter_name)

        return self._parse_ets("OperationalTrafficClasses", LOCAL_ETS)

    def _parse_ets(self, traffic_classes: str, key: str) -> Dict:
        """Get operational or remote QoS traffic classes as dictionary.

        :param traffic_classes: OperationalTrafficClasses or RemoteTrafficClasses
        :param key: key in configuration dictionary for ETS
        :return: Dictionary of QoS traffic classes configuration
        """
        ets = {}
        output = self._qos_output

        exp = (
            traffic_classes
            + r".*\n.*\n(?P<pg>\s(?P<tc>\d)\s(?P<tsa>ETS|Strict)(\s(?P<bw>\d+)%)?\s(?P<up>(.(-.)?,?)+)\n)"
        )
        search = re.search(exp, output)
        while search:
            if key not in ets:
                ets.update({key: {}})

            output = re.sub(search.group("pg"), "", output)

            priorities = []
            priorities_output = search.group("up")
            for prio_range in priorities_output.split(","):
                if "-" in prio_range:
                    begin = int(prio_range[0])
                    end = int(prio_range[2])
                    priorities.extend(list(range(begin, end + 1)))
                else:
                    priorities.append(int(prio_range))

            ets[key].update(
                {
                    search.group("tc"): {
                        "TSA": search.group("tsa"),
                        "Bandwidth": int(search.group("bw") or "0"),
                        "Priorities": priorities,
                    }
                }
            )
            search = re.search(exp, output)

        return ets

    def get_pfc(self, adapter_name: str, from_cache: bool = False) -> Dict:
        """Get local PFC TLV configuration of the adapter.

        :param adapter_name: Name of an adapter
        :param from_cache: use current Get-NetAdapterQos output
        :return: Dictionary of local PFC TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(adapter_name)

        return self._parse_pfc("OperationalFlowControl", LOCAL_PFC)

    def _parse_pfc(self, flow_control: str, key: str) -> Dict:
        """Get operational or remote QoS flow control as dictionary.

        :param flow_control: OperationalFlowControl or RemoteFlowControl
        :param key: key in configuration dictionary for PFC
        :return: Dictionary of QoS flow control configuration
        """
        pfc = {}

        pfc_per_priority = [False] * 8
        search = re.search(flow_control + r"\s:\sAll Priorities Enabled", self._qos_output)
        if search:
            pfc_per_priority = [True] * 8
        else:
            search = re.search(flow_control + r"\s:\s[a-zA-Z]+\s(?P<up>(\d(-\d)?,?)+)", self._qos_output)
            if search:
                priority_ranges = search.group("up").split(",")
                for priority_range in priority_ranges:
                    if "-" in priority_range:
                        for i in range(int(priority_range[0]), int(priority_range[2]) + 1):
                            pfc_per_priority[i] = True
                    else:
                        pfc_per_priority[int(priority_range)] = True

        pfc.update({key: pfc_per_priority})
        return pfc

    def get_app(self, adapter_name: str, from_cache: bool = False) -> Dict:
        """Get local APP TLV configuration of the adapter.

        :param adapter_name: Name of an adapter
        :param from_cache: use current Get-NetAdapterQos output
        :return: Dictionary of local APP TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(adapter_name)

        return self._parse_app("OperationalClassifications", LOCAL_APP)

    def _parse_app(self, classifications: str, key: str) -> Dict:
        """Get operational or remote QoS classification as dictionary.

        :param classifications: OperationalClassifications or RemoteClassifications
        :param key: key in configuration dictionary for APP
        :return: Dictionary of QoS classification configuration
        """
        app = {}
        output = self._qos_output

        exp = classifications + r".*\n.*\n(?P<cls>\s(?P<protocol>\w*)\s(?P<port>.*)\s(?P<up>\d)\n)"
        search = re.search(exp, output)
        while search:
            if key not in app:
                app.update({key: {}})

            output = re.sub(search.group("cls"), "", output)
            app[key].update(
                {search.group("port"): {"Priority": int(search.group("up")), "Protocol": search.group("protocol")}}
            )
            search = re.search(exp, output)

        return app

    def get_remote_ets(self, adapter_name: str, from_cache: bool = False) -> Dict:
        """Get remote ETS TLV configuration of the adapter.

        :param adapter_name: Name of an adapter
        :param from_cache: use current Get-NetAdapterQos output
        :return: Dictionary of remote ETS TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(adapter_name)

        return self._parse_ets("RemoteTrafficClasses", REMOTE_ETS)

    def get_remote_pfc(self, adapter_name: str, from_cache: bool = False) -> Dict:
        """Get remote PFC TLV configuration of the adapter.

        :param adapter_name: Name of an adapter
        :param from_cache: use current Get-NetAdapterQos output
        :return: Dictionary of remote PFC TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(adapter_name)

        return self._parse_pfc("RemoteFlowControl", REMOTE_PFC)

    def get_remote_app(self, adapter_name: str, from_cache: bool = False) -> Dict:
        """Get remote APP TLV configuration of the adapter.

        :param adapter_name: Name of an adapter
        :param from_cache: use current Get-NetAdapterQos output
        :return: Dictionary of remote APP TLV configuration
        """
        if not from_cache:
            self._read_qos_configuration(adapter_name)

        return self._parse_app("RemoteClassifications", REMOTE_APP)

    def set_dcb_operational_value(self, adapter_description: str, dcb_setting: str, dcb_value: str) -> None:
        """Set operational value for a given DCB setting.

        :param adapter_description: Description of an adapter
        :param dcb_setting: name of DCB setting as it is defined in DMIX Powershell
        :param dcb_value: DCB DisplayValue to set
        :raises DcbExecutionError: if command execution errored
        """
        output = self._connection.execute_powershell(
            f"Set-IntelNetAdapterSetting -Name '{adapter_description}' -DisplayName '{dcb_setting}' "
            f"-DisplayValue '{dcb_value}'"
        )
        if output.stderr:
            raise DcbExecutionError(f"Unable to set DCB operational value due to error: {output.stderr}")

    def get_dcb_operational_value(self, adapter_description: str, dcb_setting: str) -> str:
        """Retrieve the operational value for a given DCB setting.

        :param adapter_description: Description of an adapter
        :param dcb_setting: name of DCB setting as it is defined in DMIX Powershell
        :raises DcbExecutionError: if command execution errored
        :return: value of DCB setting
        """
        output = self._connection.execute_powershell(
            f"(Get-IntelNetAdapterStatus -Name '{adapter_description}' -Status 'DCB' | where-object "
            f"{{$_.Displayname -eq '{dcb_setting}'}}).DisplayValue"
        )
        if output.stderr:
            raise DcbExecutionError(f"Unable to retrieve DCB operational value due to error: {output.stderr}")
        else:
            return output.stdout.replace("\n", "")

    def verify_dcb(
        self,
        adapter_name: str,
        dcb_map: Dict[str, Dict[str, str]],
        dcb_config: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Verify if DCB configuration is correct.

        :param adapter_name: Name of an adapter
        :param dcb_map: reference DCB configuration
        :param dcb_config: DCB configuration, if None, get current configuration from adapter
        :return: True or False
        """
        use_get_dcb = False
        if dcb_config is None:
            use_get_dcb = True

        try:
            if use_get_dcb:
                dcb_config = self.get_dcb(adapter_name)

            ets_correct = self.verify_ets(adapter_name, dcb_map, ets_config=dcb_config[LOCAL_ETS])
            pfc_correct = self.verify_pfc(adapter_name, dcb_map, pfc_config=dcb_config[LOCAL_PFC])

            if LOCAL_APP in dcb_map:
                if LOCAL_APP in dcb_config:
                    app_correct = self.verify_app(adapter_name, dcb_map, app_config=dcb_config[LOCAL_APP])
                else:
                    logger.log(level=log_levels.MODULE_DEBUG, msg="APP TLV is missing from DCB configuration")
                    app_correct = False
            else:
                app_correct = True

            if ets_correct and pfc_correct and app_correct:
                return True

        except Exception as e:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Could not verify DCB configuration\n{e}")

        return False

    def verify_ets(
        self,
        adapter_name: str,
        dcb_map: Dict[str, Dict[str, str]],
        ets_config: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> bool:
        """Verify if ETS configuration is correct.

        :param adapter_name: Name of an adapter
        :param dcb_map: reference DCB configuration
        :param ets_config: ETS configuration, if None, get current configuration from adapter
        :return: True or False
        """
        if ets_config is None:
            ets_config = self.get_ets(adapter_name)[LOCAL_ETS]

        correct = True
        for expected_tc in dcb_map[LOCAL_ETS].values():
            missing_tc = True
            for actual_tc in ets_config.values():
                if actual_tc == expected_tc:
                    missing_tc = False
                    break

            if missing_tc:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"Missing Traffic Class with User Priorities {expected_tc['Priorities']} and \
                            bandwidth {expected_tc['Bandwidth']}",
                )
                correct = False

        return correct

    def verify_pfc(
        self, adapter_name: str, dcb_map: Dict[str, List[bool]], pfc_config: Optional[Dict[str, List[bool]]] = None
    ) -> bool:
        """Verify if PFC configuration is correct.

        :param adapter_name: Name of an adapter
        :param dcb_map: reference DCB configuration
        :param pfc_config: PFC configuration, if None, get current configuration from adapter
        :return: True or False
        """
        if pfc_config is None:
            pfc_config = self.get_pfc(adapter_name)[LOCAL_PFC]

        correct = True
        for up, expected_pfc in enumerate(dcb_map[LOCAL_PFC]):
            actual_pfc = pfc_config[up]
            if expected_pfc != actual_pfc:
                logger.log(
                    level=log_levels.MODULE_DEBUG,
                    msg=f"PFC for User Priority {up} is {self.pfc_bool_to_str(actual_pfc)} \
                            but it should be {self.pfc_bool_to_str(expected_pfc)}",
                )
                correct = False

        return correct

    def verify_app(
        self,
        adapter_name: str,
        dcb_map: Dict[str, Dict[str, str]],
        app_config: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> bool:
        """Verify if APP TLV configuration is correct.

        :param adapter_name: Name of an adapter
        :param dcb_map: reference DCB configuration
        :param app_config: APP TLV configuration, if None, get current configuration from adapter
        :return: True or False
        """
        if app_config is None:
            app_config = self.get_app(adapter_name)[LOCAL_APP]

        correct = True
        for port, expected in dcb_map[LOCAL_APP].items():
            if port in app_config:
                actual_priority = app_config[port]["Priority"]
                expected_priority = expected["Priority"]
                if actual_priority != expected_priority:
                    logger.log(
                        level=log_levels.MODULE_DEBUG,
                        msg=f"Port {port} is advertised with priority {actual_priority}, \
                                but expected priority is {expected_priority}",
                    )
                    correct = False
            else:
                logger.log(level=log_levels.MODULE_DEBUG, msg=f"Missing port {port} in APP TLV")
                correct = False

        return correct

    def pfc_bool_to_str(self, enabled: bool) -> str:
        """Convert bool value to string enabled/disabled.

        :param enabled: PFC value
        :return: enabled/disabled string
        """
        return "enabled" if enabled else "disabled"

    def remove_dcb_all_user_priorities(self) -> None:
        """Remove all DCB user priorities.

        :raises DcbExecutionError: if command execution errored
        """
        output = self._connection.execute_powershell("Remove-NetQosPolicy -Confirm:$false")
        if output.stderr:
            raise DcbExecutionError(f"Error while removing QoS Policies: {output.stderr}")

    def get_all_dcb_operational_values(self, adapter_description: str) -> Dict[str, str]:
        """Get all operational value for a given DCB setting.

        :param adapter_description: Description of an adapter
        :raises DcbExecutionError: If command execution errored
        :raises RuntimeError: If unable to retrieve DCB operational values
        :return: Value of DCB setting keywords and values
        """
        output = self._connection.execute_powershell(
            f"Get-IntelNetAdapterStatus -Name '{adapter_description}' -Status DCB | ConvertTo-json",
            expected_return_codes={0},
        )
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")
        if output.stdout:
            retval = {}
            for item in json.loads(output.stdout):
                retval[item["DisplayName"]] = item["DisplayValue"]
            return retval
        else:
            raise RuntimeError("Unable to retrieve DCB operational values")

    def get_dcb_status(self, adapter_description: str) -> tuple:
        """Get DCB status (enabled or disabled) and willing mode.

        :param adapter_description: Description of an adapter
        :raises ValueError: If DCB operation value not found
        :return: DCB status and willing mode
        """
        dcb_oper_val = self.get_dcb_operational_value(adapter_description, "DCB")
        if dcb_oper_val == WindowsDcbMode.SWITCH.value:
            return True, True
        elif dcb_oper_val == WindowsDcbMode.OS.value:
            return True, False
        elif dcb_oper_val == WindowsDcbMode.DISABLED.value:
            return False, False
        elif dcb_oper_val == WindowsDcbMode.ENABLED.value:
            return (
                True,
                self._connection.execute_powershell("(get-Netqosdcbxsetting).Willing").stdout.strip().lower() == "true",
            )
        else:
            raise ValueError("There is no DCB operation value could find.")

    def set_dcb_status(self, adapter_description: str, *, enable_dcb: bool, enable_willing_mode: bool) -> bool:
        """Set DCB option and willing mode.

        :param adapter_description: Description of an adapter
        :param enable_dcb: DCB option to set; True to enable, False to disable
        :param enable_willing_mode: Willing mode to set; True to enable, False to disable
        :raises DcbExecutionError: if command execution errored
        :raises DcbException: if any operation failure occured
        :return: True, if set dcb operation succeed
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg="set willing mode with PowerShell cmdlet")
        output = self._connection.execute_powershell(
            f"Set-Netqosdcbxsetting -willing:${'true' if enable_willing_mode else 'false'} -confirm:$false",
            expected_return_codes={},
        )
        if output.return_code != 0 or output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")
        if enable_willing_mode != strtobool(
            self._connection.execute_powershell("(get-Netqosdcbxsetting).Willing", expected_return_codes={0})
            .stdout.strip()
            .lower()
        ):
            raise DcbException(f"Could not {'en' if enable_willing_mode else 'dis'}able willing mode.")
        return self._set_dcb(adapter_description, enable_dcb, enable_willing_mode)

    def _set_dcb(self, adapter_description: str, enable_dcb: bool, enable_willing_mode: bool) -> bool:
        """Set DCB option and willing mode.

        :param adapter_description: Description of an adapter
        :param enable_dcb: DCB option to set; True to enable, False to disable
        :param enable_willing_mode: Willing mode to set; True to enable, False to disable
        :raises DcbExecutionError: if command execution errored
        :raises DcbException: if any operation failure occured
        :return: True, if set dcb operation succeed
        """
        logger.log(level=log_levels.MODULE_DEBUG, msg="set DCB with PowerShell cmdlet")
        if not enable_dcb:
            dcb_value = "Disabled"
        elif self._enable_dcb_keyword == "":
            dcb_value = "Enabled"
        elif not enable_willing_mode and self._enable_dcb_keyword == WindowsDcbMode.SWITCH.value:
            dcb_value = WindowsDcbMode.OS.value
        else:
            dcb_value = self._enable_dcb_keyword

        output = self._connection.execute_powershell(
            f'Set-Intelnetadaptersetting -DisplayName "DCB" -DisplayValue "{dcb_value}" -Name "{adapter_description}"'
        )
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")
        if not output.stdout:
            if self._enable_dcb_keyword == "":
                dcb_value = WindowsDcbMode.SWITCH.value if enable_willing_mode else WindowsDcbMode.OS.value
                output = self._connection.execute_powershell(
                    f'Set-Intelnetadaptersetting -DisplayName "DCB" -DisplayValue "{dcb_value}"'
                    ' -Name "{adapter_description}"'
                )
            if not output.stdout:
                raise DcbException(f"Could not {'en' if enable_dcb else 'dis'}able DCB option.")
        if enable_dcb and self._enable_dcb_keyword != "":
            self._enable_dcb_keyword = (
                WindowsDcbMode.SWITCH.value if dcb_value == WindowsDcbMode.OS.value else dcb_value
            )

        return True

    def get_pfc_enabled_bits(
        self, adapter_name: str, adapter_description: str, is_40g_or_later: bool
    ) -> Optional[tuple]:
        """Get remote and local PFC enable bits for all user priorities.

        :param adapter_name: Name of an adapter
        :param adapter_description: Description of an adapter
        :param is_40g_or_later: Adapter is 40G and later or not
        :raises DcbExecutionError: If exception raised from private methods
        :return: PFC state for remote and local DCB configs, None if there is any error
        """
        remote_pfc_bits = None
        local_pfc_bits = None

        if not self.is_debugps_ready():
            try:
                remote_pfc_bits = self._get_remote_pfc_enabled_bits_by_pscmd(adapter_name)
                local_pfc_bits = self._get_local_pfc_enabled_bits_by_pscmd()
            except DcbExecutionError:
                if is_40g_or_later:
                    raise DcbExecutionError("DebugPS is not ready to use yet and could not execute PS CmdLets")
                else:
                    raise DcbExecutionError("DebugPS does not support 10G SKU and and could not execute PS CmdLets")
        else:
            remote_pfc_bits = self._get_pfc_enabled_bits_by_dps(adapter_description, PfcType.REMOTE)
            local_pfc_bits = self._get_pfc_enabled_bits_by_dps(adapter_description, PfcType.LOCAL)

        if remote_pfc_bits is None or local_pfc_bits is None:
            return None
        return remote_pfc_bits, local_pfc_bits

    def is_debugps_ready(self) -> bool:
        """Check DebugPS library is installed and loaded.

        :return: True if DebugPS is ready to use; False if not
        """
        output = self._connection.execute_powershell("get-dpsver", expected_return_codes={})
        if output.return_code != 0:
            logger.log(
                level=log_levels.MODULE_DEBUG, msg=f"Host_Win.is_debugps_ready: get-dpsver RC {output.return_code}"
            )
            return False
        else:
            if (
                not output.stdout.strip()
                or "warning" in output.stdout.lower()
                or "error" in output.stdout.lower()
                or "not recognized" in output.stdout.lower()
            ):
                logger.log(level=log_levels.MODULE_DEBUG, msg=f"Host_Win.is_debugps_ready: unexpected output {output}")
                return False
        return True

    def _get_remote_pfc_enabled_bits_by_pscmd(self, adapter_name: str) -> Optional[List[str]]:
        """Get remote PFC enable bits by PowerShell CmdLets.

        :param adapter_name: Name of an adapter
        :raises DcbExecutionError: If unexpected return code found
        :return: PFC state for remote DCB configs
        """
        remote_pfc = ["False"] * 8
        cmd = f'Get-NetAdapterQos -Name "{adapter_name}"'
        output = self._connection.execute_powershell(cmd, expected_return_codes={})
        if output.return_code != 0:
            raise DcbExecutionError(f"Command {cmd} ended with return code: {output.return_code}")
        elif not output.stdout:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Command {cmd} ended with no output")
            return None

        _priority_keywords = ["remoteflowcontrol", "prior", "enabled"]
        for line in output.stdout.splitlines():
            # find a line includes all keywords
            if all([keyword in line.lower() for keyword in _priority_keywords]):  # pylint: disable=use-a-generator
                priorities = re.search(r"[0-9][0-9\-, ]+", line).group().strip()
                for _prios in priorities.split(","):
                    prios = _prios.strip()
                    if "-" in prios:
                        for index in range(int(prios.split("-")[0]), int(prios.split("-")[1]) + 1):
                            remote_pfc[index] = "True"
                    else:
                        remote_pfc[int(prios)] = "True"
                break
        return remote_pfc

    def _get_local_pfc_enabled_bits_by_pscmd(self) -> Optional[List[str]]:
        """Get local PFC enable bits by PowerShell CmdLets.

        :raises DcbExecutionError: If unexpected return code found
        :return: PFC state for local DCB configs
        """
        cmd = "Get-NetQosFlowControl | select Enabled"
        output = self._connection.execute_powershell(cmd, expected_return_codes={})
        if output.return_code != 0:
            raise DcbExecutionError(f"Command {cmd} ended with return code: {output.return_code}")
        elif not output.stdout:
            logger.log(level=log_levels.MODULE_DEBUG, msg=f"Command {cmd} ended with no output")
            return None

        return [line.strip() for line in output.stdout.split("-------")[1].splitlines() if line.strip()]

    def _get_pfc_enabled_bits_by_dps(
        self, adapter_description: str, pfc_type: PfcType = PfcType.LOCAL
    ) -> Optional[List[str]]:
        """Get remote or local PFC enable bits by Debug PS.

        :param adapter_description: Description of an adapter
        :param pfc_type: Local or Remote PFC enabled bits to find
        :raises ValueError: If pfc_type input is invalid
        :return: PFC state for remote or local DCB configs
        """
        if pfc_type == PfcType.LOCAL or pfc_type == PfcType.REMOTE:
            cmd = (
                f"(get-dpsdcb | ?{{$_.PortName -eq '{adapter_description}'}})."
                f"{pfc_type.value.capitalize()}Config.Pfc.PfcEnableBits"
            )
            output = self._connection.execute_powershell(cmd)

            if not output.stdout.strip():
                logger.log(
                    level=log_levels.MODULE_DEBUG, msg=f"Could not get PFC enable bits for {adapter_description}"
                )
                return None
            return [bits.strip() for bits in output.stdout.splitlines()]
        else:
            raise ValueError("Keyword to get PFC enabled bits with DebugPS has to be one from PfcType enum class")

    def get_pfc_port_statistics(self, adapter_description: str, priority: int) -> Dict[str, int]:
        """Get PFC RX/TX XOFF, XON counters for the port for a given priority.

        :param adapter_description: Description of an adapter
        :param priority: User priority (0 - 7)
        :raises ValueError: If user input priority value is invalid
        :raises DcbExecutionError: If command execution errored
        :raises RuntimeError: If unable to retrieve PFC statistics
        :return: RX, TX counters for XOFF, XON pause frames
        """
        if priority not in range(8):
            raise ValueError("Invalid priority value, must be from 0 - 7")

        output = self._connection.execute_powershell(
            f"(get-dpspfc | ?{{$_.PortName -eq '{adapter_description}'}}) | convertto-json", expected_return_codes={}
        )
        if output.stderr:
            raise DcbExecutionError(f"Error while executing windows command: {output.stderr}")
        if not output.stdout:
            raise RuntimeError(f"Could not retrieve PFC statistics for {adapter_description}")

        pfc = json.loads(output.stdout)
        pfc_stats = {}
        for stat in PFC_STATS:
            pfc_stats[stat] = pfc[stat][priority]
        return pfc_stats

    def get_pfc_counters(self, adapter_description: str) -> Dict[int, Dict[str, int]]:
        """Get PFC counters values for all User Priorities.

        :param adapter_description: Description of an adapter
        :return: User Priorities and their counter values
        """
        pfc_counters = {}

        for priority in range(8):
            pfc_counters[priority] = {}
            pfc_stats = self.get_pfc_port_statistics(adapter_description, priority)
            xon_rx_counter = pfc_stats.get("GLPRT_PXONRXCNT")
            xoff_rx_counter = pfc_stats.get("GLPRT_PXOFFRXCNT")
            xon_tx_counter = pfc_stats.get("GLPRT_PXONTXCNT")
            xoff_tx_counter = pfc_stats.get("GLPRT_PXOFFTXCNT")
            pfc_counters[priority].update({"xon_rx": xon_rx_counter})
            pfc_counters[priority].update({"xoff_rx": xoff_rx_counter})
            pfc_counters[priority].update({"xon_tx": xon_tx_counter})
            pfc_counters[priority].update({"xoff_tx": xoff_tx_counter})

        return pfc_counters

    def set_dcb_user_priority_to_tcp_port(self, tested_ip: str, user_priority: int = 1, tcp_port: int = 5000) -> None:
        """Set user priority to port.

        :param tested_ip: Peer IP address
        :param user_priority: user priority to set (0~7)
        :param tcp_port: TCP port number to allow traffic for the user priority
        :raises DcbExecutionError: if command execution errored
        :raises RuntimeError: if unexpected return code during command execution
        """
        cmd = (
            f'New-NetQosPolicy -Name "Prio{user_priority} BW" -PriorityValue8021Action {user_priority}'
            f" -IPSrcPrefixMatchCondition {tested_ip} "
            f"-IPDstPortStartMatchCondition {tcp_port} -IPDstPortEndMatchCondition {tcp_port}"
        )
        output = self._connection.execute_powershell(cmd, expected_return_codes={})
        if output.stderr or output.return_code != 0:
            raise RuntimeError(f"Could not assign QoS Policy of user priority {user_priority}")

    def get_dcb_max_supported_traffic_class(self, is_40g_or_later: bool, device_id: "DeviceID") -> int:
        """Get maximum number of traffic class that the current adapter support.

        All 10G but Niantic supports up to 4 TC and 40G or later NICs support 8 TC.

        :param is_40g_or_later: Adapter is 40G and later or not
        :param device_id: Device ID of an adapter
        :return: maximum number of TC supports
        """
        if is_40g_or_later or device_id == DeviceID(0x10FB):
            return 8
        else:
            return 4

    def set_dcb(self, enabled: bool, adapter_name: str) -> None:
        """Set dcb feature: enabled/disabled.

        :param enabled: Boolean input to enable/disable dcb feature
        :param adapter_name: Name of an adapter
        """
        act = "1" if enabled else "0"
        for feature in QOS_ENABLED:
            self.winreg_obj.set_feature(adapter_name, feature, act)
