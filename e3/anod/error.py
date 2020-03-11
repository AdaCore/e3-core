import e3.error


class AnodError(e3.error.E3Error):
    """Base Anod error."""

    pass


class SpecError(AnodError):
    """Invalid specification file."""

    pass


class SandBoxError(AnodError):
    """Invalid sandbox or wrong sandbox configuration."""

    pass


class ShellError(AnodError):
    """Error returned by a process spawned by Anod."""

    def __init__(self, message, origin=None, process=None):
        super(ShellError, self).__init__(message, origin)
        self.process = process
