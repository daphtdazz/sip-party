"""Complex fields in SIP messages.
"""
import random
import logging
import _util
import vb
import parse
import components
import defaults
import param
import request
import pdb

log = logging.getLogger(__name__)


class Field(parse.Parser, vb.ValueBinder):

    __metaclass__ = _util.CCPropsFor(("delegateattributes", "parseinfo"))

    # For headers that delegate properties, these are the properties to
    # delegate. Note that these are cumulative, so subclasses declaring their
    # own delegateattributes get added to these.
    delegateattributes = ["parameters"]

    value = _util.GenerateIfNotSet("value")

    # parseinfo is also cumulative, so any values set here will be overridden
    # if re-set in subclasses.
    parseinfo = {
        parse.Parser.Pattern:
            "([^;]+)"  # String value.
            "((;[^;]*)*)"  # Parameters.
            "",
        parse.Parser.Mappings:
            [("value",),
             ("parameters", param.Parameters)]
    }

    def __init__(self, value=None):
        super(Field, self).__init__()
        self.parameters = param.Parameters()
        if value is not None:
            self.value = value

    def __str__(self):
        rs = "{self.value}".format(**locals())
        rslist = [rs] + [str(val) for val in self.parameters.itervalues()]
        rs = ";".join(rslist)
        return rs

    def __setattr__(self, attr, val):
        if attr in param.Param.types:
            return setattr(self.parameters, attr, val)
        if attr != "value" and hasattr(self, "value"):
            delval = self.value
            if (hasattr(delval, "delegateattributes") and
                    attr in delval.delegateattributes):
                return setattr(delval, attr, val)

        super(Field, self).__setattr__(attr, val)


class PartyIDField(Field):
    delegateattributes = components.DNameURI.delegateattributes

    parseinfo = {
        parse.Parser.Mappings:
            [("value", components.DNameURI),
             ("parameters", param.Parameters)]
    }

    def __init__(self):
        super(PartyIDField, self).__init__(components.DNameURI())


class ViaField(Field):

    delegateattributes = ["protocol", "transport", "host"]

    parseinfo = {
        parse.Parser.Pattern:
            "(SIP */ *2[.]0)"  # protocol, i.e. SIP/2.0
            "\s*/\s*"
            "(\w+)"  # transport, UDP TCP etc.
            "\s*"
            "([^;]+)"  # Host.
            "((;[^;]*)*)"  # Parameters.
            "",
        parse.Parser.Mappings:
            [("protocol", None, lambda x: x.replace(" ", "")),
             ("transport",),
             ("host", components.Host),
             ("parameters", param.Parameters)]
    }

    def __init__(self, host=None, protocol=defaults.sipprotocol,
                 transport=defaults.transport):
        super(ViaField, self).__init__()
        self.protocol = protocol
        self.transport = transport
        if host is None:
            self.host = components.Host()
        else:
            self.host = host

    # We should always regen value because it is always a one-to-one mapping
    # onto protocol, transport and host.
    value = _util.GenerateIfNotSet("value", alwaysregen=True)

    def generate_value(self):
        prottrans = "/".join((self.protocol, self.transport))

        if self.host is not None:
            hoststr = str(self.host)
            if len(hoststr) == 0:
                hoststr = None

        if hoststr is not None:
            rv = "{prottrans} {hoststr}".format(**locals())
        else:
            rv = "{prottrans}".format(**locals())
        return rv

    def __setattr__(self, attr, val):
        if attr in self.delegateattributes:
            if hasattr(self, "value"):
                del self.value
        super(ViaField, self).__setattr__(attr, val)


class CSeqField(Field):

    delegateattributes = ["number", "reqtype"]

    parseinfo = {
        parse.Parser.Pattern:
            "(\d+)"
            " "
            "([\w_-]+)$",  # No parameters.
        parse.Parser.Mappings:
            [("number", None, int),
             ("reqtype", None, lambda x: getattr(request.Request.types, x))]
    }

    @classmethod
    def GenerateNewNumber(cls):
        return random.randint(0, 2**31 - 1)

    def __init__(self, number=None, reqtype=None):
        super(CSeqField, self).__init__()
        self.number = number
        self.reqtype = reqtype

    def generate_number(self):
        return self.GenerateNewNumber()
    number = _util.GenerateIfNotSet("number")

    def generate_value(self):
        return "{self.number} {self.reqtype}".format(self=self)
    value = _util.GenerateIfNotSet("value", alwaysregen=True)

    def __setattr__(self, attr, val):
        """The CSeq depends on the number and the request line type, so if
        either changes then we need to invalidate the value."""
        if attr in ("number", "reqtype"):
            self.value = None
        super(CSeqField, self).__setattr__(attr, val)


class Max_ForwardsField(Field):
    delegateattributes = ["number"]

    def __init__(self, number=defaults.max_forwards):
        super(Max_ForwardsField, self).__init__()
        self.number = number
        self.bind("number", "value")
