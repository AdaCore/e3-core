"""Basic ELF reader."""

from __future__ import absolute_import, division, print_function

from os.path import dirname, isfile, join

from e3.binarydata import (Address, BinaryData, BinaryFileBuffer, CharStr,
                           Field, FieldArray, FieldNullTerminatedArray, Offset,
                           String, StructType, UChar, UInt16, UInt32, UIntMax)

E_TYPE_STR = {
    0: 'No file type',
    1: 'Relocatable file',
    2: 'Executable file',
    3: 'Shared object file',
    4: 'Core file',
    0xff00: 'Processor-specific',
    0xffff: 'Processor-specific'}

SH_TYPE_STR = {
    0: 'NULL',
    1: 'PROGBITS',
    2: 'SYMTAB',
    3: 'STRTAB',
    4: 'RELA',
    5: 'HASH',
    6: 'DYNAMIC',
    7: 'NOTE',
    8: 'NOBITS',
    9: 'REL',
    10: 'SHLIB',
    11: 'DYNSYM',
    14: 'INIT_ARRAY',
    15: 'FINI_ARRAY',
    16: 'PREINIT_ARRAY',
    17: 'GROUP',
    18: 'SYMTAB_SHNDX',
    0x60000000: 'LOOS',
    0x6fffffff: 'HIOS',
    0x70000000: 'LOPROC',
    0x7fffffff: 'HIPROC',
    0x80000000: 'LOUSER',
    0xffffffff: 'HIUSER'}

DT_TYPE_STR = {
    0: 'NULL',
    1: 'NEEDED',
    2: 'PLTRELSZ',
    3: 'PLTGOT',
    4: 'HASH',
    5: 'STRTAB',
    6: 'SYMTAB',
    7: 'RELA',
    8: 'RELASZ',
    9: 'RELAENT',
    10: 'STRSZ',
    11: 'SYMENT',
    12: 'INIT',
    13: 'FINI',
    14: 'SONAME',
    15: 'RPATH',
    16: 'SYMBOLIC',
    17: 'REL',
    18: 'RELSZ',
    19: 'RELENT',
    20: 'PLTREL',
    21: 'DEBUG',
    22: 'TEXTREL',
    23: 'JMPREL',
    0x70000000: 'LOPROC',
    0x7fffffff: 'HIPROC'}


class ElfClass(UChar):
    def decode(self, buffer):
        result = UChar.decode(self, buffer)
        BinaryData.set_address_size({1: 32, 2: 64}[self.value])
        return result

    def image(self, indent=0):
        return ('32 bits ELF',
                '64 bits ELF')[self.value - 1]


class ElfData(UChar):
    def decode(self, buffer):
        result = UChar.decode(self, buffer)
        BinaryData.set_endianness({1: 'little', 2: 'big'}[self.value])
        return result

    def image(self, indent=0):
        return ('little endian', 'big endian')[self.value - 1]


class ElfType(UInt16):
    def image(self, indent=0):
        return E_TYPE_STR.get(self.value, "0x%X" % self.value)


class Sh_Type(UInt32):
    def image(self, indent=0):
        return SH_TYPE_STR.get(self.value, "0x%X" % self.value)


class ElfMagic(StructType):
    EI_MAG0 = Field(UChar)
    EI_MAG1 = Field(CharStr)
    EI_MAG2 = Field(CharStr)
    EI_MAG3 = Field(CharStr)

    def is_elf_file(self):
        return self.EI_MAG0.value == 0x7f and \
            self.EI_MAG1.value == b'E' and \
            self.EI_MAG2.value == b'L' and \
            self.EI_MAG3.value == b'F'


class ElfIdent(StructType):
    EI_MAG = Field(ElfMagic)
    EI_CLASS = Field(ElfClass)
    EI_DATA = Field(ElfData)
    EI_VERSION = Field(UChar)
    EI_PAD = FieldArray(UChar, 8)
    EI_NIDENT = Field(UChar)


class ElfHeader(StructType):
    e_ident = Field(ElfIdent)
    e_type = Field(ElfType)
    e_machine = Field(UInt16)
    e_version = Field(UInt32)
    e_entry = Field(Address)
    e_phoff = Field(Offset)
    e_shoff = Field(Offset)
    e_flags = Field(UInt32)
    e_ehsize = Field(UInt16)
    e_phentsize = Field(UInt16)
    e_phnum = Field(UInt16)
    e_shentsize = Field(UInt16)
    e_shnum = Field(UInt16)
    e_shstrndx = Field(UInt16)


class ElfSectionHeader(StructType):
    sh_name = Field(UInt32)
    sh_type = Field(Sh_Type)
    sh_flags = Field(UIntMax)
    sh_addr = Field(Address)
    sh_offset = Field(Offset)
    sh_size = Field(UIntMax)
    sh_link = Field(UInt32)
    sh_info = Field(UInt32)
    sh_addralign = Field(UIntMax)
    sh_entsize = Field(UIntMax)


