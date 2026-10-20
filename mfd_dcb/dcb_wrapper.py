# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: MIT

"""Module for the iproute2 dcb tool."""

import re

from typing import TYPE_CHECKING, Any
from mfd_const.qos import LOCAL_ETS, LOCAL_PFC, LOCAL_APP
from .exceptions import DcbExecutionError, DcbExecutionProcessError

if TYPE_CHECKING:
    from mfd_connect import RPyCConnection

APP_SELECTORS = (
    "default-prio",
    "ethtype-prio",
    "stream-port-prio",
    "dgram-port-prio",
    "port-prio",
    "dscp-prio",
    "pcp-prio",
)


class DcbCli:
    """DcbCli class provides DCB configuration read-out using the iproute2 dcb tool (dcbnl netlink)."""

    def __init__(self, interface_name: str, connection: "RPyCConnection"):
        """Initialize class parameters.

        :param interface_name: tested interface
        :param connection: connection
        """
        self.interface_name = interface_name
        self._connection = connection

    def get_dcb(self, numeric: bool = True) -> dict[str, dict[str, Any]]:
        """Get complete DCB configuration for ETS, PFC and APP TLVs.

        :param numeric: when True (default), APP protocol values are read numerically (``dcb -N app show``)
        :return: Dictionary of QoS configuration
        """
        qos = {}
        qos.update(self.get_ets())
        qos.update(self.get_pfc())
        qos.update(self.get_app(numeric=numeric))
        return qos

    def get_ets(self) -> dict[str, dict[str, Any]]:
        """Get local ETS configuration of the interface via ``dcb ets show``.

        :return: Dictionary of local ETS configuration
        """
        output = self._run("ets")
        tc_tsa = self._extract_pairs(output, "tc-tsa")
        tc_bw = self._extract_pairs(output, "tc-bw")
        prio_tc = self._extract_pairs(output, "prio-tc")

        ets_config: dict[str, dict[str, Any]] = {}
        for tc, tsa in tc_tsa.items():
            ets_config[str(tc)] = {
                "TSA": tsa.upper(),
                "Bandwidth": int(tc_bw.get(tc, 0)),
                "Priorities": [],
            }
        for prio, tc in prio_tc.items():
            ets_config.setdefault(
                str(tc),
                {"TSA": "", "Bandwidth": int(tc_bw.get(tc, 0)), "Priorities": []},
            )
            ets_config[str(tc)]["Priorities"].append(prio)
        return {LOCAL_ETS: ets_config}

    def get_pfc(self) -> dict[str, list[bool]]:
        """Get local PFC configuration of the interface via ``dcb pfc show``.

        :return: Dictionary of local PFC configuration
        """
        output = self._run("pfc")
        prio_pfc = self._extract_pairs(output, "prio-pfc")
        pfc_config = [False] * 8
        for prio, state in prio_pfc.items():
            if 0 <= prio < 8:
                pfc_config[prio] = state == "on"
        return {LOCAL_PFC: pfc_config}

    def get_app(self, numeric: bool = True) -> dict[str, dict[str, Any]]:
        """Get local APP table of the interface via ``dcb app show``.

        :param numeric: when True (default), protocol values are read numerically via ``dcb -N app show``.
        :return: Dictionary of local APP configuration
        """
        output = self._run("app", numeric=numeric)
        app_config: dict[int, dict[str, Any]] = {}
        for no, (selector, protocol, priority) in enumerate(self._extract_app_entries(output)):
            app_config[no] = {
                "selector": selector.replace("-prio", ""),
                "priority": int(priority),
                "protocol": protocol,
            }
        return {LOCAL_APP: app_config}

    def set_ets(
        self,
        user_priority_mapping: list[tuple],
        bandwidth_per_traffic_class: list[int],
        mode: str = "ieee",
    ) -> None:
        """Set ETS configuration via ``dcb ets set``.

        :param user_priority_mapping: User Priority mapping to Traffic Classes, list of tuples, each tuple is a next
        Traffic Class with given User Priorities as integer values, e.g. [(0, 1), (2, 3), (5, 4), (6, 7)]
        :param bandwidth_per_traffic_class: list of bandwidth percentage values, one per Traffic Class
        :param mode: accepted for a common setter API across wrappers; not used by the iproute2 dcb tool
        :raises DcbExecutionError: when the command writes to stderr
        """
        tc_tsa = " ".join(f"{tc}:ets" for tc in range(len(user_priority_mapping)))
        tc_bw = " ".join(f"{tc}:{bw}" for tc, bw in enumerate(bandwidth_per_traffic_class))
        prio_tc = " ".join(f"{prio}:{tc}" for tc, priorities in enumerate(user_priority_mapping) for prio in priorities)
        command = f"dcb ets set dev {self.interface_name} willing off tc-tsa {tc_tsa} tc-bw {tc_bw} prio-tc {prio_tc}"
        self._execute_dcb_command(command)

    def set_pfc(self, pfc_per_priority: list[bool], mode: str = "ieee") -> None:
        """Set Priority Flow Control via ``dcb pfc set``.

        :param pfc_per_priority: list of 8 Bool values for each priority, True is for PFC ON
        :param mode: accepted for a common setter API across wrappers; not used by the iproute2 dcb tool
        :raises DcbExecutionError: when the command writes to stderr
        """
        prio_pfc = " ".join(f"{prio}:{'on' if pfc else 'off'}" for prio, pfc in enumerate(pfc_per_priority))
        command = f"dcb pfc set dev {self.interface_name} prio-pfc {prio_pfc}"
        self._execute_dcb_command(command)

    def set_app(self, proto_prio_map: dict | list[tuple], *, selector: str = "dscp-prio") -> None:
        """Add APP (protocol to priority) entries via ``dcb app add``.

        :param proto_prio_map: mapping of protocol to priority, e.g. {26: 3} (DSCP 26 -> priority 3, RoCEv2)
        :param selector: APP selector, e.g. "dscp-prio" (default), "ethtype-prio", "port-prio"
        :raises DcbExecutionError: when the mapping is invalid or the command writes to stderr
        """
        proto_prio = self._format_app_map(proto_prio_map)
        self._execute_dcb_command(f"dcb app add dev {self.interface_name} {selector} {proto_prio}")

    def del_app(self, proto_prio_map: dict | list[tuple], *, selector: str = "dscp-prio") -> None:
        """Delete specific APP (protocol to priority) entries via ``dcb app del``.

        :param proto_prio_map: mapping of protocol to priority to remove, e.g. {26: 3}
        :param selector: APP selector, e.g. "dscp-prio" (default), "ethtype-prio", "port-prio"
        :raises DcbExecutionError: when the mapping is invalid or the command writes to stderr
        """
        proto_prio = self._format_app_map(proto_prio_map)
        self._execute_dcb_command(f"dcb app del dev {self.interface_name} {selector} {proto_prio}")

    def replace_app(self, proto_prio_map: dict | list[tuple], *, selector: str = "dscp-prio") -> None:
        """Replace APP (protocol to priority) entries via ``dcb app replace``.

        :param proto_prio_map: mapping of protocol to the new priority, e.g. {26: 5} (DSCP 26 -> priority 5)
        :param selector: APP selector, e.g. "dscp-prio" (default), "ethtype-prio", "port-prio"
        :raises DcbExecutionError: when the mapping is invalid or the command writes to stderr
        """
        proto_prio = self._format_app_map(proto_prio_map)
        self._execute_dcb_command(f"dcb app replace dev {self.interface_name} {selector} {proto_prio}")

    def flush_app(self, selector: str | None = "dscp-prio") -> None:
        """Flush the APP table via ``dcb app flush``.

        :param selector: APP selector to flush; when None, all APP entries are flushed
        :raises DcbExecutionError: when the command writes to stderr
        """
        command = f"dcb app flush dev {self.interface_name}"
        if selector:
            command += f" {selector}"
        self._execute_dcb_command(command)

    @staticmethod
    def _format_app_map(proto_prio_map: dict | list[tuple]) -> str:
        """Format a protocol-to-priority mapping into the ``dcb app`` key argument.

        :param proto_prio_map: mapping of protocol to priority, e.g. {26: 3, 30: 3}, [(26, 3)] or {"0x8906": 3}
        :return: space separated "PROTO:PRIO" pairs, e.g. "26:3 30:3"
        :raises DcbExecutionError: when the mapping is empty or malformed
        """
        pairs = proto_prio_map.items() if isinstance(proto_prio_map, dict) else proto_prio_map
        try:
            formatted = " ".join(f"{proto}:{int(prio)}" for proto, prio in pairs)
        except (TypeError, ValueError) as err:
            raise DcbExecutionError(f"Invalid proto_prio_map: {proto_prio_map}") from err
        if not formatted:
            raise DcbExecutionError("proto_prio_map must contain at least one protocol:priority entry")
        return formatted

    def _execute_dcb_command(self, cmd_list: list[str] | str) -> None:
        """Execute iproute2 dcb tool command(s) and validate the return code and stderr.

        :param cmd_list: command or list of commands to execute
        :raises DcbExecutionProcessError: when a command returns a non-zero return code
        :raises DcbExecutionError: when a command writes to stderr
        """
        cmd_list = cmd_list if isinstance(cmd_list, list) else [cmd_list]
        for cmd in cmd_list:
            output = self._connection.execute_command(
                cmd,
                custom_exception=DcbExecutionProcessError,
                expected_return_codes=[0],
            )
            if output.stderr:
                raise DcbExecutionError(f"Error while executing '{cmd}': {output.stderr}")

    def _run(self, attribute: str, numeric: bool = False) -> str:
        """Run ``dcb <attribute> show`` for the interface and return stdout.

        :param attribute: dcb object to read - pfc, ets or app
        :param numeric: when True, pass the global ``-N`` option so values are printed numerically
        :return: command stdout
        :raises DcbExecutionError: when the command reports an error on stderr
        """
        numeric_opt = "-N " if numeric else ""
        command = f"dcb {numeric_opt}{attribute} show dev {self.interface_name}"
        output = self._connection.execute_command(
            command,
            custom_exception=DcbExecutionProcessError,
            expected_return_codes=[0],
        )
        if output.stderr:
            raise DcbExecutionError(f"Error while executing dcb {command}: {output.stderr}")
        return output.stdout

    @staticmethod
    def _extract_app_entries(output: str) -> list[tuple[str, str, str]]:
        """Extract APP table entries as an ordered sequence of ``(selector, protocol, priority)``.

        :param output: ``dcb app show`` stdout
        :return: ordered list of ``(selector, protocol, priority)`` tuples
        """
        entries: list[tuple[str, str, str]] = []
        current_selector = None
        for token in output.split():
            if token in APP_SELECTORS:
                current_selector = token
                continue
            if not current_selector:
                continue
            if current_selector == "default-prio":
                entries.append((current_selector, "0", token))
            elif ":" in token:
                protocol, _, priority = token.rpartition(":")
                entries.append((current_selector, protocol, priority))
        return entries

    @staticmethod
    def _extract_pairs(output: str, keyword: str) -> dict[Any, str]:
        """Extract the ``KEY:VALUE`` pairs that follow a dcb attribute keyword.

        :param output: dcb command stdout
        :param keyword: attribute keyword to read the pairs for, e.g. "prio-pfc", "tc-tsa", "dscp-prio"
        :return: mapping of parsed key to value string
        """
        match = re.search(rf"(?<![-\w]){re.escape(keyword)}\s+((?:\S+:\S+\s*)+)", output)
        pairs: dict[Any, str] = {}
        if not match:
            return pairs
        for token in match.group(1).split():
            if ":" not in token:
                break
            key, _, value = token.partition(":")
            pairs[int(key) if key.isdigit() else key] = value
        return pairs
