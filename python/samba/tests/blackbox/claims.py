#!/usr/bin/env python3
# Unix SMB/CIFS implementation.
#
# Blackbox tests for claims support
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

import os

from samba import NTSTATUSError
from samba.auth import AuthContext
from samba.credentials import Credentials
from samba.gensec import FEATURE_SEAL, Security
from samba.tests import BlackboxTestCase

SERVER = os.environ["SERVER"]
SERVER_USERNAME = os.environ["USERNAME"]
SERVER_PASSWORD = os.environ["PASSWORD"]

HOST = f"ldap://{SERVER}"
CREDS = f"-U{SERVER_USERNAME}%{SERVER_PASSWORD}"


class ClaimsSupportTests(BlackboxTestCase):
    """Blackbox tests for Claims support

    NOTE: all these commands are subcommands of samba-tool.

    NOTE: the addCleanup functions get called automatically in reverse
    order after the tests finishes, they don't execute straight away.
    """

    def test_user_group_access(self):
        """An example use with groups."""
        client_password = "T3stPassword0nly"
        target_password = "T3stC0mputerPassword"

        # Create a computer.
        self.check_run("computer create claims-server")
        self.addCleanup(self.run_command, "computer delete claims-server")
        self.check_run(f"user setpassword claims-server\\$ --newpassword={target_password}")

        # Create a user.
        self.check_run(f"user create claimstestuser {client_password}")
        self.addCleanup(self.run_command, "user delete claimstestuser")

        # Create an authentication policy.
        self.check_run("domain auth policy create --enforce --name=restricted-servers-pol")
        self.addCleanup(self.run_command,
                        "domain auth policy delete --name=restricted-servers-pol")

        self.check_run("group add server-access-group")
        self.addCleanup(self.run_command, "group delete server-access-group")

        # Set allowed to authenticate to.
        self.check_run(f"domain auth policy modify --name=restricted-servers-pol "
                       "--computer-allowed-to-authenticate-to-by-group=server-access-group")

        self.check_run("user auth policy assign claims-server\\$ --policy=restricted-servers-pol")

        with self.assertRaises(NTSTATUSError) as error:
            self.verify_access(
                client_username="claimstestuser",
                client_password=client_password,
                target_hostname="claims-server",
                target_username="claims-server",
                target_password=target_password,
            )

        self.assertEqual(error.exception.args[0], 3221225581)
        self.assertEqual(
            error.exception.args[1],
            "The attempted logon is invalid. This is either due to a "
            "bad username or authentication information.")

        # Add group members.
        self.check_run("group addmembers server-access-group claimstestuser")

        self.verify_access(
            client_username="claimstestuser",
            client_password=client_password,
            target_hostname="claims-server",
            target_username="claims-server",
            target_password=target_password,
        )

    def test_user_silo_access(self):
        """An example use with authentication silos."""
        client_password = "T3stPassword0nly"
        target_password = "T3stC0mputerPassword"

        # Create a computer.
        self.check_run("computer create claims-server")
        self.addCleanup(self.run_command, "computer delete claims-server")
        self.check_run(f"user setpassword claims-server\\$ --newpassword={target_password}")

        # Create a user.
        self.check_run(f"user create claimstestuser {client_password}")
        self.addCleanup(self.run_command, "user delete claimstestuser")

        # Create an authentication policy.
        self.check_run("domain auth policy create --enforce --name=restricted-servers-pol")
        self.addCleanup(self.run_command,
                        "domain auth policy delete --name=restricted-servers-pol")

        # Create an authentication silo.
        self.check_run("domain auth silo create --enforce --name=restricted-servers-silo "
                       "--user-authentication-policy=restricted-servers-pol "
                       "--computer-authentication-policy=restricted-servers-pol "
                       "--service-authentication-policy=restricted-servers-pol")
        self.addCleanup(self.run_command,
                        "domain auth silo delete --name=restricted-servers-silo")

        # Set allowed to authenticate to.
        self.check_run("domain auth policy modify --name=restricted-servers-pol "
                       "--computer-allowed-to-authenticate-to-by-silo=restricted-servers-silo")

        # Grant access to silo.
        self.check_run("domain auth silo member grant --name=restricted-servers-silo --member=claims-server\\$")
        self.check_run("domain auth silo member grant --name=restricted-servers-silo --member=claimstestuser")

        self.verify_access(
            client_username="claimstestuser",
            client_password=client_password,
            target_hostname="claims-server",
            target_username="claims-server",
            target_password=target_password,
        )

        self.check_run("user auth silo assign claims-server\\$ --silo=restricted-servers-silo")

        with self.assertRaises(NTSTATUSError) as error:
            self.verify_access(
                client_username="claimstestuser",
                client_password=client_password,
                target_hostname="claims-server",
                target_username="claims-server",
                target_password=target_password,
            )

        self.assertEqual(error.exception.args[0], 3221225581)
        self.assertEqual(
            error.exception.args[1],
            "The attempted logon is invalid. This is either due to a "
            "bad username or authentication information.")

        # Set assigned silo on user and computer.
        self.check_run("user auth silo assign claimstestuser --silo=restricted-servers-silo")

        self.verify_access(
            client_username="claimstestuser",
            client_password=client_password,
            target_hostname="claims-server",
            target_username="claims-server",
            target_password=target_password,
        )

    @classmethod
    def _make_cmdline(cls, line):
        """Override to pass line as samba-tool subcommand instead.

        Automatically fills in HOST and CREDS as well.
        """
        if isinstance(line, list):
            cmd = ["samba-tool"] + line + ["-H", HOST, CREDS]
        else:
            cmd = f"samba-tool {line} -H {HOST} {CREDS}"

        return super()._make_cmdline(cmd)

    def verify_access(self, client_username, client_password,
                      target_hostname, target_username, target_password):

        lp = self.get_loadparm()

        client_creds = Credentials()
        client_creds.set_username(client_username)
        client_creds.set_password(client_password)
        client_creds.guess(lp)

        target_creds = Credentials()
        target_creds.set_username(target_username)
        target_creds.set_password(target_password)
        target_creds.guess(lp)

        settings = {
            "lp_ctx": lp,
            "target_hostname": target_hostname
        }

        gensec_client = Security.start_client(settings)
        gensec_client.set_credentials(client_creds)
        gensec_client.want_feature(FEATURE_SEAL)
        gensec_client.start_mech_by_sasl_name("GSSAPI")

        gensec_target = Security.start_server(settings=settings,
                                              auth_context=AuthContext(lp_ctx=lp))
        gensec_target.set_credentials(target_creds)
        gensec_target.start_mech_by_sasl_name("GSSAPI")

        client_finished = False
        server_finished = False
        client_to_server = b""
        server_to_client = b""

        # Operate as both the client and the server to verify the user's
        # credentials.
        while not client_finished or not server_finished:
            if not client_finished:
                print("running client gensec_update")
                client_finished, client_to_server = gensec_client.update(
                    server_to_client)
            if not server_finished:
                print("running server gensec_update")
                server_finished, server_to_client = gensec_target.update(
                    client_to_server)

        print("Got ticket to server we were set not to get a ticket to, and decrypted it")


if __name__ == "__main__":
    import unittest
    unittest.main()