class ElfDyn(StructType):
    """One element of the .dynamic section."""

    d_tag = Field(UIntMax)
    # The next field in the struct is actually a union.  We currently
    # do not support unions, but luckily this union only contains
    # fields of the same type.  Define the next field using one of
    # those fields for decoding purposes.  And for the entries whose
    # tag is such that we should be using a different field in the
    # union, we'll define properties, allowing us to use field names
    # following the same names as the ones used in the ELF standard.
    d_ptr = Field(Address)

    @property
    def d_val(self):
        """Return d_ptr field value."""
        return self.d_ptr

    def is_null(self):
        """Return True if this is the last entry in the .dynamic section.

        :rtype: bool
        """
        return self.d_tag.value == 0


class ElfDynamicSection(StructType):
    """The .dynamic section."""

    dyn_dynamic = FieldNullTerminatedArray(ElfDyn)


class Elf(object):
    def __init__(self, buffer):
        self.buffer = buffer

        # First decode ELF header
        self.header = ElfHeader()
        self.header.decode(self.buffer)

        # Retrieve section table
        self.section_table = []

        offset = self.header.e_shoff.value
        size = self.header.e_shentsize.value

        for index in range(self.header.e_shnum.value):
            self.section_table.append(ElfSectionHeader())
            self.section_table[-1].decode(self.buffer[offset:])
            offset += size

        # Retrieve section names and create a dictionary
        self.sections = {}
        str_section_off = \
            self.section_table[self.header.e_shstrndx.value].sh_offset.value

        for section in self.section_table:
            section_name = String()
            section_name.decode(
                self.buffer[str_section_off + section.sh_name.value:])
            self.sections[section_name.value] = section

    def get_shared_libraries(self):
        """Get the list of shared libraries this object file depends on.

        :return: a list of shared libraries (strings). When the shared library
            could be found using the RPATH, this function returns the
            path to that shared libraries (not normalized, and not
            necessarily the full path either). Otherwise, the shared
            library is returned as found in the ELF data.
        :rtype: list[str]
        """
        def unpack_str(buf, offset):
            """Return the null-terminated string at offset in buf.

            :param buf: A buffer.
            :param offset: The offset in the buffer where to extract
                the string from.

            :return: a string (the terminating nul character is not included).
            :rtype: str
            """
            str_len = buf[offset:].find('\0')
            return buf[offset:offset + str_len]

        def expanded_so_name(shared_lib_name, path_list):
            """Return the expanded shared library name.

            Implement the ELF shared library loading specs, minus the
            search of the LD_LIBRARY_PATH environment variable, which
            is not handled, yet:

            If so_name contains any '/', then return the name unchanged.
            Otherwise, search for so_name in the path_list directory list,
            and return the path of the first so_name that can be found.
            If not found, return so_name unchanged.

            :param shared_lib_name: The name of a shared library.
            :type shared_lib_name: str
            :param path_list: A list of directory names.  If not absolute,
                these directory names are relative to the current
                directory.
            :type path_list: list[str]

            :rtype: str
            """
            if '/' in shared_lib_name:
                return shared_lib_name

            for so_path in path_list:
                exp_so_name = join(so_path, shared_lib_name)
                if isfile(exp_so_name):
                    return exp_so_name
            # Not found in path_list, return filename unchanged.
            return shared_lib_name

        if '.dynamic' not in self.sections:
            # No .dynamic section, which means no shared library
            # dependency at all.
            return []

        dyn_sect = ElfDynamicSection()
        dyn_sect.decode(self.get_section_content('.dynamic'))
        dyn_str = self.get_section_content('.dynstr')
        if isinstance(dyn_str, BinaryFileBuffer):
            dyn_str = dyn_str.read()

        so_list = []
        rpath = None

        for dyn in dyn_sect.dyn_dynamic:
            if dyn.d_tag.value == 1:  # DT_NEEDED
                so_list.append(unpack_str(dyn_str, dyn.d_val.value))
            elif dyn.d_tag.value == 15:  # DT_RPATH
                rpath = unpack_str(dyn_str, dyn.d_val.value)

        # Now, expand the shared library filenames using the RPATH.

        if not rpath:
            # Either the ELF file has a .dynamic section with no shared
            # library dependency, or else it does not have an rpath entry.
            # Either way, the shared library filenames cannot be expanded.
            # Return the so_list verbatim...
            return so_list

        # Replace "$ORIGIN" in the RPATH with the path to our ELF file.
        path_to_objfile = dirname(self.buffer.filename)
        rpath = [path.replace('$ORIGIN/', '%s/' % (path_to_objfile or '.'))
                 for path in rpath.split(':')]

        return [expanded_so_name(so_name, rpath) for so_name in so_list]

    def get_section_content(self, index):
        """Get the content of a givent section.

        :param index: can be either the index of the section in the section
            table (int) or a section name

        :rtype: str | BinaryFileBuffer
        """
        if isinstance(index, int):
            s = self.section_table[index]
        else:
            s = self.sections[index]

        if str(s.sh_type) == 'NOBITS':
            return ""

        return self.buffer[s.sh_offset.value:
                           s.sh_offset.value + s.sh_size.value]
