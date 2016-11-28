from __future__ import absolute_import, division, print_function

import abc
import uuid

import e3.env
import e3.hash
from e3.error import E3Error


class Event(object):
    """Event class for notifying external services.

    This base class is designed to be extended via plugins.
    """

    def __init__(self, name, env=None, uid=None, **kwargs):
        """Initialize an Event object.

        :param name: name of the event (e.g. e3_test)
        :type name: str
        :param env: the event environment
        :type env: e3.env.BaseEnv
        :param uid: unique identifier
        :type uid: str
        """
        del kwargs
        self.uid = uid if uid is not None else uuid.uuid1()
        self.env = env if env is not None else e3.env.BaseEnv()
        self.name = name
        self.attachments = {}
        self.closed = False

    def attach_file(self, path, name='log'):
        """Attach log file to the event.

        When the event will be submitted, the log file will be attached.
        Note that some notification backend might cut or reject the attachment
        if too big.
        :param path: path to a log file
        :type path: str
        :param name: name of the file to attach, by default 'log'
        """
        self.attachments[name] = (path, e3.hash.sha1(path))

    def close(self):
        """Close the event. Once done it is not supposed to be modified.

        Calling the method close() allow using it with
        contexlib.closing()
        """
        self.closed = True


class EventError(E3Error):
    pass


class EventManager(object):
    """Interface to implement in order to be able to send events.

    Two methods needs to be implemented by a new EventManager:

    - send_event: method sending an event to an external service
    - Event: property returning the subclass of Event used by this EventManager
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, configuration):
        """Initialize an EventManager object."""
        self.configuration = configuration

    @abc.abstractmethod
    def send_event(self, event):
        pass  # all: no cover

    @abc.abstractproperty
    def Event(self):
        """Return the Event class used by this EventManager."""
        pass  # all: no cover
