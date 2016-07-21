from __future__ import absolute_import
from __future__ import print_function


class E3Error(Exception):
    """Exception raised by functions defined in E3."""

    def __init__(self, message, origin=None):
        """Initialize an E3Error.

        :param message: the exception message
        :type message: str
        :param origin: the name of the function, class, or module having raised
            the exception
        :type origin: str
        """
        super(E3Error, self).__init__(message, origin)
        self.origin = origin
        self.message = message

    def __str__(self):
        if self.origin:
            return '%s: %s\n' % (self.origin, self.message)
        else:
            return self.message
