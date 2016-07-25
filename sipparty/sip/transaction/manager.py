"""Manager for SIP transactions.

Copyright 2016 David Park

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging

from ...util import WeakProperty
from ..prot import TransactionID
from .base import Transaction
from .client import InviteClientTransaction, NonInviteClientTransaction
from .oneshot import OneShotTransaction
from .server import InviteServerTransaction, NonInviteServerTransaction

log = logging.getLogger(__name__)


class TransactionManager(object):

    lookup_sentinel = type('TransactionManagerLookupSentinel', (), {})()
    transport = WeakProperty('transport')

    @classmethod
    def transaction_key_for_message(cls, ttype, msg):
        """Return a key for the message to look up its transaction.

        :param message: The message to generate a key for.
        :returns tuple:
            A key in the form of a tuple suitable for looking in
            `self.transactions`.
        """
        return TransactionID(
            ttype,
            msg.ViaHeader.parameters.branch.value, msg.CseqHeader.reqtype)

    def __init__(self, transport):
        """Initialization method.

        :param args:
        """
        self.transport = transport
        self.transactions = {}
        self.terminated_transactions = {}

    def transaction_for_outbound_message(self, msg, **kwargs):
        if msg.isrequest():
            log.debug('Get outbound client trans for request %s', msg.type)
            return self.new_transaction_for_request(
                Transaction.types.client, msg, **kwargs)

        log.debug('Get outbound server trans for response %d', msg.type)
        try:
            return self.lookup_transaction(Transaction.types.server, msg)
        except KeyError:
            log.debug('No extant server transaction.')

            # It's only OK not to have a server transaction for a response
            # already when the response is a 2xx and the request type was an
            # INVITE, because RFC3261 says it is the TU's job to ensure 2xxs
            # are transmitted all the way through, and only then tidy up,
            # and the only way that can
            # happen is if the transaction is not responsible for its
            # transmission. This means the initial server INVITE transaction
            # is completed when the TU passes in the 2xx, and so cannot be
            # reused. Therefore we need a one-off transaction
            #
            # In this case we return the special one-off transaction object,
            # which is not (should not be!) retained anywhere.
            if (200 <= msg.type < 300 and
                    msg.cseqheader.reqtype == msg.types.INVITE):
                log.debug('INVITE 2xx re-transmission, create transaction')
                return self.new_transaction(
                    Transaction.types.oneshot, msg, self.transport, **kwargs)

            raise

    def transaction_for_inbound_message(self, msg, **kwargs):
        if msg.isrequest():
            log.debug('Gt inbound server transaction for request %s', msg.type)
            return self.new_transaction_for_request(
                Transaction.types.server, msg)

        log.debug('Get inbound client trans for response %d', msg.type)
        return self.lookup_transaction(Transaction.types.client, msg)

        # !!! DMP: transactions are to be entirely hidden from the dialog
        # !!! behind the transport. This means that the transaction manager /
        # !!! transport are responsible for determining what transaction is
        # !!! needed, according to what the context of the message is, i.e.
        # !!! server or client.
        # !!!   Question: do we need client_transaction_for_message /
        # !!!   server_transaction_for_message? This would rely on the
        # !!!   transport deducing whether it's server or client, rather than
        # !!!   the transaction manager. How do we distinguish between the two?
        # !!!
        # !!! This also means that the transport needs to associate DNs with
        # !!! SocketProxies to avoid double lookups and connecting more than
        # !!! once to the target.
        #
        # Answers: we want transaction_for_outbound message and
        # transaction_for_inbound_message as that makes most sense with how
        # it's going to be used.

    def __del__(self):
        log.debug('__del__ TransactionManager')
        getattr(
            super(TransactionManager, self), '__del__', lambda: None)()

    def add_transaction_for_message(self, ttype, trans, message):
        tk = self.transaction_key_for_message(message)
        self.transactions[tk] = trans

    def lookup_transaction(self, ttype, message, default=lookup_sentinel):
        """Lookup a transaction for a message.

        :returns Transaction:

        :raises KeyError: if no transaction could be found.
        """
        assert default is self.lookup_sentinel
        tk = self.transaction_key_for_message(ttype, message)
        try:
            return self.transactions[tk]
        except KeyError as exc:
            exc.args = ((
                '%s; message type %s' % (exc.args[0], message.type),) +
                exc.args[1:])
            raise

    def _new_transaction_client(self, msg, **kwargs):

        # !!! HOw is the transaction user getting to here?
        #
        # Continue with the process of implementing retrieval of the correct
        # transaction types according to the spec, and --DONE

        # implement the "one off"
        # transaction that is needed for INVITE 200 retransmissions and ACKs.
        #
        # Also need to implement the server transactions!
        #
        # Then move on to remembering the DN for sockets so that we don't have
        # to canonicalize and learn the address back up to the dialog.
        assert msg.isrequest()
        if msg.type == msg.types.INVITE:
            return InviteClientTransaction(**kwargs)

        return NonInviteClientTransaction(**kwargs)

    def _new_transaction_server(self, msg, **kwargs):
        assert msg.isrequest()
        if msg.type == msg.types.INVITE:
            return InviteServerTransaction(**kwargs)
        return NonInviteServerTransaction(**kwargs)

    def _new_trasaction_oneshot(self, msg, **kwargs):
        assert msg.type == msg.types.ACK
        return OneShotTransaction(**kwargs)

    def new_transaction(self, ttype, *args, **kwargs):
        assert ttype in Transaction.types

        # Call the appropriate specialist method.
        return getattr(self, '_new_transaction_' + ttype)(*args, **kwargs)