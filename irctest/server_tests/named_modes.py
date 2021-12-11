import re

from irctest import cases
from irctest.numerics import (
    ERR_BANNEDFROMCHAN,
    ERR_CANNOTSENDTOCHAN,
    ERR_INVITEONLYCHAN,
    RPL_CHMODELIST,
    RPL_ENDOFLISTPROPLIST,
    RPL_ENDOFPROPLIST,
    RPL_LISTPROPLIST,
    RPL_PROPLIST,
    RPL_UMODELIST,
)
from irctest.patma import ANYLIST, ANYSTR, ListRemainder, StrRe


class _NamedModeTestMixin:
    @cases.mark_capabilities("draft/named-modes")
    @cases.mark_specifications("IRCv3")
    def testListMode(self):
        """Checks list modes (type 1), using 'ban' as example."""
        self.connectClient("foo", name="user", capabilities=["draft/named-modes"])
        self.connectClient("chanop", name="chanop", capabilities=["draft/named-modes"])
        self.joinChannel("chanop", "#chan")
        self.getMessages("chanop")

        # Set ban
        self.sendLine("chanop", "PROP #chan +ban=foo!*@*")
        msg = self.getMessage("chanop")
        if self.ALLOW_MODE_REPLY and msg.command == "MODE":
            self.assertMessageMatch(
                msg, command="MODE", params=["#chan", "+b", "foo!*@*"]
            )
        else:
            self.assertMessageMatch(
                msg, command="PROP", params=["#chan", "+ban=foo!*@*"]
            )

        # Should not appear in the main list
        self.sendLine("chanop", "PROP #chan")
        msg = self.getMessage("chanop")
        self.assertMessageMatch(
            msg, command=RPL_PROPLIST, params=["chanop", "#chan", *ANYLIST]
        )
        self.assertNotIn("ban", msg.params[2:])
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFPROPLIST,
            params=["chanop", "#chan", ANYSTR],
        )

        # Check banned
        self.sendLine("chanop", "PROP #chan ban")
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_LISTPROPLIST,
            params=["chanop", "#chan", "ban", "foo!*@*", *ANYLIST],
        )
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFLISTPROPLIST,
            params=["chanop", "#chan", "ban", ANYSTR],
        )
        self.sendLine("user", "JOIN #chan")
        self.assertMessageMatch(self.getMessage("user"), command=ERR_BANNEDFROMCHAN)

        # Unset ban
        self.sendLine("chanop", "PROP #chan -ban=foo!*@*")
        msg = self.getMessage("chanop")
        if msg.command == "MODE":
            self.assertMessageMatch(
                msg, command="MODE", params=["#chan", "-b", "foo!*@*"]
            )
        else:
            self.assertMessageMatch(
                msg, command="PROP", params=["#chan", "-ban=foo!*@*"]
            )

        # Check unbanned
        self.sendLine("chanop", "PROP #chan ban")
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFLISTPROPLIST,
            params=["chanop", "#chan", "ban", ANYSTR],
        )
        self.sendLine("user", "JOIN #chan")
        self.assertMessageMatch(
            self.getMessage("user"), command="JOIN", params=["#chan"]
        )

    @cases.mark_capabilities("draft/named-modes")
    @cases.mark_specifications("IRCv3")
    def testFlagModeDefaultOn(self):
        """Checks list modes (type 1), using 'noextmsg' as example."""
        self.connectClient("foo", name="user", capabilities=["draft/named-modes"])
        self.connectClient("chanop", name="chanop", capabilities=["draft/named-modes"])
        self.joinChannel("chanop", "#chan")
        self.getMessages("chanop")

        # Check set
        self.sendLine("chanop", "PROP #chan")
        msg = self.getMessage("chanop")
        self.assertMessageMatch(
            msg, command=RPL_PROPLIST, params=["chanop", "#chan", *ANYLIST]
        )
        self.assertIn("noextmsg", msg.params[2:])
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFPROPLIST,
            params=["chanop", "#chan", ANYSTR],
        )
        self.sendLine("user", "PRIVMSG #chan :hi")
        self.assertMessageMatch(
            self.getMessage("user"),
            command=ERR_CANNOTSENDTOCHAN,
            params=["foo", "#chan", ANYSTR],
        )
        self.assertEqual(self.getMessages("chanop"), [])

        # Unset
        self.sendLine("chanop", "PROP #chan -noextmsg")
        msg = self.getMessage("chanop")
        if self.ALLOW_MODE_REPLY and msg.command == "MODE":
            self.assertMessageMatch(msg, command="MODE", params=["#chan", "-noextmsg"])
        else:
            self.assertMessageMatch(msg, command="PROP", params=["#chan", "-noextmsg"])

        # Check unset
        self.sendLine("chanop", "PROP #chan")
        msg = self.getMessage("chanop")
        self.assertMessageMatch(
            msg, command=RPL_PROPLIST, params=["chanop", "#chan", *ANYLIST]
        )
        self.assertNotIn("noextmsg", msg.params[2:])
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFPROPLIST,
            params=["chanop", "#chan", ANYSTR],
        )
        self.sendLine("user", "PRIVMSG #chan :hi")
        self.assertEqual(self.getMessages("user"), [])
        self.assertMessageMatch(
            self.getMessage("chanop"), command="PRIVMSG", params=["#chan", "hi"]
        )

        # Set
        self.sendLine("chanop", "PROP #chan +noextmsg")
        msg = self.getMessage("chanop")
        if self.ALLOW_MODE_REPLY and msg.command == "MODE":
            self.assertMessageMatch(msg, command="MODE", params=["#chan", "+noextmsg"])
        else:
            self.assertMessageMatch(msg, command="PROP", params=["#chan", "+noextmsg"])

        # Check set again
        self.sendLine("chanop", "PROP #chan")
        msg = self.getMessage("chanop")
        self.assertMessageMatch(
            msg, command=RPL_PROPLIST, params=["chanop", "#chan", *ANYLIST]
        )
        self.assertIn("noextmsg", msg.params[2:])
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFPROPLIST,
            params=["chanop", "#chan", ANYSTR],
        )
        self.sendLine("user", "PRIVMSG #chan :hi")
        self.assertMessageMatch(
            self.getMessage("user"),
            command=ERR_CANNOTSENDTOCHAN,
            params=["foo", "#chan", ANYSTR],
        )
        self.assertEqual(self.getMessages("chanop"), [])

    @cases.mark_capabilities("draft/named-modes")
    @cases.mark_specifications("IRCv3")
    def testFlagModeDefaultOff(self):
        """Checks flag modes (type 4), using 'inviteonly' as example."""
        self.connectClient("foo", name="user", capabilities=["draft/named-modes"])
        self.connectClient("chanop", name="chanop", capabilities=["draft/named-modes"])
        self.joinChannel("chanop", "#chan")
        self.getMessages("chanop")

        # Check unset
        self.sendLine("chanop", "PROP #chan")
        msg = self.getMessage("chanop")
        self.assertMessageMatch(
            msg, command=RPL_PROPLIST, params=["chanop", "#chan", *ANYLIST]
        )
        self.assertNotIn("inviteonly", msg.params[2:])
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFPROPLIST,
            params=["chanop", "#chan", ANYSTR],
        )
        self.sendLine("user", "JOIn #chan")
        self.assertMessageMatch(
            self.getMessage("user"), command="JOIN", params=["#chan"]
        )
        self.sendLine("user", "PART #chan :bye")
        self.getMessages("user")
        self.getMessages("chanop")

        # Set
        self.sendLine("chanop", "PROP #chan +inviteonly")
        msg = self.getMessage("chanop")
        if self.ALLOW_MODE_REPLY and msg.command == "MODE":
            self.assertMessageMatch(
                msg, command="MODE", params=["#chan", "+inviteonly"]
            )
        else:
            self.assertMessageMatch(
                msg, command="PROP", params=["#chan", "+inviteonly"]
            )

        # Check set
        self.sendLine("chanop", "PROP #chan")
        msg = self.getMessage("chanop")
        self.assertMessageMatch(
            msg, command=RPL_PROPLIST, params=["chanop", "#chan", *ANYLIST]
        )
        self.assertIn("inviteonly", msg.params[2:])
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFPROPLIST,
            params=["chanop", "#chan", ANYSTR],
        )
        self.sendLine("user", "JOIN #chan")
        self.assertMessageMatch(self.getMessage("user"), command=ERR_INVITEONLYCHAN)

        # Unset
        self.sendLine("chanop", "PROP #chan -inviteonly")
        msg = self.getMessage("chanop")
        if self.ALLOW_MODE_REPLY and msg.command == "MODE":
            self.assertMessageMatch(
                msg, command="MODE", params=["#chan", "-inviteonly"]
            )
        else:
            self.assertMessageMatch(
                msg, command="PROP", params=["#chan", "-inviteonly"]
            )

        # Check unset again
        self.sendLine("chanop", "PROP #chan")
        msg = self.getMessage("chanop")
        self.assertMessageMatch(
            msg, command=RPL_PROPLIST, params=["chanop", "#chan", *ANYLIST]
        )
        self.assertNotIn("inviteonly", msg.params[2:])
        self.assertMessageMatch(
            self.getMessage("chanop"),
            command=RPL_ENDOFPROPLIST,
            params=["chanop", "#chan", ANYSTR],
        )
        self.sendLine("user", "JOIn #chan")
        self.assertMessageMatch(
            self.getMessage("user"), command="JOIN", params=["#chan"]
        )


