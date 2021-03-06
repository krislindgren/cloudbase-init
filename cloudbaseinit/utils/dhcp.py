# Copyright 2014 Cloudbase Solutions Srl
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime
import netifaces
import random
import socket
import struct

_DHCP_COOKIE = b'\x63\x82\x53\x63'
_OPTION_END = b'\xff'

OPTION_NTP_SERVERS = 42


def _get_dhcp_request_data(id_req, mac_address_b, requested_options,
                           vendor_id):
    # See: http://www.ietf.org/rfc/rfc2131.txt
    data = b'\x01'
    data += b'\x01'
    data += b'\x06'
    data += b'\x00'
    data += struct.pack('!L', id_req)
    data += b'\x00\x00'
    data += b'\x00\x00'
    data += b'\x00\x00\x00\x00'
    data += b'\x00\x00\x00\x00'
    data += b'\x00\x00\x00\x00'
    data += b'\x00\x00\x00\x00'
    data += mac_address_b
    data += b'\x00' * 10
    data += b'\x00' * 64
    data += b'\x00' * 128
    data += _DHCP_COOKIE
    data += b'\x35\x01\x01'

    if vendor_id:
        vendor_id_b = vendor_id.encode('ascii')
        data += b'\x3c' + struct.pack('b', len(vendor_id_b)) + vendor_id_b

    data += b'\x3d\x07\x01' + mac_address_b
    data += b'\x37' + struct.pack('b', len(requested_options))

    for option in requested_options:
        data += struct.pack('b', option)

    data += _OPTION_END
    return data


def _parse_dhcp_reply(data, id_req):
    message_type = struct.unpack('b', data[0])[0]

    if message_type != 2:
        return (False, {})

    id_reply = struct.unpack('!L', data[4:8])[0]
    if id_reply != id_req:
        return (False, {})

    if data[236:240] != _DHCP_COOKIE:
        return (False, {})

    options = {}

    i = 240
    while data[i] != _OPTION_END:
        id_option = struct.unpack('b', data[i])[0]
        option_data_len = struct.unpack('b', data[i + 1])[0]
        i += 2
        options[id_option] = data[i: i + option_data_len]
        i += option_data_len

    return (True, options)


def _get_mac_address_by_local_ip(ip_addr):
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        for addr in addrs[netifaces.AF_INET]:
            if addr['addr'] == ip_addr:
                return addrs[netifaces.AF_LINK][0]['addr']


def get_dhcp_options(dhcp_host, requested_options=[], timeout=5.0,
                     vendor_id='cloudbase-init'):
    id_req = random.randint(0, 2 ** 32 - 1)
    options = None

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(('', 68))
        s.settimeout(timeout)
        s.connect((dhcp_host, 67))

        local_ip_addr = s.getsockname()[0]
        mac_address = _get_mac_address_by_local_ip(local_ip_addr)

        data = _get_dhcp_request_data(id_req, mac_address, requested_options,
                                      vendor_id)
        s.send(data)

        start = datetime.datetime.now()
        now = start
        replied = False
        while (not replied and
                now - start < datetime.timedelta(seconds=timeout)):
            data = s.recv(1024)
            (replied, options) = _parse_dhcp_reply(data, id_req)
            now = datetime.datetime.now()
    except socket.timeout:
        pass
    finally:
        s.close()

    return options
