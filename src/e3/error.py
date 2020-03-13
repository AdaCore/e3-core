class E3Error(Exception):
    """Exception raised by functions defined in E3."""

    def __init__(self, message, origin=None):
        """Initialize an E3Error.

        E3Error can store several messages and thus be used to propagate them.

        :param message: the exception message
        :type message: str | list[str]
        :param origin: the name of the function, class, or module having raised
            the exception
        :type origin: str
        """
        super(E3Error, self).__init__(message, origin)
        self.origin = origin
        self.messages = []
        if message is not None:
            if isinstance(message, str):
                self.messages.append(message)
            else:
                self.messages.extend(message)

    def __iadd__(self, other):
        """Add messages to the current instance.

        :param other: a message or an E3Error instance
        :type other: str | list[str] | E3Error
        """
        if isinstance(other, E3Error):
            self.messages.extend(other.messages)
        elif isinstance(other, str):
            self.messages.append(other)
        else:
            self.messages.extend(other)
        return self

    def __str__(self):
        if self.messages:
            error_msg = self.messages[-1]
        else:
            error_msg = self.__class__.__name__
        if self.origin:
            return "%s: %s\n" % (self.origin, error_msg)
        else:
            return error_msg
