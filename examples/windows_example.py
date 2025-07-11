# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Simple example of usage."""

from mfd_dcb import Dcb
from mfd_connect import RPyCConnection
from mfd_typing import DeviceID

conn = RPyCConnection(ip="x.x.x.x")
dcb_obj = Dcb(connection=conn)

print(dcb_obj.is_willing())
print(dcb_obj.set_willing(False, True))
print(
    dcb_obj.set_policy(
        "test1",
        1,
        "-IPSrcPrefixMatchCondition x.x.x.x -IPDstPortStartMatchCondition 5001 -IPDstPortEndMatchCondition 5001",
    )
)
print(dcb_obj.remove_policy("test1"))
print(dcb_obj.get_policies())
print(dcb_obj.verify_policy(dcb_obj.verify_policy({"test1": {"PriorityValue": "1"}})))
print(dcb_obj.is_qos_enabled("SLOT 4 Port 1"))
print(dcb_obj.set_qos("SLOT 4 Port 1", True))
print(dcb_obj.set_default_config())
print(dcb_obj.set_pfc([1, 1, 1, 1, 1, 1, 1, 1]))
print(dcb_obj.set_ets(["1", "2", "3", "4", "5", "6", "7"], [5, 7, 10, 15, 17, 20, 23]))
print(dcb_obj.get_dcb("SLOT 4 Port 1"))
print(dcb_obj.get_ets("SLOT 4 Port 1"))
print(dcb_obj.get_pfc("SLOT 4 Port 1"))
print(dcb_obj.get_app("SLOT 4 Port 1"))
print(dcb_obj.get_remote_ets("SLOT 4 Port 1"))
print(dcb_obj.get_remote_pfc("SLOT 4 Port 1"))
print(dcb_obj.get_remote_app("SLOT 4 Port 1"))
print(dcb_obj.set_dcb_operational_value("Intel(R) Ethernet Network Adapter E810-C-Q2", "DCB", "Enabled"))
print(dcb_obj.get_dcb_operational_value("Intel(R) Ethernet Network Adapter E810-C-Q2", "DCB Version"))

val = dcb_obj.get_dcb("SLOT 4 Port 1")
print(dcb_obj.verify_dcb("SLOT 4 Port 1", val))

print(
    dcb_obj.verify_ets(
        "SLOT 4 Port 1", {"ETS": {"0": {"TSA": "ETS", "Bandwidth": 1000, "Priorities": [0, 1, 2, 3, 4, 5, 6, 7]}}}
    )
)
print(dcb_obj.verify_pfc("SLOT 4 Port 1", {"PFC": [True, False, True, False, True, False, True, False]}))
print(
    dcb_obj.verify_app(
        "SLOT 4 Port 1",
        {"APP": {"0x8906": {"Priority": 3, "Protocol": "Ethertype"}, "3260": {"Priority": 34, "Protocol": "TCP"}}},
    )
)
print(dcb_obj.pfc_bool_to_str(True))
print(dcb_obj.remove_dcb_all_user_priorities())
print(dcb_obj.get_all_dcb_operational_values("Intel(R) Ethernet Network Adapter E810-C-Q2"))
print(dcb_obj.get_dcb_status("Intel(R) Ethernet Network Adapter E810-C-Q2"))
print(
    dcb_obj.set_dcb_status("Intel(R) Ethernet Network Adapter E810-C-Q2", enable_dcb=False, enable_willing_mode=False)
)
print(dcb_obj.get_pfc_enabled_bits("SLOT 4 Port 1", "Intel(R) Ethernet Network Adapter E810-C-Q2", True))
print(dcb_obj.get_pfc_port_statistics("Intel(R) Ethernet Network Adapter E810-C-Q2", 1))
print(dcb_obj.get_pfc_counters("Intel(R) Ethernet Network Adapter E810-C-Q2"))
print(dcb_obj.set_dcb_user_priority_to_tcp_port("10.10.10.10"))
print(dcb_obj.get_dcb_max_supported_traffic_class(True, DeviceID(0x10FB)))
print(dcb_obj.set_dcb(True, "SLOT 4 Port 1"))
