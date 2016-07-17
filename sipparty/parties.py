"""parties.py

Implements various convenient `Party` subclasses.

Copyright 2015 David Park

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
from six import itervalues
from .sip.dialogs import SimpleCallDialog
from .media.sessions import SingleRTPSession
from .party import Party


class NoMediaSimpleCallsParty(Party):
    """This Party type has no media session, so is basically useless, except
    for testing that the signaling works.
    """
    MediaSession = None
    InviteDialog = SimpleCallDialog


class SingleRTPSessionSimplenParty(Party):
    InviteDialog = SimpleCallDialog
    MediaSession = SingleRTPSession

AllPartyTypes = [
    _lval for _lval in itervalues(dict(locals()))
    if isinstance(_lval, type)
    if issubclass(_lval, Party)
    if _lval is not Party
]
