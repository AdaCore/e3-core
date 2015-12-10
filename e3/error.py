from __future__ import absolute_import


class E3Error(Exception):
    """Exception raised by functions defined in E3."""

    def __init__(self, cmd, msg):
        super(E3Error, self).__init__(cmd, msg)
        self.cmd = cmd
        self.msg = msg

    def __str__(self):
        return '%s: %s\n' % (self.cmd, self.msg)
