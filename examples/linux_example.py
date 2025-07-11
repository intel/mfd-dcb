# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Simple example of usage."""

from mfd_dcb import LinuxDcb
from mfd_connect import SSHConnection

conn = SSHConnection(username="xxx", password="xxx", ip="x.x.x.x")
dcb_obj = LinuxDcb(connection=conn)

user_priority_mapping = [(0, 1), (3, 2), (5, 4), (6, 7)]
bandwidth_per_traffic_class = [25, 25, 25, 25]
print(dcb_obj.set_ets(user_priority_mapping, bandwidth_per_traffic_class, interface_name="eth4", mode="ieee"))
pfc_per_priority = [False, True, True, False, False, False, False, False]
print(dcb_obj.set_pfc(interface_name="eth4", pfc_per_priority=pfc_per_priority))
print(dcb_obj.restart_lldpad())
print(dcb_obj.set_sw_dcb(interface_name="eth4"))
print(dcb_obj.set_dcbx_mode(interface_name="eth4", mode="ieee"))
print(dcb_obj.is_sw_dcb_mode_enabled(interface_name="eth4"))
print(dcb_obj.set_willing(interface_name="eth4", enable=True, mode="ieee", is_fwlldp_enabled=True))
print(dcb_obj.set_willing(interface_name="eth4", enable=True, mode="cee", is_fwlldp_enabled=True))
print(dcb_obj.get_pfc_counters(interface_name="enp59s0f1"))
print(dcb_obj.get_pfc_counters(interface_name="enp59s0f1", is_40g_adapter=True))
print(dcb_obj.get_pfc_counters(interface_name="enp94s0f0", is_10g_adapter=True))
print(dcb_obj.remove_lldpad_conf())
print(dcb_obj.get_dcb(interface_name="eth4", tool_name="dcbnl"))
print(dcb_obj.get_ets(interface_name="eth4", tool_name="dcbnl"))
print(dcb_obj.get_app(interface_name="eth4", tool_name="dcbnl"))
print(dcb_obj.get_pfc(interface_name="eth4", tool_name="dcbnl"))
print(dcb_obj.get_dcb(interface_name="eth4", tool_name="dcbtool"))
print(dcb_obj.get_ets(interface_name="eth4", tool_name="dcbtool"))
print(dcb_obj.get_app(interface_name="eth4", tool_name="dcbtool"))
print(dcb_obj.get_pfc(interface_name="eth4", tool_name="dcbtool"))
