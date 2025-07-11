# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Tests for `mfd_dcb` package."""

from textwrap import dedent
import pytest
import re
from unittest.mock import patch
from mfd_connect import RPyCConnection
from mfd_connect.base import ConnectionCompletedProcess
from mfd_typing import OSName
from mfd_dcb import Dcb
from mfd_dcb.linux import LinuxDcb
from mfd_ethtool import Ethtool
import mfd_dcb.dcbtool_wrapper
from mfd_dcb.exceptions import DcbConnectedOSNotSupported, DcbExecutionError, DcbExecutionProcessError


class TestLinuxDcb:
    def test_pass(self):
        assert True

    @pytest.fixture()
    def dcb(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.LINUX
        mocker.patch("mfd_ethtool.Ethtool.check_if_available", mocker.create_autospec(Ethtool.check_if_available))
        mocker.patch(
            "mfd_ethtool.Ethtool.get_version", mocker.create_autospec(Ethtool.get_version, return_value="4.15")
        )
        mocker.patch(
            "mfd_ethtool.Ethtool._get_tool_exec_factory",
            mocker.create_autospec(Ethtool._get_tool_exec_factory, return_value="ethtool"),
        )
        dcb_obj = LinuxDcb(connection=conn)
        mocker.stopall()
        return dcb_obj

    def test_constructor_returns_linux_instance(self, dcb):
        assert re.search("Linux", str(dcb))

    def test_linux(self, mocker, dcb):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.LINUX
        assert isinstance(dcb.__new__(LinuxDcb, connection=conn), LinuxDcb)

    def test_unsupported_os(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.EFISHELL
        with pytest.raises(DcbConnectedOSNotSupported):
            Dcb(connection=conn)

    def test_set_ets_ieee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        user_priority_mapping = [(0, 1), (2, 3), (4, 5), (6, 7)]
        bandwidth_per_traffic_class = [25, 25, 25, 25]
        dcb.set_ets(user_priority_mapping, bandwidth_per_traffic_class, interface_name="eth1", mode="ieee")

    def test_set_ets_cee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        user_priority_mapping = [(0, 1), (2, 3), (4, 5), (6, 7)]
        bandwidth_per_traffic_class = [25, 25, 25, 25]
        dcb.set_ets(user_priority_mapping, bandwidth_per_traffic_class, interface_name="eth1", mode="cee")

    def test_execute_qos_command_and_check_output(self, dcb):
        cmd_output = dedent(
            """driver: ice
               version: 1.13.0_rc24
               firmware-version: 3.24 0x80019aa8 1.3346.0
               expansion-rom-version:
               bus-info: 0000:f4:00.0
               supports-statistics: yes
               supports-test: yes
               supports-eeprom-access: yes
               supports-register-dump: yes
               supports-priv-flags: yes"""
        )
        command = "ethtool -i eth1"
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=cmd_output, return_code=0, stderr=""
        )
        assert dcb._execute_qos_command_and_check_output(command)

    def test_execute_qos_command_and_check_invalid_output(self, dcb):
        command = "dcbtool sc"
        out = "invalid command argument: port was not specified"
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=out, return_code=0, stderr=""
        )
        dcb._execute_qos_command_and_check_output(command)

    def test_execute_qos_command_and_check_output_error(self, dcb):
        command = "dcbtool sc interface dcb on"
        output = dedent(
            """
            Command:    Set Config
            Feature:    DCB State
            Port:       interface
            Status:     Device not capable
            """
        )
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        with pytest.raises(DcbExecutionError):
            dcb._execute_qos_command_and_check_output(command)

    def test_execute_qos_command_and_check_output_known_error(self, dcb):
        cmd_output = dedent(
            "Command:   \tSet Config\nFeature:   \tDCB State\nPort:      \teth9\nStatus:    \tDevice not capable\n"
        )
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=cmd_output, return_code=8, stderr=""
        )
        with pytest.raises(DcbExecutionError):
            dcb._execute_qos_command_and_check_output("dcbtool sc eth9 dcb on")

    def test_set_pfc_ieee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        pfc_per_priority = [False, True, True, False, False, False, False, False]
        dcb.set_pfc(pfc_per_priority=pfc_per_priority, interface_name="eth1", mode="ieee")

    def test_set_pfc_cee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        pfc_per_priority = [False, True, True, False, False, False, False, False]
        dcb.set_pfc(pfc_per_priority=pfc_per_priority, interface_name="eth1", mode="cee")

    def test_set_pfc_input_error(self, dcb):
        error = "Unexpected length for pfc_per_priority. Expected: 8, actual length: 3"
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=error
        )
        with pytest.raises(DcbExecutionError):
            pfc_per_priority = [False, True, True]
            dcb.set_pfc(pfc_per_priority=pfc_per_priority, interface_name="eth1", mode="cee")

    def test_set_pfc_error_mode(self, dcb):
        error = "Incorrect mode: no_mode, expected modes: ieee or cee"
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=error
        )
        with pytest.raises(DcbExecutionError):
            pfc_per_priority = [False, True, True]
            dcb.set_pfc(pfc_per_priority=pfc_per_priority, interface_name="eth1", mode="no_mode")

    def test_restart_lldpad(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.restart_lldpad()

    def test_set_sw_dcb_ieee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_sw_dcb(interface_name="eth1", dcbx_mode="ieee")

    def test_set_sw_dcb_cee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_sw_dcb(interface_name="eth1", dcbx_mode="cee")

    def test_set_dcbx_mode_ieee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_dcbx_mode(interface_name="eth1", mode="ieee")

    def test_set_dcbx_mode_cee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_dcbx_mode(interface_name="eth1", mode="cee")

    def test_is_sw_dcb_mode_enabled_ieee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="adminStatus=rxtx\n", return_code=0, stderr=""
        )
        assert dcb.is_sw_dcb_mode_enabled(interface_name="eth1", dcbx_mode="ieee")

    def test_is_sw_dcb_mode_enabled_cee(self, dcb):
        cmd_out = dedent(
            """Command:   \tGet ConfigFeature:   \tDCB State
                     Port:      \teth4\nStatus:    \tSuccessful\nDCB State:\ton\n"""
        )
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=cmd_out, return_code=0, stderr=""
        )
        assert dcb.is_sw_dcb_mode_enabled(interface_name="eth1", dcbx_mode="cee")

    def test_set_willing_cee_execute(self, dcb):
        command = "dcbtool sc eth4 pfc w:1 e:1 a:1"
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args=command, stdout="", return_code=0, stderr=""
        )
        dcb.set_willing(interface_name="eth4", enable=True, mode="cee", is_fwlldp_enabled=False)
        dcb._connection.execute_command.assert_called_with(command, expected_return_codes={})

    def test_set_willing_ieee_execute(self, dcb):
        command = "lldptool -Ti eth4 -V PFC enable=yes willing=yes enableTx=yes"
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args=command, stdout="", return_code=0, stderr=""
        )
        dcb.set_willing(interface_name="eth4", enable=True, mode="ieee", is_fwlldp_enabled=False)
        dcb._connection.execute_command.assert_called_with(command, expected_return_codes={})

    def test_set_willing_with_ieee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        assert dcb.set_willing(interface_name="eth4", enable=True, mode="ieee", is_fwlldp_enabled=False) is None

    def test_set_willing_with_enable_false(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        assert dcb.set_willing(interface_name="eth4", enable=False, mode="ieee", is_fwlldp_enabled=False) is None

    def test_set_willing_with_cee(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        assert dcb.set_willing(interface_name="eth4", enable=True, mode="cee", is_fwlldp_enabled=False) is None

    def test_set_willing_with_wrong_mode(self, dcb):
        with pytest.raises(DcbExecutionError):
            dcb.set_willing(interface_name="eth4", enable=True, mode="None", is_fwlldp_enabled=False)

    def test_get_pfc_counters_default(self, dcb):
        std_out = dedent(
            """link_xon_rx.nic: 0
               link_xon_tx.nic: 0
               link_xoff_rx.nic: 0
               link_xoff_tx.nic: 0
               tx_priority_0_xon.nic: 0
               tx_priority_0_xoff.nic: 0
               tx_priority_1_xon.nic: 0
               tx_priority_1_xoff.nic: 0
               tx_priority_2_xon.nic: 0
               tx_priority_2_xoff.nic: 0
               tx_priority_3_xon.nic: 0
               tx_priority_3_xoff.nic: 0
               tx_priority_4_xon.nic: 0
               tx_priority_4_xoff.nic: 0
               tx_priority_5_xon.nic: 0
               tx_priority_5_xoff.nic: 0
               tx_priority_6_xon.nic: 0
               tx_priority_6_xoff.nic: 0
               tx_priority_7_xon.nic: 0
               tx_priority_7_xoff.nic: 0
               rx_priority_0_xon.nic: 0
               rx_priority_0_xoff.nic: 0
               rx_priority_1_xon.nic: 0
               rx_priority_1_xoff.nic: 0
               rx_priority_2_xon.nic: 0
               rx_priority_2_xoff.nic: 0
               rx_priority_3_xon.nic: 0
               rx_priority_3_xoff.nic: 0
               rx_priority_4_xon.nic: 0
               rx_priority_4_xoff.nic: 0
               rx_priority_5_xon.nic: 0
               rx_priority_5_xoff.nic: 0
               rx_priority_6_xon.nic: 0
               rx_priority_6_xoff.nic: 0
               rx_priority_7_xon.nic: 0
               rx_priority_7_xoff.nic: 0"""
        )
        cmd_output = {
            0: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            1: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            2: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            3: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            4: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            5: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            6: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            7: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
        }
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=std_out, return_code=0, stderr=""
        )
        assert dcb.get_pfc_counters(interface_name="enp59s0f1") == cmd_output

    def test_get_pfc_counters_40G(self, dcb):
        std_out = dedent(
            """
                link_xon_rx.nic: 0
                link_xon_tx.nic: 0
                link_xoff_rx.nic: 0
                link_xoff_tx.nic: 0
                tx_priority_0_xon.nic: 0
                tx_priority_0_xoff.nic: 0
                tx_priority_1_xon.nic: 0
                tx_priority_1_xoff.nic: 0
                tx_priority_2_xon.nic: 0
                tx_priority_2_xoff.nic: 0
                tx_priority_3_xon.nic: 0
                tx_priority_3_xoff.nic: 0
                tx_priority_4_xon.nic: 0
                tx_priority_4_xoff.nic: 0
                tx_priority_5_xon.nic: 0
                tx_priority_5_xoff.nic: 0
                tx_priority_6_xon.nic: 0
                tx_priority_6_xoff.nic: 0
                tx_priority_7_xon.nic: 0
                tx_priority_7_xoff.nic: 0
                rx_priority_0_xon.nic: 0
                rx_priority_0_xoff.nic: 0
                rx_priority_1_xon.nic: 0
                rx_priority_1_xoff.nic: 0
                rx_priority_2_xon.nic: 0
                rx_priority_2_xoff.nic: 0
                rx_priority_3_xon.nic: 0
                rx_priority_3_xoff.nic: 0
                rx_priority_4_xon.nic: 0
                rx_priority_4_xoff.nic: 0
                rx_priority_5_xon.nic: 0
                rx_priority_5_xoff.nic: 0
                rx_priority_6_xon.nic: 0
                rx_priority_6_xoff.nic: 0
                rx_priority_7_xon.nic: 0
                rx_priority_7_xoff.nic: 0"""
        )
        cmd_output = {0: {}, 1: {}, 2: {}, 3: {}, 4: {}, 5: {}, 6: {}, 7: {}}
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=std_out, return_code=0, stderr=""
        )
        assert dcb.get_pfc_counters(interface_name="enp59s0f1", is_40g_adapter=True) == cmd_output

    def test_get_pfc_counters_10G(self, dcb):
        std_out = dedent(
            """tx_flow_control_xon: 0
               rx_flow_control_xon: 0
               tx_flow_control_xoff: 0
               rx_flow_control_xoff: 0
               tx_pb_0_pxon: 0
               tx_pb_0_pxoff: 0
               tx_pb_1_pxon: 0
               tx_pb_1_pxoff: 0
               tx_pb_2_pxon: 0
               tx_pb_2_pxoff: 0
               tx_pb_3_pxon: 0
               tx_pb_3_pxoff: 0
               tx_pb_4_pxon: 0
               tx_pb_4_pxoff: 0
               tx_pb_5_pxon: 0
               tx_pb_5_pxoff: 0
               tx_pb_6_pxon: 0
               tx_pb_6_pxoff: 0
               tx_pb_7_pxon: 0
               tx_pb_7_pxoff: 0
               rx_pb_0_pxon: 0
               rx_pb_0_pxoff: 0
               rx_pb_1_pxon: 0
               rx_pb_1_pxoff: 0
               rx_pb_2_pxon: 0
               rx_pb_2_pxoff: 0
               rx_pb_3_pxon: 0
               rx_pb_3_pxoff: 0
               rx_pb_4_pxon: 0
               rx_pb_4_pxoff: 0
               rx_pb_5_pxon: 0
               rx_pb_5_pxoff: 0
               rx_pb_6_pxon: 0
               rx_pb_6_pxoff: 0
               rx_pb_7_pxon: 0
               rx_pb_7_pxoff: 0"""
        )
        cmd_output = {
            0: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            1: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            2: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            3: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            4: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            5: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            6: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
            7: {"xon_tx": 0, "xoff_tx": 0, "xon_rx": 0, "xoff_rx": 0},
        }
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args=std_out, stdout=std_out, return_code=0, stderr=""
        )
        assert dcb.get_pfc_counters(interface_name="enp94s0f0", is_10g_adapter=True) == cmd_output

    def test__get_pfc_counters_invalid_priority(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(ValueError):
            dcb._get_frame_list(priority=10)

    def test__get_pfc_counter_dict_invalid_input(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(
            DcbExecutionError, match=re.escape("No match found for tx_pb_0_pxon for _get_pfc_counter_dict")
        ):
            dcb._get_pfc_counter_dict(
                out="",
                pfc_counters={0: {}},
                priority=0,
                frame_list=["tx_pb_0_pxon", "tx_pb_0_pxoff", "rx_pb_0_pxon", "rx_pb_0_pxoff"],
            )

    def test_remove_lldpad_conf(self, dcb):
        command = "systemctl start lldpad.service"
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args=command, stdout="", return_code=0, stderr=""
        )
        dcb.remove_lldpad_conf()
        dcb._connection.execute_command.assert_called_with(command, expected_return_codes={})

    def test_get_dcb_dcbnl(self, dcb):
        dcbnl_out = """DCBX Mode: \n\tDCB_CAP_DCBX_HOST \n\tDCB_CAP_DCBX_VER_IEEE \n\nETS Data:
        tc: 0 tsa: ets, bw: 40%\n\t up:  0\n\t up:  1\n\t up:  2\n\t up:  5\n\t up:  6\n\t up:  7
        tc: 1 tsa: ets, bw: 30%\n\t up:  3\ntc: 2 tsa: ets, bw: 30%\n\t up:  4\ntc: 3 tsa: strict
        tc: 4 tsa: strict\ntc: 5 tsa: strict\ntc: 6 tsa: stricttc: 7 tsa: strict\n\nPFC Data:
        \tpfc_cap: 8 pfc_enable: 0x18\n\nApps Table:\n\tselector: 1 priority: 3 protocol: 0x8914
        \tselector: 2 priority: 4 protocol: 0xcbc\n\tselector: 1 priority: 3 protocol: 0x8906\n
        """
        cmd_output = {
            "ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            },
            "PFC": [False, False, False, True, True, False, False, False],
            "APP": {
                0: {"selector": 1, "priority": 3, "protocol": "0x8914"},
                1: {"selector": 2, "priority": 4, "protocol": "0xcbc"},
                2: {"selector": 1, "priority": 3, "protocol": "0x8906"},
            },
        }
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=dcbnl_out, return_code=0, stderr=""
        )
        assert dcb.get_dcb(interface_name="eth4", tool_name="dcbnl") == cmd_output

    def test_get_ets_dcbnl(self, dcb):
        dcbnl_out = """DCBX Mode: \n\tDCB_CAP_DCBX_HOST \n\tDCB_CAP_DCBX_VER_IEEE \n\nETS Data:
        tc: 0 tsa: ets, bw: 40%\n\t up:  0\n\t up:  1\n\t up:  2\n\t up:  5\n\t up:  6\n\t up:  7
        tc: 1 tsa: ets, bw: 30%\n\t up:  3\ntc: 2 tsa: ets, bw: 30%\n\t up:  4\ntc: 3 tsa: strict
        tc: 4 tsa: strict\ntc: 5 tsa: strict\ntc: 6 tsa: strict\ntc: 7 tsa: strict\n\nPFC Data:
        \tpfc_cap: 8 pfc_enable: 0x18\n\nApps Table:\n\tselector: 1 priority: 3 protocol: 0x8914
        \tselector: 2 priority: 4 protocol: 0xcbc\n\tselector: 1 priority: 3 protocol: 0x8906\n
        """
        cmd_output = {
            "ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            }
        }
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=dcbnl_out, return_code=0, stderr=""
        )
        assert dcb.get_ets(interface_name="eth4", tool_name="dcbnl") == cmd_output

    def test_get_app_dcbnl(self, dcb):
        dcbnl_out = """DCBX Mode: \n\tDCB_CAP_DCBX_HOST \n\tDCB_CAP_DCBX_VER_IEEE \n\nETS Data:
        tc: 0 tsa: ets, bw: 40%\n\t up:  0\n\t up:  1\n\t up:  2\n\t up:  5\n\t up:  6\n\t up:  7
        tc: 1 tsa: ets, bw: 30%\n\t up:  3\ntc: 2 tsa: ets, bw: 30%\n\t up:  4\ntc: 3 tsa: strict
        tc: 4 tsa: strict\ntc: 5 tsa: strict\ntc: 6 tsa: strict\ntc: 7 tsa: strict\n\nPFC Data:
        \tpfc_cap: 8 pfc_enable: 0x18\n\nApps Table:\n\tselector: 1 priority: 3 protocol: 0x8914
        \tselector: 2 priority: 4 protocol: 0xcbc\n\tselector: 1 priority: 3 protocol: 0x8906\n
        """
        cmd_output = {
            "APP": {
                0: {"selector": 1, "priority": 3, "protocol": "0x8914"},
                1: {"selector": 2, "priority": 4, "protocol": "0xcbc"},
                2: {"selector": 1, "priority": 3, "protocol": "0x8906"},
            }
        }
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=dcbnl_out, return_code=0, stderr=""
        )
        assert dcb.get_app(interface_name="eth4", tool_name="dcbnl") == cmd_output

    def test_get_ets_dcbtool(self, dcb, mocker):
        dcbtool_out = dedent(
            """
            Command:    Get Oper
            Feature:    Priority Groups
            Port:       p7p1
            Status:     Successful
            Oper Version: 0
            Max Version:  0
            Errors:     0x00 - none
            Oper Mode:  true
            Syncd:      true
            up2tc:      0 0 0 1 2 0 0 0
            pgpct:      10% 10% 80% 0% 0% 0% 0% 0%
            pgid:       0 0 0 1 2 0 0 0
            uppct:      100% 100% 100% 100% 100% 100% 100% 100%
            pg strict:  0 0 0 0 0 0 0 0
            pfcup:      0 0 0 0 0 0 0 0"""
        )
        cmd_output = {
            "ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "1": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "2": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "3": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
            }
        }
        mocker.patch(
            "mfd_dcb.linux.LinuxDcb._get_tool",
            mocker.create_autospec(
                LinuxDcb._get_tool, return_value=mfd_dcb.dcbtool_wrapper.DcbTool("eth4", dcb._connection)
            ),
        )
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=dcbtool_out, return_code=0, stderr=""
        )
        assert dcb.get_ets(interface_name="eth4", tool_name="dcbtool") == cmd_output
        dcb._connection.execute_command.assert_called_with(
            "dcbtool go eth4 pg", custom_exception=DcbExecutionProcessError
        )

    def test_get_app_dcbtool(self, dcb, mocker):
        mocker.patch(
            "mfd_dcb.linux.LinuxDcb._get_tool",
            mocker.create_autospec(
                LinuxDcb._get_tool, return_value=mfd_dcb.dcbtool_wrapper.DcbTool("eth4", dcb._connection)
            ),
        )
        with pytest.raises(DcbExecutionError, match=re.escape("get_app not implemented in dcbtool")):
            dcb.get_app(interface_name="eth4", tool_name="dcbtool")

    def test_get_dcb_dcbtool(self, dcb, mocker):
        dcbtool_out = dedent(
            """
            Command:    Get Oper
            Feature:    Priority Groups
            Port:       p7p1
            Status:     Successful
            Oper Version: 0
            Max Version:  0
            Errors:     0x00 - none
            Oper Mode:  true
            Syncd:      true
            up2tc:      0 0 0 1 2 0 0 0
            pgpct:      10% 10% 80% 0% 0% 0% 0% 0%
            pgid:       0 0 0 1 2 0 0 0
            uppct:      100% 100% 100% 100% 100% 100% 100% 100%
            pg strict:  0 0 0 0 0 0 0 0
            pfcup:      0 0 0 0 0 0 0 0"""
        )
        cmd_output = {
            "ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "1": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "2": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "3": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
            },
            "PFC": [True],
        }
        mocker.patch(
            "mfd_dcb.linux.LinuxDcb._get_tool",
            mocker.create_autospec(
                LinuxDcb._get_tool, return_value=mfd_dcb.dcbtool_wrapper.DcbTool("eth4", dcb._connection)
            ),
        )
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=dcbtool_out, return_code=0, stderr=""
        )
        assert dcb.get_dcb(interface_name="eth4", tool_name="dcbtool") == cmd_output

    def test_get_pfc_dcbtool(self, dcb, mocker):
        dcbtool_out = dedent(
            """
            Command:    Get Oper
            Feature:    Priority Groups
            Port:       p7p1
            Status:     Successful
            Oper Version: 0
            Max Version:  0
            Errors:     0x00 - none
            Oper Mode:  true
            Syncd:      true
            up2tc:      0 0 0 1 2 0 0 0
            pgpct:      10% 10% 80% 0% 0% 0% 0% 0%
            pgid:       0 0 0 1 2 0 0 0
            uppct:      100% 100% 100% 100% 100% 100% 100% 100%
            pg strict:  0 0 0 0 0 0 0 0
            pfcup:      0 0 0 0 0 0 0 0"""
        )
        cmd_output = {"PFC": [True]}
        mocker.patch(
            "mfd_dcb.linux.LinuxDcb._get_tool",
            mocker.create_autospec(
                LinuxDcb._get_tool, return_value=mfd_dcb.dcbtool_wrapper.DcbTool("eth4", dcb._connection)
            ),
        )
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=dcbtool_out, return_code=0, stderr=""
        )
        assert dcb.get_pfc(interface_name="eth4", tool_name="dcbtool") == cmd_output

    def test_get_pfc_dcbnl(self, dcb):
        dcbnl_out = """DCBX Mode: \n\tDCB_CAP_DCBX_HOST \n\tDCB_CAP_DCBX_VER_IEEE \n\nETS Data:
        tc: 0 tsa: ets, bw: 40%\n\t up:  0\n\t up:  1\n\t up:  2\n\t up:  5\n\t up:  6\n\t up:  7
        tc: 1 tsa: ets, bw: 30%\n\t up:  3\ntc: 2 tsa: ets, bw: 30%\n\t up:  4\ntc: 3 tsa: strict
        tc: 4 tsa: strict\ntc: 5 tsa: strict\ntc: 6 tsa: strict\ntc: 7 tsa: strict\n\nPFC Data:
        \tpfc_cap: 8 pfc_enable: 0x18\n\nApps Table:\n\tselector: 1 priority: 3 protocol: 0x8914
        \tselector: 2 priority: 4 protocol: 0xcbc\n\tselector: 1 priority: 3 protocol: 0x8906\n
        """
        cmd_output = {"PFC": [False, False, False, True, True, False, False, False]}
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=dcbnl_out, return_code=0, stderr=""
        )
        assert dcb.get_pfc(interface_name="eth4", tool_name="dcbnl") == cmd_output

    def test_get_pfc_dcbtool_exception_pfc(self, dcb, mocker):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="pfcup: ", return_code=0, stderr=""
        )
        with pytest.raises(DcbExecutionError, match="No match found for PFC"):
            dcb.get_pfc(interface_name="eth4", tool_name="dcbtool")

    def test_get_pfc_dcbtool_exception_ets(self, dcb, mocker):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="pgid: ", return_code=0, stderr=""
        )
        with pytest.raises(DcbExecutionError, match="No match found for ETS"):
            dcb.get_ets(interface_name="eth4", tool_name="dcbtool")

    def test_verify_dcb(self, dcb, mocker):
        SAN_DCB_MAP = {
            "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            },
            "LOCAL_PFC": [False, False, False, True, True, False, False, False],
            "LOCAL_APP": {"3260": {"Priority": 4, "Protocol": "TCP"}},
        }
        dcb.get_dcb = mocker.Mock()
        dcb.verify_ets = mocker.Mock()
        dcb.verify_pfc = mocker.Mock()
        dcb.verify_app = mocker.Mock()
        dcb._retry_logic = mocker.Mock()
        dcb.get_dcb.return_value = SAN_DCB_MAP
        dcb.verify_ets.return_value = True
        dcb.verify_pfc.return_value = True
        dcb.verify_app.return_value = True
        assert dcb.verify_dcb("interface_name", SAN_DCB_MAP)
        dcb.verify_ets.assert_called_with("interface_name", SAN_DCB_MAP, ets_config=SAN_DCB_MAP.get("LOCAL_ETS"))
        dcb.verify_pfc.assert_called_with("interface_name", SAN_DCB_MAP, pfc_config=SAN_DCB_MAP.get("LOCAL_PFC"))
        dcb.verify_app.assert_called_with("interface_name", SAN_DCB_MAP, app_config=SAN_DCB_MAP.get("LOCAL_APP", {}))

    def test_verify_dcb_exception(self, dcb, mocker):
        dcb_map = {"LOCAL_ETS": {}, "LOCAL_PFC": {}, "LOCAL_APP": {}}
        with pytest.raises(DcbExecutionError):
            dcb.verify_dcb("eth0", dcb_map)

    def test_retry_logic(self, dcb, mocker):
        switch = mocker.Mock()
        switch_port = "Te 1/25"
        interval = 5
        retries_left = 3
        with patch.object(dcb, "restart_lldpad") as mock_restart_lldpad:
            with patch("time.sleep") as mock_sleep:
                dcb._retry_logic(switch, switch_port, interval, retries_left)
                mock_restart_lldpad.assert_called_once()
                switch.shutdown.assert_called_with(False, switch_port)
                mock_sleep.assert_called_with(5)
                assert mock_sleep.call_count == 3

    def test_verify_ets(self, dcb, mocker):
        interface_name_mock = "eth0"
        dcb_map_mock = {
            "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            }
        }
        ets_config_mock = {
            "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
            "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
            "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
        }
        # Call the verify_ets method
        assert dcb.verify_ets(interface_name_mock, dcb_map_mock, ets_config_mock)

    def test_verify_ets_negative(self, dcb, mocker):
        interface_name_mock = "eth0"
        dcb_map_mock = {
            "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            }
        }
        ets_config_mock = {
            "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
            "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
        }
        # Call the verify_ets method
        assert not dcb.verify_ets(interface_name_mock, dcb_map_mock, ets_config_mock)

    def test_verify_pfc(self, dcb, mocker):
        interface_name_mock = "eth0"
        dcb_map_mock = {"LOCAL_PFC": [False, False, False, True, True, False, False, False]}
        pfc_config_mock = {0: False, 1: False, 2: False, 3: True, 4: True, 5: False, 6: False, 7: False}
        # Call the verify_pfc method
        assert dcb.verify_pfc(interface_name_mock, dcb_map_mock, pfc_config_mock)

    def test_verify_pfc_negative(self, dcb, mocker):
        interface_name_mock = "eth0"
        dcb_map_mock = {"LOCAL_PFC": [False, False, False, True, True, False, False, False]}
        pfc_config_mock = {
            0: False,
            1: False,
            2: False,
            3: True,
            4: False,  # Incorrect PFC configuration
            5: False,
            6: False,
            7: False,
        }
        # Call the verify_pfc method
        assert not dcb.verify_pfc(interface_name_mock, dcb_map_mock, pfc_config_mock)

    def test_verify_app(self, dcb, mocker):
        interface_name_mock = "eth0"
        dcb_map_mock = {
            "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            },
            "LOCAL_PFC": [False, False, False, True, True, False, False, False],
            "LOCAL_APP": {"Priority": 4, "Protocol": "TCP"},
        }
        # Mock the verify_app method
        dcb.get_app = mocker.Mock()
        dcb.get_app.return_value = {"LOCAL_APP": {"3260": {"Priority": 4, "Protocol": "TCP"}}}
        assert dcb.verify_app(interface_name_mock, dcb_map_mock)

    def test_verify_app_negative(self, dcb, mocker):
        interface_name_mock = "eth0"

        dcb_map_mock = {
            "LOCAL_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            },
            "LOCAL_PFC": [False, False, False, True, True, False, False, False],
            "LOCAL_APP": {"Priority": 5, "Protocol": "UDP"},
        }
        # Mock the verify_app method
        dcb.get_app = mocker.Mock()
        dcb.get_app.return_value = {"LOCAL_APP": {"3260": {"Priority": 4, "Protocol": "TCP"}}}
        return_value = dcb.verify_app(interface_name_mock, dcb_map_mock)
        assert not return_value
