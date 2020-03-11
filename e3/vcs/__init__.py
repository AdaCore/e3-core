from e3.error import E3Error


class VCSError(E3Error):
    def __init__(self, message, origin, process=None):
        super(VCSError, self).__init__(message, origin)
        self.origin = origin
        self.message = message
        self.process = process
