# Copyright 2013 Mirantis Inc.
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

import os

from oslo.config import cfg

from cloudbaseinit.openstack.common import log as logging
from cloudbaseinit.plugins.windows.userdataplugins import base
from cloudbaseinit.plugins.windows import userdatautils

opts = [
    cfg.StrOpt('heat_config_dir', default='C:\\cfn', help='The directory '
               'where the Heat configuration files must be saved'),
]

CONF = cfg.CONF
CONF.register_opts(opts)

LOG = logging.getLogger(__name__)


class HeatPlugin(base.BaseUserDataPlugin):
    _heat_user_data_filename = "cfn-userdata"

    def __init__(self):
        super(HeatPlugin, self).__init__("text/x-cfninitdata")

    def _check_heat_config_dir(self):
        if not os.path.exists(CONF.heat_config_dir):
            os.makedirs(CONF.heat_config_dir)

    def process(self, part):
        self._check_heat_config_dir()

        file_name = os.path.join(CONF.heat_config_dir, part.get_filename())
        with open(file_name, 'wb') as f:
            f.write(part.get_payload())

        if part.get_filename() == self._heat_user_data_filename:
            return userdatautils.execute_user_data_script(part.get_payload())
