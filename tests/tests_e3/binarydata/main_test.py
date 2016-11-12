from __future__ import absolute_import, division, print_function

import sys

import e3.os.process
import pytest
from e3.binarydata import BinaryFileBuffer
from e3.binarydata.elf import Elf, ElfMagic


def test_elf():
    def is_elf_file(filename):
        with BinaryFileBuffer(filename) as buffer:
            result = ElfMagic()
            result.decode(buffer)
        result = result.is_elf_file()
        return result
    rlimit = e3.os.process.get_rlimit(platform='x86_64-linux')
    assert is_elf_file(rlimit)

    with BinaryFileBuffer(rlimit) as b:
        elf_f = Elf(b)
        assert b'.text' in elf_f.sections
        assert b'ld-linux-x86-64.so.2' in \
            elf_f.get_section_content(b'.interp').read()


@pytest.mark.skipif(sys.platform != 'darwin',
                    reason='requires otool binarya')
def test_macho():
    import e3.binarydata.macho
    rlimit = e3.os.process.get_rlimit()
    assert '/usr/lib/libSystem.B.dylib' in \
           e3.binarydata.macho.get_dylib_deps(rlimit)
