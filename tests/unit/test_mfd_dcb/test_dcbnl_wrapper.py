# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import re

import pytest
from mfd_connect import RPyCConnection
from mfd_connect.base import ConnectionCompletedProcess

from mfd_dcb.dcbnl_wrapper import Dcbnl
from mfd_dcb.exceptions import DcbExecutionProcessError, DcbExecutionError


class TestReadQosConfiguration:
    @pytest.fixture
    def dcb(self, mocker):
        connection = mocker.create_autospec(RPyCConnection, name="RPyCConnection")
        connection.modules().sys.executable = "/usr/bin/python"

        # Instance of the class containing _read_qos_configuration
        instance = Dcbnl(interface_name="eth0", connection=connection)
        yield instance

    def test_read_qos_configuration_success(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="output", return_code=0, stderr=""
        )
        dcb._connection.path.return_value = "/tmp/tools/dcb/dcbnl.py"
        dcb._read_qos_configuration()
        dcb._connection.execute_command.assert_called_once_with(
            "/usr/bin/python /tmp/tools/dcb/dcbnl.py eth0",
            custom_exception=DcbExecutionProcessError,
            expected_return_codes=[0],
        )
        assert dcb._qos_output == "output"

    def test_read_qos_configuration_command_error(self, dcb):
        dcb._connection.execute_command.return_value = ConnectionCompletedProcess(
            args="", stdout="output", return_code=0, stderr="error"
        )
        dcb._connection.path.return_value = "/tmp/tools/dcb/dcbnl.py"
        with pytest.raises(
            DcbExecutionError,
            match=re.escape("Error while executing dcbnl /usr/bin/python /tmp/tools/dcb/dcbnl.py eth0: error"),
        ):
            dcb._read_qos_configuration()
