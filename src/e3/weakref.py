from __future__ import annotations

from typing import TypeVar, Generic, TYPE_CHECKING
import weakref

if TYPE_CHECKING:
    from types import TracebackType

_T = TypeVar("_T")
_DEFAULT_T = TypeVar("_DEFAULT_T")


class WeakRef(Generic[_T, _DEFAULT_T]):
    """Manage an optional weak reference on an instance.

    This class is designed to be used in a context ('with' clause) to force the user
    to get a strong reference on the object before using it.

    Without a `strong` reference somewhere, the weak reference may be collected at any
    moment by the garbage collector.

    Examples:
        .. code::

            class X:
                def __init__(self, data: weakref.ReferenceType[object] | object):
                    self.data = data

                def use_data(self):
                    with WeakRef(self.data) as strong:
                        pass
    or
        .. code::

            class X:
                def __init__(self, data: weakref.ReferenceType[object] | object):
                    self.data = WeakRef(data)

                def use_data(self):
                    with self.data:
                        value = self.data.value

    .. warning::

        If a strong reference is passed directly, without a save by the user,
        `self.default()` will always be returned.

        The following example will always returns `self.default()`:

        .. code::

            def myfunction() -> None:
                with WeakRef(MyClass()) as mycls0:
                    # mycls0 is the return value of `self.default()` because the user
                    # doesn't have any reference to `MyClass()`.
                    pass
    """

    def __init__(self, value: _T | _DEFAULT_T | None) -> None:
        """Store the initial managed value and initialise the class instance.

        :param value: The managed object.
        """
        self.__weak = weakref.ref(value) if value is not None else None
        # The list is initialised with a first element set to None, this is to be sure
        # `self.current_strong_reference` will always return a value without making
        # additionnal tests.
        self.__current_reference: list[_T | _DEFAULT_T | None] = [None]

    def default(self) -> _DEFAULT_T | None:
        """Create a default value.

        This method is called if the managed weak reference has been collected by the
        garbage collector. In that situation, the managed weak reference is updated with
        the value returned by this method.

        This method return None by default and can be surcharged by the child class.

        .. note::
            The returned value of this method is used "like this"

        :return: A default value to use if the previous weak reference has been
            collected by the garbage collector. Return None by default.
        """
        return None

    @property
    def value(self) -> _T | _DEFAULT_T | None:
        """Get a strong reference to the wrapped value.

        This property always returns None outside of a context.

        :return: A strong reference to the wrapped value
        """
        return self.__current_reference[-1]

    def __enter__(self) -> _T | _DEFAULT_T | None:
        """Enter in a new context.

        This method will create a strong reference of the current wrapped value, and
        will save it until the context is exited. If the wrapped value is a weak
        reference collected by the garbadge collector, this method returns the `default`
        value.

        :return: A strong reference to the wrapped value.
        """
        if len(self.__current_reference) == 1:
            strong_ref = self.__weak() if self.__weak else None

            # If the previous object has been collected by the garbage collector,
            # then check if we have a not None default value.
            if not strong_ref:
                strong_ref = self.default()

                # If the return value of `self.default` is not None, we can update our
                # `__weak` attribute to possibly re-use it later.
                #
                # Doing this is usefull to avoid re-creating an object in the same
                # scope, for example:
                #
                #   weak = WeakRef(None)
                #   with weak as x:
                #       pass
                #   with weak as y:
                #       pass
                #   assert x is y, "This assertion must not raise"
                if strong_ref:
                    self.__weak = weakref.ref(strong_ref)

            self.__current_reference.append(strong_ref)
        return self.value

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Exit a context.

        This method will remove the saved strong reference and return None, by default,
        to let python manage the exception (if one occure).

        :param exc_type: The type of the raised exception, or None if no exception has
            been raised.
        :param exc_value: The exception value.
        :param traceback: The exception traceback.
        :return: None. This method can also return a boolean value if the exception is
            self managed. See the python documentation for more information.
        """
        if len(self.__current_reference) > 1:
            self.__current_reference.pop()
        return None
