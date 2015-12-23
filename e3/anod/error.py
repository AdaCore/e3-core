import e3.error


class AnodError(e3.error.E3Error):
    pass


class SpecError(AnodError):
    pass


class SandBoxError(AnodError):
    pass
