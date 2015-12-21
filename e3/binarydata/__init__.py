"""Parsing of binary data.

This package provide some helpers to ease parsing of binary datas such
as object files, executables, ...
"""

from __future__ import absolute_import
import struct
import os
from collections import OrderedDict


class BinaryFileBuffer(object):
    """Buffer class.

    Instance of this class can be used during the decoding of a binary
    structure to avoid passing the full file content to the decoders.
    The resulting instances can be used like an array from which you get
    slices.

    :ivar filename: associated filename. This attribute is set only for the
        first BinaryFileBuffer that open the file. Subsequent instance
        issued from slices do no contain that information.
    :ivar fd: the file descriptor
    :ivar begin: start position
    :ivar last: end position
    """

    def __init__(self, filename=None):
        """Initialize a BinaryFileBuffer.

        :param filename: path to a file. None default value is used
            only internally when creating slice objects
        :type filename: str | None
        """
        self.filename = None

        if filename is not None:
            self.fd = open(filename, 'rb')
            self.begin = 0
            self.last = os.path.getsize(filename) - 1
            self.filename = filename

    def __del__(self):
        self.close()

    def __len__(self):
        return self.last - self.begin + 1

    def read(self):
        """Return the buffer content (in bytes)"""
        self.fd.seek(self.begin)
        result = self.fd.read(self.last - self.begin + 1)
        return result

    def __getitem__(self, key):
        slice_object = BinaryFileBuffer()
        slice_object.fd = self.fd

        if isinstance(key, slice):
            indices = key.indices(len(self))
            slice_object.begin = self.begin + indices[0]
            slice_object.last = self.begin + indices[1] - 1
        else:
            slice_object.begin = self.begin + key
            slice_object.last = self.begin + key

        return slice_object

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        del type, value, tb
        self.close()

    def close(self):
        """Close buffer.

        Note that slices extracted from the original buffer won't close
        the file descriptor.
        """
        if self.filename is not None:
            self.fd.close()


class BinaryData(object):
    """Base class for data decoders/encoders.

    You should not use directly instances of that class
    """
    ADDRESS_ENCODING = b'L'  # 32bits
    ENDIANNESS = b'='  # Native encoding

    def __init__(self):
        pass

    def __str__(self):
        return self.image(indent=0)

    @classmethod
    def set_address_size(cls, size):
        """Set address size.

        Set globally the size of an address. This affect classes such as
        Address or Offset.

        :param size: can be 32, 64 or 16
        :type size: int
        """
        BinaryData.ADDRESS_ENCODING = {32: b'L', 64: b'Q', 16: b'H'}[size]

    @classmethod
    def set_endianness(cls, endian):
        """Set endianness.

        Set globally the endianness used during data decoding. It affects
        behavior of all classes dealing with decoding of numeric types

        :param endian: can be 'native' (default), 'little' or 'big'
        :type endian: str
        """
        BinaryData.ENDIANNESS = {'native': b'=',
                                 'little': b'<',
                                 'big': b'>'}[endian]

    def image(self, indent=0):
        """Return an image of the current object.

        :param indent: integer that represent the required indentation level
        :type indent: int

        :rtype: str
        """
        return b''


class BasicType(BinaryData):
    """Basic type encoder/decoder.

    This class should not be used directly. A child class just have to define
    two class variables: FORMATTER (a formatting python string) and DECODER
    a valid decoding string for struct module. Note that endianness setting is
    automatically applied.
    """
    DECODER = b''

    def __init__(self, value=None):
        """Initialize a BasicType.

        :param value: should be set to the value to be encoded. When decoding
            this parameter is ignored.
        """
        super(BasicType, self).__init__()
        self.size = None
        self.value = value
        self.decoder = BinaryData.ENDIANNESS + self.DECODER

    def decode(self, buffer):
        """Decode.

        Read a value from the beginning of the buffer

        :param buffer: BinaryFileBuffer or string
        :type: BinaryFileBuffer | str

        :return: size in bytes of the decoded data in the buffer
        :rtype: int
        """
        self.size = struct.calcsize(self.decoder)
        self.value = struct.unpack(self.decoder, buffer[0:self.size].read())[0]
        return self.size

    def encode(self):
        """Encode.

        Encode a value. The instance should have in this case been created
        with value parameters different from None.

        :rtype: str
        """
        return struct.pack(self.decoder, self.value)

    def image(self, indent=0):
        """Return an image of the current object.

        :param indent: integer that represent the required indentation level
        :type indent: int

        :rtype: str
        """
        return self.FORMATTER % self.value


class Address(BasicType):
    """Address decoder."""

    FORMATTER = b'0x%x'

    def __init__(self, value=None):
        super(Address, self).__init__(value)
        self.decoder = BinaryData.ENDIANNESS + BinaryData.ADDRESS_ENCODING


class Offset(Address):
    """Offset decoder (same as Address)."""
    pass


class UIntMax(Address):
    """System max unsigned integer decoder (same as Address)."""
    pass


class CharStr(BinaryData):
    """Char as string decoder."""
    def __init__(self, value=None):
        super(CharStr, self).__init__()
        self.size = 1
        self.decoder = None
        self.value = value

    def decode(self, buffer):
        self.value = buffer[0].read()
        return 1

    def encode(self):
        return self.value

    def image(self, indent=0):
        return self.value


class Char(BasicType):
    """8bits signed integer decoder."""
    DECODER = b'b'
    FORMATTER = b'0x%02x'


class Int16(BasicType):
    """16bits signed integer decoder."""
    DECODER = b'h'
    FORMATTER = b'0x%04x'


class Int32(BasicType):
    """32bits signed integer decoder."""
    DECODER = b'l'
    FORMATTER = b'0x%08x'


