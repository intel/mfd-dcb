# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest
from mfd_connect import RPyCConnection
from mfd_sysctl import Sysctl
from mfd_typing import OSName
from mfd_connect.base import ConnectionCompletedProcess
from unittest.mock import call

from mfd_dcb.freebsd import FreeBsdDcb, PfcMode


class TestFreebsdDcb:
    @pytest.fixture
    def dcb(self, mocker):
        conn = mocker.create_autospec(RPyCConnection)
        conn.get_os_name.return_value = OSName.FREEBSD
        mocker.patch(
            "mfd_sysctl.Sysctl.check_if_available",
            mocker.create_autospec(Sysctl.check_if_available),
        )
        mocker.patch(
            "mfd_sysctl.Sysctl.get_version",
            mocker.create_autospec(Sysctl.get_version, return_value="N/A"),
        )
        mocker.patch(
            "mfd_sysctl.Sysctl._get_tool_exec_factory",
            mocker.create_autospec(Sysctl._get_tool_exec_factory, return_value="sysctl"),
        )

        dcb_obj = FreeBsdDcb(connection=conn)
        mocker.stopall()
        return dcb_obj

    def test_constructor_returns_freebsd_instance(self, dcb):
        assert "FreeBsd" in str(dcb)

    def test_dscp_apply_map(self, dcb: FreeBsdDcb):
        # fmt: off
        dscpmap = [
            0, 0, 0, 0, 0, 0, 0, 0,
            1, 0, 0, 0, 0, 0, 0, 0,
            2, 0, 0, 0, 0, 0, 0, 0,
            3, 0, 0, 0, 0, 0, 0, 0,
            4, 0, 0, 0, 0, 0, 0, 0,
            5, 0, 0, 0, 0, 0, 0, 0,
            6, 0, 0, 0, 0, 0, 0, 0,
            7, 0, 0, 0, 0, 0, 0, 0,
        ]
        # fmt: on
        args = {
            "sysctl dev.ice.2.dscp2tc_map.0-7": ",".join(map(str, dscpmap[0:8])),
            "sysctl dev.ice.2.dscp2tc_map.8-15": ",".join(map(str, dscpmap[8:16])),
            "sysctl dev.ice.2.dscp2tc_map.16-23": ",".join(map(str, dscpmap[16:24])),
            "sysctl dev.ice.2.dscp2tc_map.24-31": ",".join(map(str, dscpmap[24:32])),
            "sysctl dev.ice.2.dscp2tc_map.32-39": ",".join(map(str, dscpmap[32:40])),
            "sysctl dev.ice.2.dscp2tc_map.40-47": ",".join(map(str, dscpmap[40:48])),
            "sysctl dev.ice.2.dscp2tc_map.48-55": ",".join(map(str, dscpmap[48:56])),
            "sysctl dev.ice.2.dscp2tc_map.56-63": ",".join(map(str, dscpmap[56:64])),
        }
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            return_code=0, args="", stdout="", stderr=""
        )
        dcb.dscp_apply_map("ice2", dscpmap)
        dcb._connection.execute_command.assert_has_calls(
            [call(f"{k}={v}", expected_return_codes=[0]) for k, v in args.items()]
        )

    def test_dscp_read_map(self, mocker, dcb: FreeBsdDcb):
        # fmt: off
        dscpmap = [
            0, 0, 0, 0, 0, 0, 0, 0,
            1, 0, 0, 0, 0, 0, 0, 0,
            2, 0, 0, 0, 0, 0, 0, 0,
            3, 0, 0, 0, 0, 0, 0, 0,
            4, 0, 0, 0, 0, 0, 0, 0,
            5, 0, 0, 0, 0, 0, 0, 0,
            6, 0, 0, 0, 0, 0, 0, 0,
            7, 0, 0, 0, 0, 0, 0, 0,
        ]
        # fmt: on
        args = {
            "dev.ice.2.dscp2tc_map.0-7": ",".join(map(str, dscpmap[0:8])),
            "dev.ice.2.dscp2tc_map.8-15": ",".join(map(str, dscpmap[8:16])),
            "dev.ice.2.dscp2tc_map.16-23": ",".join(map(str, dscpmap[16:24])),
            "dev.ice.2.dscp2tc_map.24-31": ",".join(map(str, dscpmap[24:32])),
            "dev.ice.2.dscp2tc_map.32-39": ",".join(map(str, dscpmap[32:40])),
            "dev.ice.2.dscp2tc_map.40-47": ",".join(map(str, dscpmap[40:48])),
            "dev.ice.2.dscp2tc_map.48-55": ",".join(map(str, dscpmap[48:56])),
            "dev.ice.2.dscp2tc_map.56-63": ",".join(map(str, dscpmap[56:64])),
        }
        dcb._sysctl.get_sysctl_value = mocker.create_autospec(dcb._sysctl.get_sysctl_value)
        dcb._sysctl.get_sysctl_value.return_value.__str__.side_effect = list(args.values())
        m = dcb.dscp_read_map("ice2")
        assert m == dscpmap
        dcb._sysctl.get_sysctl_value.assert_has_calls([call(a) for a in args.keys()], any_order=True)

    def test_dscp_verify_map(self, mocker, dcb):
        # fmt: off
        dscpmap = [
            0, 0, 0, 0, 0, 0, 0, 0,
            1, 0, 0, 0, 0, 0, 0, 0,
            2, 0, 0, 0, 0, 0, 0, 0,
            3, 0, 0, 0, 0, 0, 0, 0,
            4, 0, 0, 0, 0, 0, 0, 0,
            5, 0, 0, 0, 0, 0, 0, 0,
            6, 0, 0, 0, 0, 0, 0, 0,
            7, 0, 0, 0, 0, 0, 0, 0,
        ]
        # fmt: on
        args = {
            "dev.ice.2.dscp2tc_map.0-7": ",".join(map(str, dscpmap[0:8])),
            "dev.ice.2.dscp2tc_map.8-15": ",".join(map(str, dscpmap[8:16])),
            "dev.ice.2.dscp2tc_map.16-23": ",".join(map(str, dscpmap[16:24])),
            "dev.ice.2.dscp2tc_map.24-31": ",".join(map(str, dscpmap[24:32])),
            "dev.ice.2.dscp2tc_map.32-39": ",".join(map(str, dscpmap[32:40])),
            "dev.ice.2.dscp2tc_map.40-47": ",".join(map(str, dscpmap[40:48])),
            "dev.ice.2.dscp2tc_map.48-55": ",".join(map(str, dscpmap[48:56])),
            "dev.ice.2.dscp2tc_map.56-63": ",".join(map(str, dscpmap[56:64])),
        }
        dcb._sysctl.get_sysctl_value = mocker.create_autospec(dcb._sysctl.get_sysctl_value)
        dcb._sysctl.get_sysctl_value.return_value.__str__.side_effect = list(args.values()) * 2
        assert dcb.dscp_verify_map("ice2", dscpmap) is True
        dcb._sysctl.get_sysctl_value.assert_has_calls([call(a) for a in args.keys()], any_order=True)
        assert dcb.dscp_verify_map("ice2", [0] * 64) is False

    def test_set_pfc_mode(self, mocker, dcb):
        dcb._sysctl.set_sysctl_value = mocker.create_autospec(dcb._sysctl.set_sysctl_value)
        dcb.set_pfc_mode("ice2", PfcMode.DSCP)
        dcb._sysctl.set_sysctl_value.assert_called_once_with("dev.ice.2.pfc_mode", value="1")

    def test_get_pfc_mode(self, mocker, dcb):
        dcb._sysctl.get_sysctl_value = mocker.create_autospec(dcb._sysctl.get_sysctl_value)
        dcb._sysctl.get_sysctl_value.return_value = "1"
        assert dcb.get_pfc_mode("ice2") == PfcMode.DSCP
        dcb._sysctl.get_sysctl_value.return_value = "0"
        assert dcb.get_pfc_mode("ice2") == PfcMode.VLAN

    def test_set_ets_min_rate(self, mocker, dcb):
        dcb._sysctl.set_sysctl_value = mocker.create_autospec(dcb._sysctl.set_sysctl_value)
        dcb.set_ets_min_rate("ice2", [0, 1, 2, 3, 4, 5, 6, 7])
        dcb._sysctl.set_sysctl_value.assert_called_once_with("dev.ice.2.ets_min_rate", value="0,1,2,3,4,5,6,7")

    def test_get_ets_min_rate(self, mocker, dcb):
        dcb._sysctl.get_sysctl_value = mocker.create_autospec(dcb._sysctl.get_sysctl_value)
        dcb._sysctl.get_sysctl_value.return_value = "0,1,2,3,4,5,6,7"
        assert dcb.get_ets_min_rate("ice2") == [0, 1, 2, 3, 4, 5, 6, 7]
