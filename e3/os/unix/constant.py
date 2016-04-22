from __future__ import absolute_import
from __future__ import print_function
import sys

# Constant used in wait3 call to keep process in waitable state
WNOWAIT = 0
if 'linux' in sys.platform:
    WNOWAIT = 0x01000000
elif 'sun' in sys.platform:
    WNOWAIT = 0x00000080
elif 'darwin' in sys.platform:
    WNOWAIT = 0x00000020
elif 'aix' in sys.platform:
    WNOWAIT = 0x00000010
