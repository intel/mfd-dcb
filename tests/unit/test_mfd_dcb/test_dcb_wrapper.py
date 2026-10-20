# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: MIT

"""Tests for `mfd_dcb.dcb_wrapper` module."""

from textwrap import dedent

import pytest
from mfd_connect import RPyCConnection
from mfd_connect.base import ConnectionCompletedProcess
from mfd_const.qos import LOCAL_ETS, LOCAL_PFC, LOCAL_APP

from mfd_dcb.dcb_wrapper import DcbCli
from mfd_dcb.exceptions import DcbExecutionError, DcbExecutionProcessError


class TestDcbCli:
    @pytest.fixture()
    def wrapper(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        return DcbCli("eth1", conn)

    def _out(self, stdout):
        return ConnectionCompletedProcess(args="", stdout=stdout, return_code=0, stderr="")

    def test_get_pfc(self, wrapper):
        stdout = dedent(
            """\
            pfc-cap 4 macsec-bypass off delay 1949
            prio-pfc 0:off 1:off 2:off 3:on 4:off 5:off 6:off 7:off
            """
        )
        wrapper._connection.execute_command.return_value = self._out(stdout)
        assert wrapper.get_pfc() == {LOCAL_PFC: [False, False, False, True, False, False, False, False]}

    def test_get_ets(self, wrapper):
        stdout = dedent(
            """\
            willing off ets-cap 4 cbs off
            tc-bw 0:40 1:40 2:10 3:10 4:0 5:0 6:0 7:0
            pg-bw 0:40 1:40 2:10 3:10 4:0 5:0 6:0 7:0
            tc-tsa 0:ets 1:ets 2:ets 3:ets 4:strict 5:strict 6:strict 7:strict
            prio-tc 0:0 1:1 2:2 3:3 4:0 5:0 6:0 7:0
            reco-tc-bw 0:40 1:40 2:10 3:10 4:0 5:0 6:0 7:0
            reco-tc-tsa 0:ets 1:ets 2:ets 3:ets 4:strict 5:strict 6:strict 7:strict
            reco-prio-tc 0:0 1:1 2:2 3:3 4:0 5:0 6:0 7:0
            """
        )
        wrapper._connection.execute_command.return_value = self._out(stdout)
        ets = wrapper.get_ets()[LOCAL_ETS]
        assert ets["0"] == {
            "TSA": "ETS",
            "Bandwidth": 40,
            "Priorities": [0, 4, 5, 6, 7],
        }
        assert ets["1"] == {"TSA": "ETS", "Bandwidth": 40, "Priorities": [1]}
        assert ets["2"] == {"TSA": "ETS", "Bandwidth": 10, "Priorities": [2]}
        assert ets["3"] == {"TSA": "ETS", "Bandwidth": 10, "Priorities": [3]}
        assert ets["4"] == {"TSA": "STRICT", "Bandwidth": 0, "Priorities": []}

    def test_get_ets_ignores_reco_only_fields(self, wrapper):
        stdout = dedent(
            """\
            willing off ets-cap 8 cbs off
            reco-tc-bw 0:40 1:60 2:0 3:0 4:0 5:0 6:0 7:0
            reco-tc-tsa 0:ets 1:ets 2:strict 3:strict 4:strict 5:strict 6:strict 7:strict
            reco-prio-tc 0:0 1:1 2:0 3:0 4:0 5:0 6:0 7:0
            """
        )
        wrapper._connection.execute_command.return_value = self._out(stdout)
        ets = wrapper.get_ets()[LOCAL_ETS]
        assert ets == {}

    def test_get_app(self, wrapper):
        stdout = "ethtype-prio 8906:3\ndscp-prio 26:3 30:3"
        wrapper._connection.execute_command.return_value = self._out(stdout)
        app = wrapper.get_app()[LOCAL_APP]
        assert app[0] == {"selector": "ethtype", "priority": 3, "protocol": "8906"}
        assert app[1] == {"selector": "dscp", "priority": 3, "protocol": "26"}
        assert app[2] == {"selector": "dscp", "priority": 3, "protocol": "30"}

    def test_get_app_repeated_protocol(self, wrapper):
        stdout = "dscp-prio 26:3 26:5"
        wrapper._connection.execute_command.return_value = self._out(stdout)
        app = wrapper.get_app()[LOCAL_APP]
        assert app == {
            0: {"selector": "dscp", "priority": 3, "protocol": "26"},
            1: {"selector": "dscp", "priority": 5, "protocol": "26"},
        }

    def test_get_app_mixed_port_selectors(self, wrapper):
        stdout = dedent(
            """\
            stream-port-prio 1234:4
            dgram-port-prio 5678:5
            port-prio 9999:6
            """
        )
        wrapper._connection.execute_command.return_value = self._out(stdout)
        app = wrapper.get_app()[LOCAL_APP]
        assert app == {
            0: {"selector": "stream-port", "priority": 4, "protocol": "1234"},
            1: {"selector": "dgram-port", "priority": 5, "protocol": "5678"},
            2: {"selector": "port", "priority": 6, "protocol": "9999"},
        }

    def test_get_app_default_prio(self, wrapper):
        stdout = "default-prio 1 3"
        wrapper._connection.execute_command.return_value = self._out(stdout)
        app = wrapper.get_app()[LOCAL_APP]
        assert app == {
            0: {"selector": "default", "priority": 1, "protocol": "0"},
            1: {"selector": "default", "priority": 3, "protocol": "0"},
        }

    def test_get_app_all_selectors(self, wrapper):
        stdout = dedent(
            """\
            ethtype-prio 8906:3
            default-prio 2
            dscp-prio 26:3 30:3
            stream-port-prio 1234:4
            dgram-port-prio 5678:5
            port-prio 9999:6
            pcp-prio 1:7
            """
        )
        wrapper._connection.execute_command.return_value = self._out(stdout)
        app = wrapper.get_app()[LOCAL_APP]
        assert app == {
            0: {"selector": "ethtype", "priority": 3, "protocol": "8906"},
            1: {"selector": "default", "priority": 2, "protocol": "0"},
            2: {"selector": "dscp", "priority": 3, "protocol": "26"},
            3: {"selector": "dscp", "priority": 3, "protocol": "30"},
            4: {"selector": "stream-port", "priority": 4, "protocol": "1234"},
            5: {"selector": "dgram-port", "priority": 5, "protocol": "5678"},
            6: {"selector": "port", "priority": 6, "protocol": "9999"},
            7: {"selector": "pcp", "priority": 7, "protocol": "1"},
        }

    def test_get_app_default_numeric(self, wrapper):
        stdout = "dscp-prio 22:3 24:3"
        wrapper._connection.execute_command.return_value = self._out(stdout)
        wrapper.get_app()
        command = wrapper._connection.execute_command.call_args.args[0]
        assert command == "dcb -N app show dev eth1"

    def test_get_app_names_opt_out(self, wrapper):
        stdout = "dscp-prio flash:3"
        wrapper._connection.execute_command.return_value = self._out(stdout)
        wrapper.get_app(numeric=False)
        command = wrapper._connection.execute_command.call_args.args[0]
        assert command == "dcb app show dev eth1"

    def test_get_dcb_merges(self, wrapper):
        ets_out = dedent(
            """\
            willing off ets-cap 4 cbs off
            tc-bw 0:70 1:30 2:0 3:0 4:0 5:0 6:0 7:0
            pg-bw 0:70 1:30 2:0 3:0 4:0 5:0 6:0 7:0
            tc-tsa 0:ets 1:ets 2:strict 3:strict 4:strict 5:strict 6:strict 7:strict
            prio-tc 0:0 1:0 2:0 3:1 4:0 5:0 6:0 7:0
            reco-tc-bw 0:70 1:30 2:0 3:0 4:0 5:0 6:0 7:0
            reco-tc-tsa 0:ets 1:ets 2:strict 3:strict 4:strict 5:strict 6:strict 7:strict
            reco-prio-tc 0:0 1:0 2:0 3:1 4:0 5:0 6:0 7:0
            """
        )
        pfc_out = dedent(
            """\
            pfc-cap 4 macsec-bypass off delay 1949
            prio-pfc 0:off 1:off 2:off 3:on 4:off 5:off 6:off 7:off
            """
        )
        app_out = "dscp-prio 26:3"
        wrapper._connection.execute_command.side_effect = [
            self._out(ets_out),
            self._out(pfc_out),
            self._out(app_out),
        ]
        result = wrapper.get_dcb()
        assert set(result) == {LOCAL_ETS, LOCAL_PFC, LOCAL_APP}

        ets = result[LOCAL_ETS]
        assert ets["0"] == {
            "TSA": "ETS",
            "Bandwidth": 70,
            "Priorities": [0, 1, 2, 4, 5, 6, 7],
        }
        assert ets["1"] == {"TSA": "ETS", "Bandwidth": 30, "Priorities": [3]}
        assert ets["2"] == {"TSA": "STRICT", "Bandwidth": 0, "Priorities": []}

        assert result[LOCAL_PFC] == [
            False,
            False,
            False,
            True,
            False,
            False,
            False,
            False,
        ]
        assert result[LOCAL_APP] == {0: {"selector": "dscp", "priority": 3, "protocol": "26"}}

    def test_stderr_raises(self, wrapper):
        wrapper._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr="dcb: command failed"
        )
        with pytest.raises(DcbExecutionError):
            wrapper.get_pfc()

    def test_empty_output(self, wrapper):
        wrapper._connection.execute_command.return_value = self._out("")
        assert wrapper.get_pfc() == {LOCAL_PFC: [False] * 8}
        assert wrapper.get_app() == {LOCAL_APP: {}}

    def test_execute_dcb_command(self, wrapper):
        command = "dcb pfc set dev eth1 prio-pfc 0:off 1:off 2:off 3:on 4:off 5:off 6:off 7:off"
        wrapper._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="", return_code=0, stderr=""
        )
        wrapper._execute_dcb_command(command)
        wrapper._connection.execute_command.assert_called_once_with(
            command,
            custom_exception=DcbExecutionProcessError,
            expected_return_codes=[0],
        )

    def test_execute_dcb_command_stderr_raises(self, wrapper):
        command = "dcb ets set dev eth1 tc-tsa 0:ets tc-bw 0:100 prio-tc 0:0"
        wrapper._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="",
            stdout="",
            return_code=0,
            stderr="Attribute write: Unknown error -1",
        )
        with pytest.raises(DcbExecutionError, match="Attribute write: Unknown error -1"):
            wrapper._execute_dcb_command(command)

    def test_execute_dcb_command_process_error_propagates(self, wrapper):
        wrapper._connection.execute_command.side_effect = DcbExecutionProcessError(
            returncode=1, cmd="dcb ets set dev eth1 willing off", stderr="failed"
        )
        with pytest.raises(DcbExecutionProcessError):
            wrapper._execute_dcb_command("dcb ets set dev eth1 willing off")

    def test_format_app_map(self, wrapper):
        assert wrapper._format_app_map({26: 3, 30: 3}) == "26:3 30:3"
        assert wrapper._format_app_map([(26, 3), (30, 3)]) == "26:3 30:3"
        assert wrapper._format_app_map({"0x8906": 3}) == "0x8906:3"

    def test_format_app_map_empty(self, wrapper):
        with pytest.raises(DcbExecutionError):
            wrapper._format_app_map({})

    def test_format_app_map_malformed(self, wrapper):
        with pytest.raises(DcbExecutionError):
            wrapper._format_app_map([(1, 2, 3)])
