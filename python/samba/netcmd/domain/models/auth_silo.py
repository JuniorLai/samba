# Unix SMB/CIFS implementation.
#
# Authentication silo model.
#
# Copyright (C) Catalyst.Net Ltd. 2023
#
# Written by Rob van der Linde <rob@catalyst.net.nz>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from .fields import DnField, BooleanField, StringField
from .model import Model


class AuthenticationSilo(Model):
    description = StringField("description")
    enforced = BooleanField("msDS-AuthNPolicySiloEnforced")
    user_policy = DnField("msDS-UserAuthNPolicy")
    service_policy = DnField("msDS-ServiceAuthNPolicy")
    computer_policy = DnField("msDS-ComputerAuthNPolicy")
    members = DnField("msDS-AuthNPolicySiloMembers", many=True)

    @staticmethod
    def get_base_dn(ldb):
        """Return the base DN for the AuthenticationSilo model.

        :param ldb: Ldb connection
        :return: Dn object of container
        """
        base_dn = ldb.get_config_basedn()
        base_dn.add_child(
            "CN=AuthN Silos,CN=AuthN Policy Configuration,CN=Services")
        return base_dn

    @staticmethod
    def get_object_class():
        return "msDS-AuthNPolicySilo"