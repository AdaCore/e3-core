import e3.error


class AnodError(e3.error.E3Error):
    def __init__(self, cmd, msg=None):
        if msg is None:
            # Use cmd as the exception message directly
            super(AnodError, self).__init__(None, cmd)
        else:
            super(AnodError, self).__init__(cmd, msg)


class SpecError(AnodError):
    def __init__(self, cmd, msg=None):
        if msg is None:
            # Use cmd as the exception message directly
            super(AnodError, self).__init__(None, cmd)
        else:
            super(AnodError, self).__init__(cmd, msg)


class SandBoxError(AnodError):
    pass