class Int64(BasicType):
    """64bits signed integer decoder."""
    DECODER = b'q'
    FORMATTER = b'0x%016x'


class UChar(BasicType):
    """8bits unsigned integer decoder."""
    DECODER = b'B'
    FORMATTER = b'0x%02x'


class UInt16(BasicType):
    """16bits unsigned integer decoder."""
    DECODER = b'H'
    FORMATTER = b'0x%04x'


class UInt32(BasicType):
    """32bits unsigned integer decoder."""
    DECODER = b'L'
    FORMATTER = b'0x%08x'


class UInt64(BasicType):
    """64bits unsigned integer decoder."""
    DECODER = b'Q'
    FORMATTER = b'0x%016x'


class Uleb128(BinaryData):
    """Unsigned LEB128 integer decoder."""
    def __init__(self, value=None):
        super(Uleb128, self).__init__()
        self.value = value
        if value is None:
            self.size = 0
        else:
            self.size = 1
        self.decoder = None

    def decode(self, buffer):
        size = 0
        value = 0
        shift = 0

        while True:
            b = struct.unpack('B', buffer[size:size + 1].read())[0]
            size += 1
            value |= b << shift
            shift += 7
            if b >> shift == 0:
                break
        self.value = value
        self.size = size
        return size

    def encode(self):
        pass

    def image(self, indent=0):
        return str(self.value)


class String(BinaryData):
    """C string decoder (null terminated string)."""
    def __init__(self, value=None):
        super(String, self).__init__()
        self.value = value
        self.size = 0
        if self.value is not None:
            self.size = len(value)
        self.decoder = None

    def decode(self, buffer):
        end = 0
        while buffer[end].read() != b'\0':
            end += 1
        self.value = buffer[0:end].read()
        self.size = len(self.value) + 1
        return self.size

    def encode(self):
        return self.value + b'\0'


class Field(object):
    """Simple elements for StructType.

    This class is used to declare elements of class inheriting from
    StructType. See StructType documentation.
    """

    __counter__ = 0

    def __init__(self, kind):
        """Field constructor.

        :param kind: any child class of BinaryData
        """
        self.kind = kind
        self.index = Field.__counter__
        Field.__counter__ += 1

    def decode(self, buffer):
        value = self.kind()
        size = value.decode(buffer)

        return size, value


class FieldArray(Field):
    """Array elements for StructType.

    See StructType documentation
    """

    def __init__(self, kind, size):
        """FieldArray constructor.

        :param kind: any child class of BinaryData
        """
        super(FieldArray, self).__init__(kind)
        self.kind = [self.kind] * size

    def decode(self, buffer):
        value = []
        size = 0
        for el in self.kind:
            val = el()
            size += val.decode(buffer[size:])
            value.append(val)

        return size, value


class FieldNullTerminatedArray(Field):
    """Null terminated array of elements for StructType.

    See StructType documentation
    """

    def decode(self, buffer):
        value = []
        size = 0
        while True:
            val = self.kind()
            size += val.decode(buffer[size:])
            value.append(val)

            if val.is_null():
                break

        return size, value


class MetaStructType(type):
    """StructType metaclass."""
    def __new__(mcs, name, bases, dict):
        new_dict = {'META': OrderedDict()}

        tmp = []
        for k in dict:
            if isinstance(dict[k], Field):
                tmp.append((k, dict[k]))
            else:
                new_dict[k] = dict[k]

        tmp.sort(key=lambda x: x[1].index)

        for item in tmp:
            new_dict['META'][item[0]] = item[1]

        return type.__new__(mcs, name, bases, new_dict)


class StructType(BinaryData):
    """Structure decoder.

    This class is used to decode complete structure in one pass.

    For example, to decode a ELF file header (the first part), you can do:

    .. code-block:: python

        class ElfMagic(StructType):
            EI_MAG0    = Field(UChar)
            EI_MAG1    = Field(CharStr)
            EI_MAG2    = Field(CharStr)
            EI_MAG3    = Field(CharStr)
            EI_CLASS   = Field(ElfClass)
            EI_DATA    = Field(ElfData)
            EI_VERSION = Field(UChar)
            EI_PAD     = FieldArray(UChar, 8)
            EI_NIDENT  = Field(UChar)

    Then to use the decoder:

    .. code-block:: python

        e = ElfMagic()
        e.decode(buffer)
        assert e.EI_MAG1.value == 'E'
        assert e.EI_MAG2.value == 'L'
        assert e.EI_MAG3.value == 'F'

    When declaring a field for a given structure you can use Field, FieldArray
    or FieldNullTerminatedArray classes.
    """
    __metaclass__ = MetaStructType

    def __init__(self, **kwargs):
        super(StructType, self).__init__()
        self.value = kwargs
        self.size = 0

    def __getattr__(self, value):
        return self.value[value]

    def decode(self, buffer):
        self.size = 0
        self.value = OrderedDict()
        for item in self.META:
            size, value = self.META[item].decode(buffer[self.size:])
            self.size += size
            self.value[item] = value
        return self.size

    def encode(self):
        result = ''
        for item in self.META:
            if isinstance(self.value[item], list):
                for k in self.value[item]:
                    result += k.encode()
            else:
                result += self.value[item].encode()
        return result

    def image(self, indent=0):
        result = ['  ' * indent + 'struct: %s' % self.__class__.__name__]

        indent_str = '  ' * (indent + 1)
        for item in self.value:
            if isinstance(self.value[item], list):
                result.append(indent_str + item + ':')
                for el in self.value[item]:
                    result.append(el.image(indent=indent + 1))
            else:
                result.append(
                    indent_str + item + ': ' +
                    self.value[item].image(indent=indent + 1))

        return '\n'.join(result)
