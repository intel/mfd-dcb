# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

"""Tests for `dcbtool_wrapper` package."""

from textwrap import dedent
import pytest
from mfd_connect import RPyCConnection
from mfd_connect.base import ConnectionCompletedProcess
from mfd_typing import OSName
from mfd_dcb import DcbTool


class TestDcbToolWrapper:
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

    @pytest.fixture()
    def dcb(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.LINUX
        dcbtool_obj = DcbTool(connection=conn, interface_name="eth4")
        mocker.stopall()
        return dcbtool_obj

    def test_get_dcb(self, dcb, mocker):
        expected = {
            "ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "1": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "2": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "3": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
            },
            "PFC": [True],
        }
        ets_out = {
            "ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "1": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "2": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "3": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
            }
        }
        pfc_out = {"PFC": [True]}
        mocker.patch(
            "mfd_dcb.dcbtool_wrapper.DcbTool.get_ets",
            mocker.create_autospec(DcbTool.get_ets, return_value=ets_out),
        )
        mocker.patch(
            "mfd_dcb.dcbtool_wrapper.DcbTool.get_pfc",
            mocker.create_autospec(DcbTool.get_pfc, return_value=pfc_out),
        )
        assert dcb.get_dcb() == expected
        dcb.get_ets.assert_called()
        dcb.get_pfc.assert_called()

    def test_get_pfc(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=self.dcbtool_out, return_code=0, stderr=""
        )
        assert dcb.get_pfc() == {"PFC": [True]}

    def test_get_ets(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout=self.dcbtool_out, return_code=0, stderr=""
        )
        out = {
            "ETS": {
                "0": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "1": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "2": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
                "3": {"TSA": "ETS", "Bandwidth": 100, "Priorities": []},
            }
        }
        assert dcb.get_ets() == out
