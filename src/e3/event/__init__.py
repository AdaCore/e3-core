from __future__ import annotations

import abc
import json
import os
import sys
import time
import uuid
from typing import TYPE_CHECKING

import e3.env
import e3.hash
import e3.log
import stevedore
from e3.date import timestamp_as_string
from e3.error import E3Error
from e3.fs import mkdir

logger = e3.log.getLogger("event")

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, Callable, Dict, Optional, Tuple, Type


def unique_id() -> str:
    """Return a random globally unique id.

    :return: an id
    """
    # Using clock_seq ensures that the uid of the event has at least
    # microsecond precision.
    return str(uuid.uuid1(clock_seq=int(1000 * time.time())))


class Event:
    """Event class for notifying external services.

    An event is composed of:

      * some data organized as key value dict
      * some attachments

    By default the data will contain the following keys:
      * name: the name of the event
      * uid: a global unique id
      * begin_time: time at which the event was created
      * end_time: time at which the event was closed
    """

    def __init__(self, name: str, uid: Optional[str] = None, **kwargs: Dict[str, Any]):
        """Initialize an Event object.

        :param name: name of the event (e.g. e3_test)
        :param uid: unique identifier. If not given then an automatic uuid is
            computed
        :param kwargs: additional key value pairs
        """
        # Internal attributes. All other attributes are store in _data. By
        # using this construct we ensure the used cannot modify directly these
        # internal.
        object.__setattr__(self, "_attachments", {})
        object.__setattr__(self, "_data", {})
        object.__setattr__(self, "_closed", False)
        object.__setattr__(self, "_formatters", {})

        self.uid = uid if uid is not None else unique_id()
        self.name = name
        self.begin_time = time.time()
        self.end_time: Optional[float] = None

        for key, value in list(kwargs.items()):
            self._data[key] = value

        self.set_formatter("begin_time", self.format_date)
        self.set_formatter("end_time", self.format_date)

    def __enter__(self) -> Event:
        return self

    def __exit__(
        self,
        _type: Optional[Type[BaseException]],
        _val: Optional[BaseException],
        _tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def set_formatter(self, key: str, fun: Callable[[str, Any], dict]) -> None:
        """Add a formatter for a given key. (see as_dict).

        :param key: the event attribute to format
        :param fun: a function that takes the key and the associated value
            and return a dict
        """
        self._formatters[key] = fun

    def __setattr__(self, name: str, value: Any) -> None:
        """Store all attributes in the self._data dict."""
        # Once the event is closed disallow attributes modifications
        if self._closed:
            raise EventError(f"event {self.name} ({self.uid}) closed")
        self._data[name] = value

    def __getattr__(self, name: str) -> Any:
        """Attributes are retrieved in the _data internal dict."""
        try:
            return self._data[name]
        except KeyError as e:
            raise AttributeError(e).with_traceback(sys.exc_info()[2])

    def get_attachments(self) -> Dict[str, Tuple[str, str]]:
        """Return the list of attachments.

        :return: a list of tuple (path, sha1(path))
        """
        return self._attachments

    def attach_file(self, path: str, name: str = "log") -> None:
        """Attach log file to the event.

        When the event will be submitted, the log file will be attached.
        Note that some notification backend might cut or reject the attachment
        if too big.
        :param path: path to a log file
        :param name: name of the file to attach, by default 'log'
        """
        if self._closed:
            raise EventError(f"event {self.name} ({self.uid}) closed")
        self._attachments[name] = (path, e3.hash.sha1(path))

    def close(self) -> None:
        """Close the event. Once done it is not supposed to be modified.

        Calling the method close() allow using it with
        contexlib.closing()
        """
        if not self._closed:
            self.end_time = time.time()
            object.__setattr__(self, "_closed", True)

    def format_date(self, key: str, value: float | str) -> Dict[str, str]:
        """Format timestamp fields.

        :param key: the data key
        :param value: a timestamp
        :return: a dict associating the original key to a human readable date
        """
        if isinstance(value, float):
            return {key: timestamp_as_string(value)}
        else:
            return {key: value}

    def as_dict(self) -> Dict[str, str]:
        """Convert the event data into a dict that can be serialized as json.

        For each key, value of the _data dict by default add them into the
        returned dict (default) or use a formatter that return a dict used to
        update the result.

        :return: a dict
        """
        result = {}
        for key, value in list(self._data.items()):
            if key in self._formatters:
                d = self._formatters[key](key, value)
                result.update(d)
            else:
                result[key] = value
        return result

    def dump(self, event_dir: str) -> str:
        """Dump the event into a json file.

        :param event_dir: directory in which the json is dumped
        :return: json file location
        """
        result = {
            "data": self.as_dict(),
            "attachments": self._attachments,
            "closed": self._closed,
        }
        mkdir(event_dir)
        json_filename = os.path.join(event_dir, f"{self.uid}-{unique_id()}.json")
        with open(json_filename, "w") as fd:
            json.dump(result, fd)
        return json_filename

    @classmethod
    def load(cls, json_filename: str) -> Event:
        """Retrieve an event from a JSON file.

        :param json_filename: file from which event is loaded
        :return: an event
        """
        with open(json_filename) as fd:
            event_dict = json.load(fd)

        result = Event(name="unknown")
        object.__setattr__(result, "_attachments", event_dict["attachments"])
        object.__setattr__(result, "_data", event_dict["data"])
        object.__setattr__(result, "_closed", event_dict["closed"])
        return result


class EventHandler(metaclass=abc.ABCMeta):
    """Interface to implement in order to be able to send events.

    One method needs to be implemented by a new EventManager:

    - send_event: method sending an event to an external service
    """

    @abc.abstractmethod
    def send_event(self, event: Event) -> bool:
        """Send an event.

        :param event: an Event
        :return: True on success, False otherwise
        """
        pass  # all: no cover

    @classmethod
    def decode_config(cls, config_str: str) -> dict:
        """Decode a config string into a dict.

        :param config_str: the string containing configuration information
        :return: a dict that can be used as ``**kwargs`` for the handler
            initialization method
        """
        return {}

    def encode_config(self) -> str:
        """Encode the handler configuration into a string.

        This default implementation can be used for handlers that do not
        need any configuration parameters (i.e: for which __init__ does not
        take any parameter apart for self).

        :return: a string that contains the current handler configuration.
            The string should not contain the '|' character.
        """
        return ""


class EventError(E3Error):
    pass


class EventManager:
    """Manage a set of handlers that will be used to send events."""

    def __init__(self) -> None:
        """Initialize a manager."""
        self.handlers: Dict[str, EventHandler] = {}

    def send_event(self, event: Event) -> bool:
        """Send an event to using all registered handlers.

        :param event: an event
        :return: True if the event was sent successfully to all handlers
        """
        status = True

        for handler in list(self.handlers.values()):
            handler_status = handler.send_event(event)
            if not handler_status:
                status = False

        return status

    def send_event_from_file(self, filename: str) -> bool:
        """Send an event from a dumped event.

        :param filename: path to the json file containing the event
        :return: True if the event was sent successfully to all handlers
        """
        e = Event.load(filename)
        return self.send_event(e)

    def get_handler(self, name: str) -> Callable[..., EventHandler]:
        """Get an handler class by name.

        Available handler classes are registered using the e3.event.handler
        entry_points in your setup.py

        :param name: handler name
        :return: an handler class
        """
        return stevedore.DriverManager("e3.event.handler", name).driver

    def add_handler(self, name: str, *args: Any, **kwargs: Any) -> None:
        """Add an handler instance to the manager.

        args and kwargs are passed to the handler __init__ method

        :param name: the handler name
        """
        logger.info("Add handler %s (%s %s)", name, args, kwargs)
        self.handlers[name] = self.get_handler(name)(*args, **kwargs)

    def load_handlers_from_env(self, var_name: str = "E3_EVENT_HANDLERS") -> None:
        """Add handlers by decoding an env variable.

        The variable value should have the following format:

            handler_name1=some_value|handler_name2=some_value|handler_name3

        The value associated with each handler is passed to the handler method
        decode_config. In most cases the user do not need to create this value
        manually but called handler_config_as_env method to create the
        variable. The main goal of this function is to share EventManager
        configuration among several processes

        :param var_name: the name of the variable
        """
        handler_cfg_str = os.environ.get(var_name, "")
        handler_cfg_dict: Dict[str, str] = dict(
            [
                el.split("=", 1)  # type: ignore
                if "=" in el
                else (el, "")
                for el in handler_cfg_str.split("|")
            ]
        )
        for handler_name, handler_config in list(handler_cfg_dict.items()):
            handler = self.get_handler(handler_name)
            logger.info("Add handler %s (%s)", handler_name, handler_config)
            self.handlers[handler_name] = handler(
                **handler.decode_config(handler_config)  # type: ignore
            )

    def handler_config_as_env(self, var_name: str = "E3_EVENT_HANDLERS") -> None:
        """Add handlers by decoding an env variable.

        :param var_name: the name of the variable containing the handler
            configurations
        """
        result = []
        for handler_name, handler in list(self.handlers.items()):
            config_str = handler.encode_config()
            assert "|" not in config_str
            result.append(f"{handler_name}={config_str}")
        os.environ[var_name] = "|".join(result)


# Declare the default manager
default_manager = EventManager()


def send_event(event: Event) -> bool:
    """Send event using default manager.

    See EventManager.send_event

    :param event: an event
    """
    return default_manager.send_event(event)


def send_event_from_file(filename: str) -> bool:
    """Send event from a file using default manager.

    See EventManager.send_event_from_file
    """
    return default_manager.send_event_from_file(filename)


def add_handler(name: str, *args: Any, **kwargs: Any) -> None:
    """Add handler in the default manager.

    See EventManager.add_handler
    """
    return default_manager.add_handler(name, *args, **kwargs)


def load_handlers_from_env(var_name: str = "E3_EVENT_HANDLERS") -> None:
    """Load handlers to default manager using env var.

    See EventManager.load_handlers_from_env

    :param var_name: the name of the variable containing the configuration
    """
    return default_manager.load_handlers_from_env(var_name=var_name)


def handler_config_as_env(var_name: str = "E3_EVENT_HANDLERS") -> None:
    """Export default manager handler configurations into env.

    See EventManager.handler_config_as_env

    :param var_name: the name of the variable
    """
    return default_manager.handler_config_as_env(var_name=var_name)
