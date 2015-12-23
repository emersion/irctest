"""
Tests section 4.1 of RFC 1459.
<https://tools.ietf.org/html/rfc1459#section-4.1>
"""

from irctest import cases
from irctest import authentication
from irctest.irc_utils.message_parser import Message
from irctest.basecontrollers import NotImplementedByController
from irctest.client_mock import ConnectionClosed

class PasswordedConnectionRegistrationTestCase(cases.BaseServerTestCase):
    password = 'testpassword'
    @cases.SpecificationSelector.requiredBySpecification('RFC1459', 'RFC2812')
    def testPassBeforeNickuser(self):
        self.addClient()
        self.sendLine(1, 'PASS {}'.format(self.password))
        self.sendLine(1, 'NICK foo')
        self.sendLine(1, 'USER username * * :Realname')

        m = self.getRegistrationMessage(1)
        self.assertMessageEqual(m, command='001',
                fail_msg='Did not get 001 after correct PASS+NICK+USER: {msg}')

    @cases.SpecificationSelector.requiredBySpecification('RFC1459', 'RFC2812')
    def testNoPassword(self):
        self.addClient()
        self.sendLine(1, 'NICK foo')
        self.sendLine(1, 'USER username * * :Realname')
        m = self.getRegistrationMessage(1)
        self.assertNotEqual(m.command, '001',
                msg='Got 001 after NICK+USER but missing PASS')

    @cases.SpecificationSelector.requiredBySpecification('RFC1459', 'RFC2812')
    def testPassAfterNickuser(self):
        """“The password can and must be set before any attempt to register
        the connection is made.”
        -- <https://tools.ietf.org/html/rfc1459#section-4.1.1>

        “The optional password can and MUST be set before any attempt to
        register the connection is made.
        Currently this requires that user send a PASS command before
        sending the NICK/USER combination.”
        -- <https://tools.ietf.org/html/rfc2812#section-3.1.1>
        """
        self.addClient()
        self.sendLine(1, 'NICK foo')
        self.sendLine(1, 'USER username * * :Realname')
        self.sendLine(1, 'PASS {}'.format(self.password))
        m = self.getRegistrationMessage(1)
        self.assertNotEqual(m.command, '001',
                'Got 001 after PASS sent after NICK+USER')

class ConnectionRegistrationTestCase(cases.BaseServerTestCase):
    @cases.SpecificationSelector.requiredBySpecification('RFC1459')
    def testQuitDisconnects(self):
        """“The server must close the connection to a client which sends a
        QUIT message.”
        -- <https://tools.ietf.org/html/rfc1459#section-4.1.3>
        """
        self.connectClient('foo')
        self.getMessages(1)
        self.sendLine(1, 'QUIT')
        with self.assertRaises(ConnectionClosed):
            self.getMessages(1) # Fetch remaining messages
            self.getMessages(1)

    @cases.SpecificationSelector.requiredBySpecification('RFC2812')
    def testQuitErrors(self):
        """“A client session is terminated with a quit message.  The server
        acknowledges this by sending an ERROR message to the client.”
        -- <https://tools.ietf.org/html/rfc2812#section-3.1.7>
        """
        self.connectClient('foo')
        self.getMessages(1)
        self.sendLine(1, 'QUIT')
        try:
            commands = {m.command for m in self.getMessages(1)}
        except ConnectionClosed:
            assert False, 'Connection closed without ERROR.'
        self.assertIn('ERROR', commands,
                fail_msg='Did not receive ERROR as a reply to QUIT.')


    def testNickCollision(self):
        """A user connects and requests the same nickname as an already
        registered user.
        """
        self.connectClient('foo')
        self.addClient()
        self.sendLine(2, 'NICK foo')
        self.sendLine(2, 'USER username * * :Realname')
        m = self.getRegistrationMessage(2)
        self.assertNotEqual(m.command, '001',
                'Received 001 after registering with the nick of a '
                'registered user.')

    def testEarlyNickCollision(self):
        """Two users register simultaneously with the same nick."""
        self.addClient()
        self.addClient()
        self.sendLine(1, 'NICK foo')
        self.sendLine(2, 'NICK foo')
        self.sendLine(1, 'USER username * * :Realname')
        self.sendLine(2, 'USER username * * :Realname')
        m1 = self.getRegistrationMessage(1)
        m2 = self.getRegistrationMessage(2)
        self.assertNotEqual((m1.command, m2.command), ('001', '001'),
                'Two concurrently registering requesting the same nickname '
                'both got 001.')
