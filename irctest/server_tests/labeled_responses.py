"""
`IRCv3 labeled-response <https://ircv3.net/specs/extensions/labeled-response>`_

This specification is a little hard to test because all labels are optional;
so there may be many false positives.
"""

import re

import pytest

from irctest import cases
from irctest.numerics import ERR_UNKNOWNCOMMAND
from irctest.patma import ANYDICT, ANYOPTSTR, NotStrRe, RemainingKeys, StrRe


class LabeledResponsesTestCase(cases.BaseServerTestCase):
    @cases.mark_capabilities("echo-message", "batch", "labeled-response")
    def testLabeledPrivmsgResponsesToMultipleClients(self):
        sender = self.connectClient(
            "sender",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(sender)
        rcpt1 = self.connectClient(
            "rcpt1",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(rcpt1)
        rcpt2 = self.connectClient(
            "rcpt2",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(rcpt2)
        rcpt3 = self.connectClient(
            "rcpt3",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(rcpt3)

        self.sendLine(sender, "@label=12345 PRIVMSG rcpt1,rcpt2,rcpt3 :hi")
        m = self.getMessage(sender)
        m2 = self.getMessage(rcpt1)
        m3 = self.getMessage(rcpt2)
        m4 = self.getMessage(rcpt3)

        # ensure the label isn't sent to recipients
        self.assertMessageMatch(m2, command="PRIVMSG", tags={})
        self.assertMessageMatch(
            m3,
            command="PRIVMSG",
            tags={},
        )
        self.assertMessageMatch(m4, command="PRIVMSG", tags={})

        self.assertMessageMatch(
            m, command="BATCH", fail_msg="No BATCH echo received after sending one out"
        )

    @cases.mark_capabilities("echo-message", "batch", "labeled-response")
    def testLabeledPrivmsgResponsesToClient(self):
        sender = self.connectClient(
            "sender",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(sender)
        recipient = self.connectClient(
            "recipient",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(recipient)

        self.sendLine(sender, "@label=12345 PRIVMSG recipient :hi")
        m = self.getMessage(sender)
        m2 = self.getMessage(recipient)

        # ensure the label isn't sent to recipient
        self.assertMessageMatch(m2, command="PRIVMSG", tags={})

        self.assertMessageMatch(m, command="PRIVMSG", tags={"label": "12345"})

    @pytest.mark.react_tag
    @cases.mark_capabilities("echo-message", "batch", "labeled-response")
    def testLabeledPrivmsgResponsesToChannel(self):
        sender = self.connectClient(
            "sender",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(sender)
        recipient = self.connectClient(
            "recipient",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(recipient)

        # join channels
        self.sendLine(sender, "JOIN #test")
        self.getMessages(sender)
        self.sendLine(recipient, "JOIN #test")
        self.getMessages(recipient)
        self.getMessages(sender)

        self.sendLine(
            sender, "@label=12345;+draft/reply=123;+draft/react=l😃l PRIVMSG #test :hi"
        )
        ms = self.getMessage(sender)
        mt = self.getMessage(recipient)

        # ensure the label isn't sent to recipient
        self.assertMessageMatch(mt, command="PRIVMSG", tags={})

        # ensure sender correctly receives msg
        self.assertMessageMatch(ms, command="PRIVMSG", tags={"label": "12345"})

    @cases.mark_capabilities("echo-message", "batch", "labeled-response")
    def testLabeledPrivmsgResponsesToSelf(self):
        c = self.connectClient(
            "client",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(c)

        self.sendLine(c, "@label=12345 PRIVMSG client :hi")
        m1 = self.getMessage(c)
        m2 = self.getMessage(c)

        number_of_labels = 0
        for m in [m1, m2]:
            self.assertMessageMatch(
                m,
                command="PRIVMSG",
                fail_msg="Got a message back that wasn't a PRIVMSG",
            )
            if "label" in m.tags:
                number_of_labels += 1
                self.assertEqual(
                    m.tags["label"],
                    "12345",
                    m,
                    fail_msg=(
                        "Echo'd label doesn't match the label we sent "
                        "(should be '12345'): {msg}"
                    ),
                )

        self.assertEqual(
            number_of_labels,
            1,
            m1,
            fail_msg=(
                "When sending a PRIVMSG to self with echo-message, "
                "we only expect one message to contain the label. "
                "Instead, {} messages had the label"
            ).format(number_of_labels),
        )

    @cases.mark_capabilities("echo-message", "batch", "labeled-response")
    def testLabeledNoticeResponsesToClient(self):
        sender = self.connectClient(
            "sender",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(sender)
        recipient = self.connectClient(
            "recipient",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(recipient)

        self.sendLine(sender, "@label=12345 NOTICE recipient :hi")
        m = self.getMessage(sender)
        m2 = self.getMessage(recipient)

        # ensure the label isn't sent to recipient
        self.assertMessageMatch(m2, command="NOTICE", tags={})

        self.assertMessageMatch(m, command="NOTICE", tags={"label": "12345"})

    @pytest.mark.react_tag
    @cases.mark_capabilities("echo-message", "batch", "labeled-response")
    def testLabeledNoticeResponsesToChannel(self):
        sender = self.connectClient(
            "sender",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(sender)
        recipient = self.connectClient(
            "recipient",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(recipient)

        # join channels
        self.sendLine(sender, "JOIN #test")
        self.getMessages(sender)
        self.sendLine(recipient, "JOIN #test")
        self.getMessages(recipient)
        self.getMessages(sender)

        self.sendLine(
            sender, "@label=12345;+draft/reply=123;+draft/react=l😃l NOTICE #test :hi"
        )
        ms = self.getMessage(sender)
        mt = self.getMessage(recipient)

        # ensure the label isn't sent to recipient
        self.assertMessageMatch(mt, command="NOTICE", tags={})

        # ensure sender correctly receives msg
        self.assertMessageMatch(ms, command="NOTICE", tags={"label": "12345"})

    @cases.mark_capabilities("echo-message", "batch", "labeled-response")
    def testLabeledNoticeResponsesToSelf(self):
        c = self.connectClient(
            "client",
            capabilities=["echo-message", "batch", "labeled-response"],
            skip_if_cap_nak=True,
        )
        self.getMessages(c)

        self.sendLine(c, "@label=12345 NOTICE client :hi")
        m1 = self.getMessage(c)
        m2 = self.getMessage(c)

        number_of_labels = 0
        for m in [m1, m2]:
            self.assertMessageMatch(
                m, command="NOTICE", fail_msg="Got a message back that wasn't a NOTICE"
            )
            if "label" in m.tags:
                number_of_labels += 1
                self.assertEqual(
                    m.tags["label"],
                    "12345",
                    m,
                    fail_msg=(
                        "Echo'd label doesn't match the label we sent "
                        "(should be '12345'): {msg}"
                    ),
                )

        self.assertEqual(
            number_of_labels,
            1,
            m1,
            fail_msg=(
                "When sending a NOTICE to self with echo-message, "
                "we only expect one message to contain the label. "
                "Instead, {} messages had the label"
            ).format(number_of_labels),
        )

    @pytest.mark.react_tag
    @cases.mark_capabilities(
        "echo-message", "batch", "labeled-response", "message-tags"
    )
    def testLabeledTagMsgResponsesToClient(self):
        sender = self.connectClient(
            "sender",
            capabilities=["echo-message", "batch", "labeled-response", "message-tags"],
            skip_if_cap_nak=True,
        )
        self.getMessages(sender)
        recipient = self.connectClient(
            "recipient",
            capabilities=["echo-message", "batch", "labeled-response", "message-tags"],
            skip_if_cap_nak=True,
        )
        self.getMessages(recipient)

        # Need to get a valid msgid because Unreal validates them
        self.sendLine(sender, "PRIVMSG recipient :hi")
        msgid = self.getMessage(sender).tags["msgid"]
        assert msgid == self.getMessage(recipient).tags["msgid"]

        self.sendLine(
            sender,
            f"@label=12345;+draft/reply={msgid};+draft/react=l😃l TAGMSG recipient",
        )
        m = self.getMessage(sender)
        m2 = self.getMessage(recipient)

        # ensure the label isn't sent to recipient
        self.assertMessageMatch(
            m2,
            command="TAGMSG",
            tags={
                "+draft/reply": msgid,
                "+draft/react": "l😃l",
                RemainingKeys(NotStrRe("label")): ANYOPTSTR,
            },
        )
        self.assertNotIn(
            "label",
            m2.tags,
            m2,
            fail_msg=(
                "When sending a TAGMSG with a label, "
                "the target user shouldn't receive the label "
                "(only the sending user should): {msg}"
            ),
        )

        self.assertMessageMatch(
            m,
            command="TAGMSG",
            tags={
                "label": "12345",
                "+draft/reply": msgid,
                "+draft/react": "l😃l",
                **ANYDICT,
            },
        )

    @pytest.mark.react_tag
    @cases.mark_capabilities(
        "echo-message", "batch", "labeled-response", "message-tags"
    )
    def testLabeledTagMsgResponsesToChannel(self):
        sender = self.connectClient(
            "sender",
            capabilities=["echo-message", "batch", "labeled-response", "message-tags"],
            skip_if_cap_nak=True,
        )
        self.getMessages(sender)
        recipient = self.connectClient(
            "recipient",
            capabilities=["echo-message", "batch", "labeled-response", "message-tags"],
            skip_if_cap_nak=True,
        )
        self.getMessages(recipient)

        # join channels
        self.sendLine(sender, "JOIN #test")
        self.getMessages(sender)
        self.sendLine(recipient, "JOIN #test")
        self.getMessages(recipient)
        self.getMessages(sender)

        # Need to get a valid msgid because Unreal validates them
        self.sendLine(sender, "PRIVMSG #test :hi")
        msgid = self.getMessage(sender).tags["msgid"]
        assert msgid == self.getMessage(recipient).tags["msgid"]

        self.sendLine(
            sender, f"@label=12345;+draft/reply={msgid};+draft/react=l😃l TAGMSG #test"
        )
        ms = self.getMessage(sender)
        mt = self.getMessage(recipient)

        # ensure the label isn't sent to recipient
        self.assertMessageMatch(
            mt,
            command="TAGMSG",
            tags={
                "+draft/reply": msgid,
                "+draft/react": "l😃l",
                RemainingKeys(NotStrRe("label")): ANYOPTSTR,
            },
            fail_msg="No TAGMSG received by the target after sending one out",
        )
        self.assertNotIn(
            "label",
            mt.tags,
            mt,
            fail_msg=(
                "When sending a TAGMSG with a label, "
                "the target user shouldn't receive the label "
                "(only the sending user should): {msg}"
            ),
        )

        # ensure sender correctly receives msg
        self.assertMessageMatch(
            ms,
            command="TAGMSG",
            tags={"label": "12345", "+draft/reply": msgid, **ANYDICT},
        )

    @pytest.mark.react_tag
    @cases.mark_capabilities(
        "echo-message", "batch", "labeled-response", "message-tags"
    )
    def testLabeledTagMsgResponsesToSelf(self):
        c = self.connectClient(
            "client",
            capabilities=["echo-message", "batch", "labeled-response", "message-tags"],
            skip_if_cap_nak=True,
        )
        self.getMessages(c)

        self.sendLine(c, "@label=12345;+draft/reply=123;+draft/react=l😃l TAGMSG client")
        m1 = self.getMessage(c)
        m2 = self.getMessage(c)

        number_of_labels = 0
        for m in [m1, m2]:
            self.assertMessageMatch(
                m, command="TAGMSG", fail_msg="Got a message back that wasn't a TAGMSG"
            )
            if "label" in m.tags:
                number_of_labels += 1
                self.assertEqual(
                    m.tags["label"],
                    "12345",
                    m,
                    fail_msg=(
                        "Echo'd label doesn't match the label we sent "
                        "(should be '12345'): {msg}"
                    ),
                )

        self.assertEqual(
            number_of_labels,
            1,
            m1,
            fail_msg=(
                "When sending a TAGMSG to self with echo-message, "
                "we only expect one message to contain the label. "
                "Instead, {} messages had the label"
            ).format(number_of_labels),
        )

    @cases.mark_capabilities("batch", "labeled-response", "message-tags", "server-time")
    def testBatchedJoinMessages(self):
        c = self.connectClient(
            "client",
            capabilities=["batch", "labeled-response", "message-tags", "server-time"],
            skip_if_cap_nak=True,
        )
        self.getMessages(c)

        self.sendLine(c, "@label=12345 JOIN #xyz")
        m = self.getMessages(c)

        # we expect at least join and names lines, which must be batched
        self.assertGreaterEqual(len(m), 3)

        # valid BATCH start line:
        batch_start = m[0]
        self.assertMessageMatch(
            batch_start,
            command="BATCH",
            params=[StrRe(r"\+.*"), "labeled-response"],
        )
        batch_id = batch_start.params[0][1:]
        # batch id MUST be alphanumerics and hyphens
        self.assertTrue(
            re.match(r"^[A-Za-z0-9\-]+$", batch_id) is not None,
            "batch id must be alphanumerics and hyphens, got %r" % (batch_id,),
        )
        self.assertEqual(batch_start.tags.get("label"), "12345")

        # valid BATCH end line
        batch_end = m[-1]
        self.assertMessageMatch(batch_end, command="BATCH", params=["-" + batch_id])

        # messages must have the BATCH tag
        for message in m[1:-1]:
            self.assertEqual(message.tags.get("batch"), batch_id)

    @cases.mark_capabilities("labeled-response")
    def testNoBatchForSingleMessage(self):
        c = self.connectClient(
            "client", capabilities=["batch", "labeled-response"], skip_if_cap_nak=True
        )
        self.getMessages(c)

        self.sendLine(c, "@label=98765 PING adhoctestline")
        # no BATCH should be initiated for a one-line response,
        # it should just be labeled
        m = self.getMessage(c)
        self.assertMessageMatch(m, command="PONG", tags={"label": "98765"})
        self.assertEqual(m.params[-1], "adhoctestline")

    @cases.mark_capabilities("labeled-response")
    def testEmptyBatchForNoResponse(self):
        c = self.connectClient(
            "client", capabilities=["batch", "labeled-response"], skip_if_cap_nak=True
        )
        self.getMessages(c)

        # PONG never receives a response
        self.sendLine(c, "@label=98765 PONG adhoctestline")

        # labeled-response: "Servers MUST respond with a labeled
        # `ACK` message when a client sends a labeled command that normally
        # produces no response."
        ms = self.getMessages(c)
        self.assertEqual(len(ms), 1)
        ack = ms[0]

        self.assertMessageMatch(ack, command="ACK", tags={"label": "98765"})

    @cases.mark_capabilities("labeled-response")
    def testUnknownCommand(self):
        c = self.connectClient(
            "client", capabilities=["batch", "labeled-response"], skip_if_cap_nak=True
        )

        # this command doesn't exist, but the error response should still
        # be labeled:
        self.sendLine(c, "@label=deadbeef NONEXISTENT_COMMAND")
        ms = self.getMessages(c)
        self.assertEqual(len(ms), 1)
        unknowncommand = ms[0]
        self.assertMessageMatch(
            unknowncommand, command=ERR_UNKNOWNCOMMAND, tags={"label": "deadbeef"}
        )
