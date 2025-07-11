# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Tests for `mfd_dcb` package."""

from textwrap import dedent

import re
import pytest
from mfd_connect import RPyCConnection
from mfd_connect.base import ConnectionCompletedProcess
from mfd_typing import OSName, DeviceID
from mfd_win_registry import WindowsRegistry

from mfd_dcb.windows import WindowsDcb
from mfd_dcb.exceptions import DcbConnectedOSNotSupported, DcbExecutionError, DcbException


class TestMfdDcb:
    def test_pass(self):
        assert True

    @pytest.fixture()
    def dcb(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.WINDOWS
        mocker.patch("mfd_dcb.windows.WindowsRegistry", return_value=mocker.Mock())
        mocker.create_autospec(WindowsRegistry)
        dcb_obj = WindowsDcb(connection=conn)
        mocker.stopall()
        return dcb_obj

    def test_constructor_returns_windows_instance(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.WINDOWS
        assert re.search("WindowsDcb", str(WindowsDcb(connection=conn)))

    def test_windows(self, mocker, dcb):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.WINDOWS
        assert isinstance(dcb.__new__(WindowsDcb, connection=conn), WindowsDcb)

    def test_unsupported_os(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.EFISHELL
        with pytest.raises(DcbConnectedOSNotSupported):
            WindowsDcb(connection=conn)

    def test_is_willing(self, dcb):
        output = dedent(
            r"""
        Willing
        -------
        True
        """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetQosDcbxSetting | select Willing", stdout=output, return_code=0, stderr=""
        )
        assert dcb.is_willing() is True

    def test_is_willing_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.is_willing()

    def test_set_willing(self, dcb):
        output = dedent("")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Set-NetQosDcbxSetting -Willing 0 -Confirm:$false", stdout=output, return_code=0, stderr=""
        )
        dcb.set_willing(enable=False, is_40g_or_later=True)
        dcb._connection.execute_powershell.assert_called_with("Set-NetQosDcbxSetting -Willing 0 -Confirm:$false")

    def test_is_willing_after_set_willing(self, dcb):
        output = dedent(
            r"""
        Willing
        -------
        False
        """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetQosDcbxSetting | select Willing", stdout=output, return_code=0, stderr=""
        )
        assert dcb.is_willing() is False

    def test_set_willing_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_willing(enable=False, is_40g_or_later=True)

    def test_set_policy(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_policy(
            "test1",
            1,
            "-IPSrcPrefixMatchCondition 10.10.10.10 -IPDstPortStartMatchCondition 5001 \
-IPDstPortEndMatchCondition 5001",
        )
        dcb._connection.execute_powershell.assert_called_with(
            'New-NetQosPolicy -Name "test1" -PriorityValue8021Action 1 -IPSrcPrefixMatchCondition 10.10.10.10 '
            "-IPDstPortStartMatchCondition 5001 -IPDstPortEndMatchCondition 5001 -Confirm:$false"
        )

    def test_set_policy_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_policy(
                "test1",
                1,
                "-IPSrcPrefixMatchCondition 10.10.10.10 -IPDstPortStartMatchCondition 5001 \
                        -IPDstPortEndMatchCondition 5001",
            )

    def test_get_policies(self, dcb):
        output = {
            "test1": {
                "Owner": "Group Policy (Machine)",
                "NetworkProfile": "All",
                "Precedence": "127",
                "JobObject": "",
                "IPProtocol": "Both",
                "IPSrcPrefix": "10.10.10.10",
                "IPDstPortStart": "5001",
                "IPDstPortEnd": "5001",
                "PriorityValue": "1",
            }
        }
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetQosPolicy",
            stdout="\n\nName           : test1\nOwner          : Group Policy (Machine)\nNetworkProfile : All\n\
                    Precedence     : 127\nJobObject      : \nIPProtocol     : Both\nIPSrcPrefix    : 10.10.10.10\n\
                    IPDstPortStart : 5001\nIPDstPortEnd   : 5001\nPriorityValue  : 1\n\n\n\n",
            return_code=0,
            stderr="",
        )
        assert dcb.get_policies() == output

    def test_remove_policy(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Remove-NetQosPolicy -Name '{name}' -Confirm:$false", stdout="", return_code=0, stderr=""
        )
        dcb.remove_policy("test1")
        dcb._connection.execute_powershell.assert_called_with('Remove-NetQosPolicy -Name "test1" -Confirm:$false')

    def test_remove_policy_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="Remove-NetQosPolicy -Name '{name}' -Confirm:$false",
            stdout="",
            return_code=0,
            stderr="Error while executing windows command",
        )
        with pytest.raises(DcbExecutionError):
            dcb.remove_policy("test1")

    def test_get_policies_after_remove_policy(self, dcb):
        output = {}
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetQosPolicy", stdout="", return_code=0, stderr=""
        )
        assert dcb.get_policies() == output

    def test_get_policies_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="Get-NetQosPolicy", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.get_policies()

    def test_verify_policy(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetQosPolicy",
            stdout="\n\nName           : test1\nOwner          : Group Policy (Machine)\nNetworkProfile : All\n\
                    Precedence     : 127\nJobObject      : \nIPProtocol     : Both\nIPSrcPrefix    : 10.10.10.10\n\
                    IPDstPortStart : 5001\nIPDstPortEnd   : 5001\nPriorityValue  : 1\n\n\n\n",
            return_code=0,
            stderr="",
        )
        assert dcb.verify_policy({"test1": {"PriorityValue": "1"}}) is True

    def test_verify_policy_negative_case(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetQosPolicy",
            stdout="\n\nName           : test1\nOwner          : Group Policy (Machine)\nNetworkProfile : All\n\
                    Precedence     : 127\nJobObject      : \nIPProtocol     : Both\nIPSrcPrefix    : 10.10.10.10\n\
                    IPDstPortStart : 5001\nIPDstPortEnd   : 5001\nPriorityValue  : 1\n\n\n\n",
            return_code=0,
            stderr="",
        )
        assert dcb.verify_policy({"test1": {"PriorityValue": "10"}}) is False

    def test_verify_policy_error_in_output(self, dcb):
        expected_output = {
            "test1": {
                "Owner": "Group Policy (Machine)",
                "NetworkProfile": "All",
                "Precedence": "127",
                "JobObject": "",
                "IPProtocol": "Both",
                "IPSrcPrefix": "10.10.10.10",
                "IPDstPortStart": "5001",
                "IPDstPortEnd": "5001",
                "PriorityValue": "1",
            }
        }
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.verify_policy(expected_output)

    def test_is_qos_enabled(self, dcb):
        output = dedent("Enabled : False")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetAdapterQos 'SLOT 4 Port 1'", stdout=output, return_code=0, stderr=""
        )
        assert dcb.is_qos_enabled("SLOT 4 Port 1") is False

    def test_set_qos(self, dcb):
        output = dedent("Enabled : True")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        dcb.set_qos("SLOT 4 Port 1", True)
        dcb._connection.execute_powershell.assert_called_with('Enable-NetAdapterQos "SLOT 4 Port 1" -Confirm:$false')

    def test_set_qos_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_qos("SLOT 4 Port 1", True)

    def test_is_qos_enabled_after_enable_qos(self, dcb):
        output = dedent("Enabled : True")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Get-NetAdapterQos 'SLOT 4 Port 1'", stdout=output, return_code=0, stderr=""
        )
        assert dcb.is_qos_enabled("SLOT 4 Port 1") is True

    def test_set_default_config(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="Remove-NetQosPolicy -Confirm:$false", stdout="", return_code=0, stderr=""
        )
        dcb.set_default_config()
        dcb._connection.execute_powershell.assert_called_with(
            "Disable-NetQosFlowControl -Priority 0,1,2,3,4,5,6,7 -Confirm:$false"
        )

    def test_set_default_config_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_default_config()

    def test_set_pfc(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_pfc([1, 1, 1, 1, 1, 1, 1, 1])
        dcb._connection.execute_powershell.assert_called_with(
            "Enable-NetQosFlowControl -Priority 0,1,2,3,4,5,6,7 -Confirm:$false"
        )

    def test_set_pfc_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_pfc([1, 1, 1, 1, 1, 1, 1, 1])

    def test_set_pfc_invalid_input_list_length(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(ValueError):
            dcb.set_pfc([1, 1, 1, 1, 1, 1, 1])

    def test_get_pfc(self, dcb):
        output = dedent("OperationalFlowControl     : All Priorities Enabled")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_pfc("SLOT 4 Port 1") == {"PFC": [True, True, True, True, True, True, True, True]}

    def test_set_ets(self, dcb, mocker):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_ets(["0", "1", "2", "3", "4", "5", "6", "7"], [0, 5, 7, 10, 15, 17, 20, 23])
        dcb._connection.execute_powershell.assert_has_calls(
            [
                mocker.call("New-NetQosTrafficClass -Name 'TC1' -priority 1 -BandwidthPercentage 5 -Algorithm ETS"),
                mocker.call("New-NetQosTrafficClass -Name 'TC2' -priority 2 -BandwidthPercentage 7 -Algorithm ETS"),
                mocker.call("New-NetQosTrafficClass -Name 'TC3' -priority 3 -BandwidthPercentage 10 -Algorithm ETS"),
                mocker.call("New-NetQosTrafficClass -Name 'TC4' -priority 4 -BandwidthPercentage 15 -Algorithm ETS"),
                mocker.call("New-NetQosTrafficClass -Name 'TC5' -priority 5 -BandwidthPercentage 17 -Algorithm ETS"),
                mocker.call("New-NetQosTrafficClass -Name 'TC6' -priority 6 -BandwidthPercentage 20 -Algorithm ETS"),
                mocker.call("New-NetQosTrafficClass -Name 'TC7' -priority 7 -BandwidthPercentage 23 -Algorithm ETS"),
            ]
        )

    def test_set_ets_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_ets(["1", "2", "3", "4", "5", "6", "7"], [5, 7, 10, 15, 17, 20, 23])

    def test_set_ets_invalid_input_list_length(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(ValueError):
            dcb.set_ets(["1"], [5])

    def test_set_ets_inputs_with_different_list_length(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(ValueError):
            dcb.set_ets([], [1])

    def test_get_ets(self, dcb):
        output = dedent(
            r"""
                OperationalTrafficClasses  : TC TSA    Bandwidth Priorities
                                             -- ---    --------- ----------
                                              0 ETS    100%      0-7
                """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_ets("SLOT 4 Port 1") == {
            "ETS": {"0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": [0, 1, 2, 3, 4, 5, 6, 7]}}
        }

    def test_get_app(self, dcb):
        output = dedent(
            r"""
                OperationalClassifications : Protocol  Port/Type Priority
                                             --------  --------- --------
                                             Ethertype 0x8906    3
                                             TCP       3260      4
                """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_app("SLOT 4 Port 1") == {
            "APP": {"0x8906": {"Priority": 3, "Protocol": "Ethertype"}, "3260": {"Priority": 4, "Protocol": "TCP"}}
        }

    def test_get_remote_ets(self, dcb):
        output = dedent(
            r"""
                RemoteTrafficClasses       : TC TSA    Bandwidth Priorities
                                             -- ---    --------- ----------
                                              0 ETS    40%       0-2,5-7
                                              1 ETS    30%       3
                                              2 ETS    30%       4
                """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_remote_ets("SLOT 4 Port 1") == {
            "Remote_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            }
        }

    def test_get_remote_pfc(self, dcb):
        output = dedent("RemoteFlowControl          : Priorities 3-4 Enabled")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_remote_pfc("SLOT 4 Port 1") == {
            "Remote_PFC": [False, False, False, True, True, False, False, False]
        }

    def test_get_remote_app(self, dcb):
        output = dedent(
            r"""
                RemoteClassifications      : Protocol  Port/Type Priority
                                             --------  --------- --------
                                             Ethertype 0x8906    3
                                             TCP       3260      4
               """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_remote_app("SLOT 4 Port 1") == {
            "Remote_APP": {
                "0x8906": {"Priority": 3, "Protocol": "Ethertype"},
                "3260": {"Priority": 4, "Protocol": "TCP"},
            }
        }

    def test_get_dcb(self, dcb):
        output = dedent(
            """
Name                       : SLOT 4 Port 1
Enabled                    : True
Capabilities               :                       Hardware     Current
                                                   --------     -------
                             MacSecBypass        : NotSupported NotSupported
                             DcbxSupport         : CEE, IEEE    CEE, IEEE
                             NumTCs(Max/ETS/PFC) : 8/8/8        8/8/8

OperationalTrafficClasses  : TC TSA    Bandwidth Priorities
                             -- ---    --------- ----------
                              0 ETS    100%      0-7

OperationalFlowControl     : All Priorities Enabled
OperationalClassifications : Protocol  Port/Type Priority
                             --------  --------- --------
                             Ethertype 0x8906    3
                             TCP       3260      4

RemoteTrafficClasses       : TC TSA    Bandwidth Priorities
                             -- ---    --------- ----------
                              0 ETS    40%       0-2,5-7
                              1 ETS    30%       3
                              2 ETS    30%       4

RemoteFlowControl          : Priorities 3-4 Enabled
RemoteClassifications      : Protocol  Port/Type Priority
                             --------  --------- --------
                             Ethertype 0x8906    3
                             TCP       3260      4
               """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_dcb("SLOT 4 Port 1") == {
            "ETS": {"0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": [0, 1, 2, 3, 4, 5, 6, 7]}},
            "PFC": [True, True, True, True, True, True, True, True],
            "APP": {"0x8906": {"Priority": 3, "Protocol": "Ethertype"}, "3260": {"Priority": 4, "Protocol": "TCP"}},
            "Remote_ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 40, "Priorities": [0, 1, 2, 5, 6, 7]},
                "1": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]},
                "2": {"TSA": "ETS", "Bandwidth": 30, "Priorities": [4]},
            },
            "Remote_PFC": [False, False, False, True, True, False, False, False],
            "Remote_APP": {
                "0x8906": {"Priority": 3, "Protocol": "Ethertype"},
                "3260": {"Priority": 4, "Protocol": "TCP"},
            },
        }

    def test_set_dcb_operational_value(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_dcb_operational_value("Intel(R) Ethernet Network Adapter E810-C-Q2", "DCB", "Enabled")
        dcb._connection.execute_powershell.assert_called_with(
            "Set-IntelNetAdapterSetting -Name 'Intel(R) Ethernet Network Adapter E810-C-Q2' \
-DisplayName 'DCB' -DisplayValue 'Enabled'"
        )

    def test_set_dcb_operational_value_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_dcb_operational_value("Intel(R) Ethernet Network Adapter E810-C-Q2", "DCB", "Enabled")

    def test_get_dcb_operational_value(self, dcb):
        output = dedent("IEEE 802.1Qaz")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_dcb_operational_value("Intel(R) Ethernet Network Adapter E810-C-Q2", "DCB Version") == output

    def test_get_dcb_operational_value_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.get_dcb_operational_value("Intel(R) Ethernet Network Adapter E810-C-Q2", "DCB Version")

    def test_verify_dcb(self, dcb):
        output = dedent(
            r"""
                OperationalTrafficClasses  : TC TSA    Bandwidth Priorities
                                             -- ---    --------- ----------
                                              0 ETS    100%      0-7
                OperationalFlowControl     : All Priorities Enabled
                OperationalClassifications : Protocol  Port/Type Priority
                                             --------  --------- --------
                                             Ethertype 0x8906    3
                                             TCP       3260      4
            """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout=output,
            return_code=0,
            stderr="",
        )
        assert (
            dcb.verify_dcb(
                "SLOT 4 Port 1",
                {
                    "ETS": {"0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": [0, 1, 2, 3, 4, 5, 6, 7]}},
                    "PFC": [True, True, True, True, True, True, True, True],
                    "APP": {
                        "0x8906": {"Priority": 3, "Protocol": "Ethertype"},
                        "3260": {"Priority": 4, "Protocol": "TCP"},
                    },
                },
            )
            is True
        )

    def test_verify_ets(self, dcb):
        output = dedent(
            r"""
                OperationalTrafficClasses  : TC TSA    Bandwidth Priorities
                                             -- ---    --------- ----------
                                              0 ETS    100%      0-7
                """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout=output,
            return_code=0,
            stderr="",
        )
        assert (
            dcb.verify_ets(
                "SLOT 4 Port 1",
                {"ETS": {"0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": [0, 1, 2, 3, 4, 5, 6, 7]}}},
            )
            is True
        )
        dcb._connection.execute_powershell.assert_called_with(
            'Get-NetAdapterQos "SLOT 4 Port 1"', expected_return_codes=[0]
        )

    def test_verify_ets_negative_case(self, dcb):
        output = dedent(
            r"""
                OperationalTrafficClasses  : TC TSA    Bandwidth Priorities
                                             -- ---    --------- ----------
                                              0 ETS    100%      0-7
                """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout=output,
            return_code=0,
            stderr="",
        )
        assert (
            dcb.verify_ets(
                "SLOT 4 Port 1",
                {"ETS": {"0": {"TSA": "ETS", "Bandwidth": 1000, "Priorities": [0, 1, 2, 3, 4, 5, 6, 7]}}},
            )
            is False
        )

    def test_verify_pfc(self, dcb):
        output = dedent("OperationalFlowControl     : All Priorities Enabled")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout=output,
            return_code=0,
            stderr="",
        )
        assert dcb.verify_pfc("SLOT 4 Port 1", {"PFC": [True, True, True, True, True, True, True, True]}) is True
        dcb._connection.execute_powershell.assert_called_with(
            'Get-NetAdapterQos "SLOT 4 Port 1"', expected_return_codes=[0]
        )

    def test_verify_pfc_negative_case(self, dcb):
        output = dedent("OperationalFlowControl     : All Priorities Enabled")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout=output,
            return_code=0,
            stderr="",
        )
        assert dcb.verify_pfc("SLOT 4 Port 1", {"PFC": [True, False, True, False, True, False, True, False]}) is False

    def test_verify_app(self, dcb):
        output = dedent(
            r"""
                OperationalClassifications : Protocol  Port/Type Priority
                                             --------  --------- --------
                                             Ethertype 0x8906    3
                                             TCP       3260      4
                """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout=output,
            return_code=0,
            stderr="",
        )
        assert (
            dcb.verify_app(
                "SLOT 4 Port 1",
                {
                    "APP": {
                        "0x8906": {"Priority": 3, "Protocol": "Ethertype"},
                        "3260": {"Priority": 4, "Protocol": "TCP"},
                    }
                },
            )
            is True
        )
        dcb._connection.execute_powershell.assert_called_with(
            'Get-NetAdapterQos "SLOT 4 Port 1"', expected_return_codes=[0]
        )

    def test_verify_app_negative_case(self, dcb):
        output = dedent(
            r"""
                OperationalClassifications : Protocol  Port/Type Priority
                                             --------  --------- --------
                                             Ethertype 0x8906    3
                                             TCP       3260      4
                """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout=output,
            return_code=0,
            stderr="",
        )
        assert (
            dcb.verify_app(
                "SLOT 4 Port 1",
                {
                    "APP": {
                        "0x8906": {"Priority": 3, "Protocol": "Ethertype"},
                        "3260": {"Priority": 34, "Protocol": "TCP"},
                    }
                },
            )
            is False
        )

    def test_pfc_bool_to_str(self, dcb):
        output = dedent("enabled")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout="",
            return_code=0,
            stderr="",
        )
        assert dcb.pfc_bool_to_str(True) == output

    def test_pfc_bool_to_str_negative_case(self, dcb):
        output = dedent("disabled")
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="",
            stdout="",
            return_code=0,
            stderr="",
        )
        assert dcb.pfc_bool_to_str(True) != output

    def test_remove_dcb_all_user_priorities(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.remove_dcb_all_user_priorities()
        dcb._connection.execute_powershell.assert_called_with("Remove-NetQosPolicy -Confirm:$false")

    def test_remove_dcb_all_user_priorities_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while removing QoS Policies"
        )
        with pytest.raises(DcbExecutionError):
            dcb.remove_dcb_all_user_priorities()

    def test_get_all_dcb_operational_values(self, dcb):
        output = dedent(
            """
            [
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "DCB",
                "DisplayValue":  "Disabled"
            },
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "DCB Status",
                "DisplayValue":  "Non Operational - No Peer"
            },
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "iSCSI Status",
                "DisplayValue":  "Disabled"
            },
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "DCB Priority Flow Control",
                "DisplayValue":  "Disabled"
            },
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "DCB Priority Group",
                "DisplayValue":  "Disabled"
            },
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "DCB Version",
                "DisplayValue":  "IEEE 802.1Qaz"
            },
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "DCB Bandwidth Percentages",
                "DisplayValue":  [
                                     "13",
                                     "13",
                                     "13",
                                     "13",
                                     "12",
                                     "12",
                                     "12",
                                     "12"
                                 ]
            },
            {
                "Name":  "Intel(R) Ethernet Network Adapter E810-C-Q2",
                "DisplayName":  "DCB User Priorities",
                "DisplayValue":  [
                                     "1",
                                     "2",
                                     "4",
                                     "8",
                                     "16",
                                     "32",
                                     "64",
                                     "128"
                                 ]
            }
            ]"""
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_all_dcb_operational_values("Intel(R) Ethernet Network Adapter E810-C-Q2") == {
            "DCB": "Disabled",
            "DCB Status": "Non Operational - No Peer",
            "iSCSI Status": "Disabled",
            "DCB Priority Flow Control": "Disabled",
            "DCB Priority Group": "Disabled",
            "DCB Version": "IEEE 802.1Qaz",
            "DCB Bandwidth Percentages": ["13", "13", "13", "13", "12", "12", "12", "12"],
            "DCB User Priorities": ["1", "2", "4", "8", "16", "32", "64", "128"],
        }
        dcb._connection.execute_powershell.assert_called_with(
            "Get-IntelNetAdapterStatus -Name 'Intel(R) Ethernet Network Adapter E810-C-Q2' "
            "-Status DCB | ConvertTo-json",
            expected_return_codes={0},
        )

    def test_get_all_dcb_operational_values_empty_output(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(RuntimeError):
            dcb.get_all_dcb_operational_values("Intel(R) Ethernet Network Adapter E810-C-Q2")

    def test_get_all_dcb_operational_values_error_in_output(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.get_all_dcb_operational_values("Intel(R) Ethernet Network Adapter E810-C-Q2")

    def test_get_dcb_status(self, dcb):
        output = "Enabled"
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.get_dcb_status("Intel(R) Ethernet Network Adapter E810-C-Q2") == (True, False)
        dcb._connection.execute_powershell.assert_called_with("(get-Netqosdcbxsetting).Willing")

    def test_get_dcb_status_error_in_output(self, dcb):
        output = "Enabled"
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr="Unable to retrieve DCB operational value"
        )
        with pytest.raises(DcbExecutionError):
            dcb.get_dcb_status("Intel(R) Ethernet Network Adapter E810-C-Q2")

    def test_get_dcb_status_invalid_dcb_oper_value(self, dcb):
        output = "enabled"
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        with pytest.raises(ValueError):
            dcb.get_dcb_status("Intel(R) Ethernet Network Adapter E810-C-Q2")

    def test_set_dcb_status(self, dcb):
        output = "false"
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert (
            dcb.set_dcb_status(
                "Intel(R) Ethernet Network Adapter E810-C-Q2", enable_dcb=False, enable_willing_mode=False
            )
            is True
        )
        dcb._connection.execute_powershell.assert_called_with(
            'Set-Intelnetadaptersetting -DisplayName "DCB" -DisplayValue "Disabled" '
            '-Name "Intel(R) Ethernet Network Adapter E810-C-Q2"'
        )

    def test_set_dcb_status_error_in_output(self, dcb):
        output = "Enabled"
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr="There is no DCB operation value could find."
        )
        with pytest.raises(DcbExecutionError):
            dcb.set_dcb_status(
                "Intel(R) Ethernet Network Adapter E810-C-Q2", enable_dcb=False, enable_willing_mode=False
            )

    def test_set_dcb_status_mode_not_set(self, dcb):
        output = "True"
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        with pytest.raises(DcbException):
            dcb.set_dcb_status(
                "Intel(R) Ethernet Network Adapter E810-C-Q2", enable_dcb=False, enable_willing_mode=False
            )

    def test_is_debugps_ready(self, dcb):
        output = dedent(
            """
            Port                                                 Etrack ID    FW     Build   API
            ----                                                 ---------    --     -----   ---
            Intel(R) Ethernet Network Adapter E810-C-Q2          0x80018E17   7.3    1738... 1.7
            Intel(R) Ethernet Network Adapter E810-C-Q2 #2       0x80018E17   7.3    1738... 1.7
            """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb.is_debugps_ready() is True
        dcb._connection.execute_powershell.assert_called_with("get-dpsver", expected_return_codes={})

    def test_is_debugps_ready_unexpected_return_code(self, dcb):
        output = dedent(
            """
            Port                                                 Etrack ID    FW     Build   API
            ----                                                 ---------    --     -----   ---
            Intel(R) Ethernet Network Adapter E810-C-Q2          0x80018E17   7.3    1738... 1.7
            Intel(R) Ethernet Network Adapter E810-C-Q2 #2       0x80018E17   7.3    1738... 1.7
            """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=1, stderr=""
        )
        assert dcb.is_debugps_ready() is False
        dcb._connection.execute_powershell.assert_called_with("get-dpsver", expected_return_codes={})

    def test_is_debugps_ready_warning_in_output(self, dcb):
        output = dedent(
            """
            Port                                                 Etrack ID    FW     Build   API
            ----                                                 ---------    --     -----   ---
            Intel(R) Ethernet Network Adapter E810-C-Q2          0x80018E17   7.3    1738... 1.7
            Intel(R) Ethernet Network Adapter E810-C-Q2 #2       0x80018E17   7.3    1738... 1.7
            """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=1, stderr=""
        )
        assert dcb.is_debugps_ready() is False
        dcb._connection.execute_powershell.assert_called_with("get-dpsver", expected_return_codes={})

    def test_is_debugps_ready_error_in_output(self, dcb):
        output = dedent(
            """
            Port                                                 Etrack ID    FW     Build   API
            ----                                                 ---------    --     -----   ---
            Intel(R) Ethernet Network Adapter E810-C-Q2          0x80018E17   7.3    1738... 1.7
            Intel(R) Ethernet Network Adapter E810-C-Q2 #2       0x80018E17   7.3    1738... 1.7
            """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=1, stderr=""
        )
        assert dcb.is_debugps_ready() is False
        dcb._connection.execute_powershell.assert_called_with("get-dpsver", expected_return_codes={})

    def test_is_debugps_ready_not_recognized_in_output(self, dcb):
        output = dedent(
            """
            Port                                                 Etrack ID    FW     Build   API
            ----                                                 ---------    --     -----   ---
            Intel(R) Ethernet Network Adapter E810-C-Q2          0x80018E17   7.3    1738... 1.7
            Intel(R) Ethernet Network Adapter E810-C-Q2 #2       0x80018E17   7.3    1738... 1.7
            """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=1, stderr=""
        )
        assert dcb.is_debugps_ready() is False
        dcb._connection.execute_powershell.assert_called_with("get-dpsver", expected_return_codes={})

    def test_get_pfc_enabled_bits_by_dps(self, dcb):
        output = dedent(
            """False
            False
            False
            False
            False
            False
            False
            False"""
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb._get_pfc_enabled_bits_by_dps("Intel(R) Ethernet Network Adapter E810-C-Q2") == [
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
        ]
        dcb._connection.execute_powershell.assert_called_with(
            "(get-dpsdcb | ?{$_.PortName -eq 'Intel(R) Ethernet Network Adapter E810-C-Q2'})."
            "LocalConfig.Pfc.PfcEnableBits"
        )

    def test_get_pfc_enabled_bits_by_dps_invalid_pfc_type(self, dcb):
        output = dedent(
            """False
            False
            False
            False
            False
            False
            False
            False"""
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        with pytest.raises(ValueError):
            dcb._get_pfc_enabled_bits_by_dps("Intel(R) Ethernet Network Adapter E810-C-Q2", "private")

    def test_get_remote_pfc_enabled_bits_by_pscmd(self, dcb):
        output = dedent(
            """
            Name         : SLOT 4 Port 1
            Enabled      : False
            Capabilities :                       Hardware     Current
                                                 --------     -------
                           MacSecBypass        : NotSupported NotSupported
                           DcbxSupport         : CEE, IEEE    None
                           NumTCs(Max/ETS/PFC) : 8/8/8        0/0/0
        """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb._get_remote_pfc_enabled_bits_by_pscmd("SLOT 4 Port 1") == [
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
        ]
        dcb._connection.execute_powershell.assert_called_with(
            'Get-NetAdapterQos -Name "SLOT 4 Port 1"', expected_return_codes={}
        )

    def test_get_remote_pfc_enabled_bits_by_pscmd_unexpected_return_code(self, dcb):
        output = dedent(
            """
            Name         : SLOT 4 Port 1
            Enabled      : False
            Capabilities :                       Hardware     Current
                                                 --------     -------
                           MacSecBypass        : NotSupported NotSupported
                           DcbxSupport         : CEE, IEEE    None
                           NumTCs(Max/ETS/PFC) : 8/8/8        0/0/0
        """
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=1, stderr=""
        )
        with pytest.raises(DcbExecutionError):
            dcb._get_remote_pfc_enabled_bits_by_pscmd("SLOT 4 Port 1")
        dcb._connection.execute_powershell.assert_called_with(
            'Get-NetAdapterQos -Name "SLOT 4 Port 1"', expected_return_codes={}
        )

    def test_get_local_pfc_enabled_bits_by_pscmd(self, dcb):
        output = dedent(
            "\nEnabled\n-------\n  False\n  False\n  False\n  False\n  False\n  False\n  False\n  False\n\n\n"
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=0, stderr=""
        )
        assert dcb._get_local_pfc_enabled_bits_by_pscmd() == [
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
            "False",
        ]
        dcb._connection.execute_powershell.assert_called_with(
            "Get-NetQosFlowControl | select Enabled", expected_return_codes={}
        )

    def test_get_local_pfc_enabled_bits_by_pscmd_unexpected_return_code(self, dcb):
        output = dedent(
            "\nEnabled\n-------\n  False\n  False\n  False\n  False\n  False\n  False\n  False\n  False\n\n\n"
        )
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout=output, return_code=1, stderr=""
        )
        with pytest.raises(DcbExecutionError):
            dcb._get_local_pfc_enabled_bits_by_pscmd()
        dcb._connection.execute_powershell.assert_called_with(
            "Get-NetQosFlowControl | select Enabled", expected_return_codes={}
        )

    def test_get_local_pfc_enabled_bits_by_pscmd_empty_output(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        assert dcb._get_local_pfc_enabled_bits_by_pscmd() is None
        dcb._connection.execute_powershell.assert_called_with(
            "Get-NetQosFlowControl | select Enabled", expected_return_codes={}
        )

    def test_get_pfc_counters_error_in_output(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.get_pfc_counters("Intel(R) Ethernet Network Adapter E810-C-Q2")

    def test_get_pfc_counters_empty_output(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(RuntimeError):
            dcb.get_pfc_counters("Intel(R) Ethernet Network Adapter E810-C-Q2")
        dcb._connection.execute_powershell.assert_called_with(
            "(get-dpspfc | ?{$_.PortName -eq 'Intel(R) Ethernet Network Adapter E810-C-Q2'}) | convertto-json",
            expected_return_codes={},
        )

    def test_get_pfc_port_statistics_invalid_priority_input(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(ValueError):
            dcb.get_pfc_port_statistics("Intel(R) Ethernet Network Adapter E810-C-Q2", 10)

    def test_get_pfc_port_statistics_error_in_output(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(DcbExecutionError):
            dcb.get_pfc_port_statistics("Intel(R) Ethernet Network Adapter E810-C-Q2", 7)

    def test_get_pfc_port_statistics_empty_output(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        with pytest.raises(RuntimeError):
            dcb.get_pfc_port_statistics("Intel(R) Ethernet Network Adapter E810-C-Q2", 7)

    def test_set_dcb_user_priority_to_tcp_port(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_dcb_user_priority_to_tcp_port("10.10.10.10")
        dcb._connection.execute_powershell.assert_called_with(
            'New-NetQosPolicy -Name "Prio1 BW" -PriorityValue8021Action 1 -IPSrcPrefixMatchCondition 10.10.10.10 '
            "-IPDstPortStartMatchCondition 5000 -IPDstPortEndMatchCondition 5000",
            expected_return_codes={},
        )

    def test_set_dcb_user_priority_to_tcp_port_with_nondefault_values(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        dcb.set_dcb_user_priority_to_tcp_port("10.10.10.10", 2, 5555)
        dcb._connection.execute_powershell.assert_called_with(
            'New-NetQosPolicy -Name "Prio2 BW" -PriorityValue8021Action 2 -IPSrcPrefixMatchCondition 10.10.10.10 '
            "-IPDstPortStartMatchCondition 5555 -IPDstPortEndMatchCondition 5555",
            expected_return_codes={},
        )

    def test_set_dcb_user_priority_to_tcp_port_error_in_code(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="Error while executing windows command"
        )
        with pytest.raises(RuntimeError):
            dcb.set_dcb_user_priority_to_tcp_port("10.10.10.10")

    def test_set_dcb_user_priority_to_tcp_port_invalid_return_code(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=1, stderr=""
        )
        with pytest.raises(RuntimeError):
            dcb.set_dcb_user_priority_to_tcp_port("10.10.10.10")

    def test_get_dcb_max_supported_traffic_class_40G_and_higher(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        assert dcb.get_dcb_max_supported_traffic_class(True, DeviceID(0x10FB)) == 8

    def test_get_dcb_max_supported_traffic_class_10G_Niantic_card(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        assert dcb.get_dcb_max_supported_traffic_class(False, DeviceID(0x10FB)) == 8

    def test_get_dcb_max_supported_traffic_class_lesser_than_40G(self, dcb):
        dcb._connection.execute_powershell.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        assert dcb.get_dcb_max_supported_traffic_class(False, DeviceID(0x10FA)) == 4

    def test_set_dcb(self, dcb):
        dcb.set_dcb(True, "SLOT 4 Port 1")
        dcb.winreg_obj.set_feature.assert_called_with("SLOT 4 Port 1", "*QOS", "1")

    def test_set_dcb_disable_scenario(self, dcb):
        dcb.set_dcb(False, "SLOT 4 Port 1")
        dcb.winreg_obj.set_feature.assert_called_with("SLOT 4 Port 1", "*QOS", "0")