class NamedModesTestCase(_NamedModeTestMixin, cases.BaseServerTestCase):
    """Normal testing of the named-modes spec."""

    ALLOW_MODE_REPLY = True

    @cases.mark_capabilities("draft/named-modes")
    @cases.mark_specifications("IRCv3")
    def testConnectionNumerics(self):
        """Tests RPL_CHMODELIST and RPL_UMODELIST."""
        self.addClient()
        self.sendLine(1, "CAP LS 302")
        self.getCapLs(1)
        self.sendLine(1, "USER user user user :user")
        self.sendLine(1, "NICK user")
        self.sendLine(1, "CAP END")
        self.skipToWelcome(1)
        msgs = self.getMessages(1)

        seen_chmodes = set()
        seen_umodes = set()

        got_last_chmode = False
        got_last_umode = False
        capturing_re = r"[12345]:(?P<name>(\S+/)?[a-zA-Z0-9-]+)(=[a-zA-Z]+)?"
        # fmt: off
        chmode_re = r"[12345]:(\S+/)?[a-zA-Z0-9-]+(=[a-zA-Z]+)?"
        umode_re  =    r"[34]:(\S+/)?[a-zA-Z0-9-]+(=[a-zA-Z]+)?"  # noqa
        # fmt: on
        chmode_pat = [ListRemainder(StrRe(chmode_re), min_length=1)]
        umode_pat = [ListRemainder(StrRe(umode_re), min_length=1)]
        for msg in msgs:
            if msg.command == RPL_CHMODELIST:
                self.assertFalse(
                    got_last_chmode, "Got RPL_CHMODELIST after the list ended."
                )
                if msg.params[1] == "*":
                    self.assertMessageMatch(
                        msg, command=RPL_CHMODELIST, params=["user", "*", *chmode_pat]
                    )
                else:
                    self.assertMessageMatch(
                        msg, command=RPL_CHMODELIST, params=["user", *chmode_pat]
                    )
                    got_last_chmode = True

                for token in msg.params[-1].split(" "):
                    name = re.match(capturing_re, token).group("name")
                    self.assertNotIn(name, seen_chmodes, f"Duplicate chmode {name}")
                    seen_chmodes.add(name)

            elif msg.command == RPL_UMODELIST:
                self.assertFalse(
                    got_last_umode, "Got RPL_UMODELIST after the list ended."
                )
                if msg.params[1] == "*":
                    self.assertMessageMatch(
                        msg, command=RPL_UMODELIST, params=["user", "*", *umode_pat]
                    )
                else:
                    self.assertMessageMatch(
                        msg, command=RPL_UMODELIST, params=["user", *umode_pat]
                    )
                    got_last_umode = True

                for token in msg.params[-1].split(" "):
                    name = re.match(capturing_re, token).group("name")
                    self.assertNotIn(name, seen_umodes, f"Duplicate umode {name}")
                    seen_umodes.add(name)

        self.assertIn(
            "noextmsg", seen_chmodes, "'noextmsg' chmode not supported/advertised"
        )
        self.assertIn(
            "invisible", seen_umodes, "'invisible' umode not supported/advertised"
        )


class OverlyStrictNamedModesTestCase(_NamedModeTestMixin, cases.BaseServerTestCase):
    """Stronger tests, that assert the server only sends PROP and never MODE.
    Passing these tests is not required to"""

    ALLOW_MODE_REPLY = False