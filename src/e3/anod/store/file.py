from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from typing import cast, overload, TYPE_CHECKING
import json
import os
from pathlib import Path
import tempfile
from e3.fs import extension, rm, mv, cp, sync_tree
from e3.anod.store.interface import StoreError, resource_id as store_resource_id
from e3.archive import is_known_archive_format, create_archive, unpack_archive
from e3.log import getLogger
from e3.dsse import DSSE

from e3.anod.store.interface import StoreRWInterface

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Literal, TypedDict, TypeVar

    from e3.archive import RemoveRootDirType

    from e3.anod.store.interface import StoreReadInterface
    from e3.anod.store.buildinfo import BuildInfo, BuildInfoDict

    FileType = TypeVar("FileType", bound="File")

    class ResourceDict(TypedDict):
        id: str
        path: os.PathLike[str] | str
        size: int
        creation_date: str

    # Once mypy is updated and python11 is used, change the total attribute to use
    # NotRequired instead to improve the type checking.
    # See https://peps.python.org/pep-0655/
    class FileDict(TypedDict, total=False):
        _id: str | None
        kind: str
        name: str
        alias: str
        filename: str
        revision: str
        metadata: dict[str, Any] | None
        build_id: str
        resource_id: str | None
        build: BuildInfoDict
        resource: ResourceDict
        internal: bool | None
        downloaded_as: os.PathLike[str] | str | None
        unpack_dir: str | None


logger = getLogger("e3.anod.store.buildinfo")


@dataclass
class Resource:
    """The resource information about a file.

    :ivar id: The resource id (generaly the sha1 of the file).
    :ivar path: The resource path (Where the file is located).
    :ivar size: The file size.
    :ivar creation_date: The creation date of this resource.
    """

    id: str
    path: os.PathLike[str] | str
    size: int
    creation_date: str


class FileKind(Enum):
    """The kind of file object to be stored."""

    source = "source"
    readme = "readme"
    thirdparty = "thirdparty"
    binary = "binary"
    attachment = "attachment"


class File(object):
    """A file served by Store.

    :ivar    file_id: file ID.
    :vartype file_id: str
    :ivar    build_id: build ID under which the File was created.
    :vartype build_id: str
    :ivar    kind: file type
    :vartype kind: FileKind
    :ivar    name: name of the resource (this is not the filename).
    :vartype name: str
    :ivar    resource_id: resource ID of the file content
    :vartype resource_id: str
    :ivar    filename: expected filename.
    :vartype filename: str
    :ivar    alias: alternate filename.
    :vartype alias: str
    :ivar    revision: free form field containing revision information
    :vartype revision: str
    :ivar    metadata: additional metadata
    :vartype metadata: dict | None
    :ivar    internal: True if the File can be distributed outside AdaCore,
        False otherwise. May also be None, if the information is not known.
    :vartype internal: bool | None
    :ivar build_info: build info
    :vartype build: BuildInfo | None
    """

    def __init__(
        self: FileType,
        build_id: str,
        kind: FileKind,
        name: str,
        filename: str,
        resource_id: str | None = None,
        file_id: str | None = None,
        internal: bool = True,
        alias: str | None = None,
        revision: str = "",
        build_info: BuildInfo | None = None,
        metadata: dict[str, Any] | None = None,
        store: StoreReadInterface | StoreRWInterface | None = None,
        resource_path: os.PathLike[str] | str | None = None,
        unpack_dir: str | None = None,
        resource: Resource | None = None,
    ) -> None:
        """Initialize a File.

        :param build_id: see corresponding attribute.
        :param kind: see corresponding attribute.
        :param name: see corresponding attribute.
        :param filename: see corresponding attribute.
        :param resource_id: see corresponding attribute.
        :param file_id: see corresponding attribute.
        :param internal: see corresponding attribute (default to True).
        :param alias: see corresponding attribute (if None, filename is used).
        :param revision: see corresponding attribute (default is '').
        :param build_info: see corresponding attribute (default is None).
        :param metadata: see corresponding attribute (default is None).
        :param store: a store instance.
        :param resource_path: the path of the file in the current computer. Generaly
            used to create a file to push.
        :param unpack_dir: the directory to unpack the file (if the file is an archive).
        :param resource: a Resource dataclass. Use to link the current file object with
            its real location.
        """
        if resource_path:
            resource_path = os.fspath(resource_path)
        assert file_id is None or isinstance(
            file_id, str
        ), f"invalid file_id: {file_id}"
        self.file_id = file_id
        assert isinstance(build_id, str), f"invalid build_id: {build_id}"
        self.build_id = build_id
        assert isinstance(kind, FileKind), f"invalid kind: {kind}"
        self.kind = kind
        assert isinstance(name, str), f"invalid name: {name}"
        self.name = name
        assert resource_id is None or isinstance(
            resource_id, str
        ), f"invalid resource_id: {resource_id}"
        self.resource_id = resource_id
        assert isinstance(filename, str), f"invalid filename: {filename}"
        self.filename = filename
        self.internal = internal
        self.alias = alias or filename
        self.revision = revision
        self.metadata: dict[str, Any] = metadata or {}

        self.downloaded_as: str | None = None
        self.unpack_dir = unpack_dir
        self.build_info = build_info

        self.store = store
        self.resource = resource

        if resource_path is not None:
            self.bind_to_resource(resource_path)

        if self.resource and self.resource_id and self.resource.id != self.resource_id:
            raise StoreError(
                f"File({self.name=}).resource_id != File({self.name=}).resource.id"
            )

    def push(self: FileType) -> FileType:
        """Upload this file to Store, using self.store to do so.

        :return: A newly created File instance of the final file. The current instance
            is also updated accordingly.
        """
        res = self.load(
            data=self.store.submit_file(self.as_dict()), store=self.store  # type: ignore[union-attr]
        )
        self.__update(res)
        return res

    def __update(self: FileType, file: FileType) -> None:
        """Update this file data.

        This method is used to update the value of the current file from another.

        This is especially used after a file is pushed to our store to update this file
        with the uploaded one, because after pushing a file, some internal values may
        change (for example, a file_id will be generated).

        :param file: The file object or its dict representation used to update the
            current one.
        """
        self.file_id = file.file_id
        self.build_id = file.build_id
        self.kind = file.kind
        self.name = file.name
        self.resource_id = file.resource_id
        self.filename = file.filename
        self.internal = file.internal
        self.alias = file.alias
        self.revision = file.revision
        self.metadata = file.metadata
        self.downloaded_as = file.downloaded_as
        self.unpack_dir = file.unpack_dir
        self.build_info = file.build_info
        self.resource = file.resource

    def bind_to_resource(self: FileType, path: os.PathLike[str] | str) -> None:
        """Bind this File to the file at the given path.

        Unless self.resource_id is already set, this also sets self.resource_id
        using this file's contents (see e3.anod.store.interface.resource_id for
        more info on that).

        :param path: the file path on the current computer.
        """
        if self.resource_id is None:
            self.resource_id = store_resource_id(path)

        self.downloaded_as = os.path.abspath(path)

        if not self.resource:
            self.resource = Resource(
                id=self.resource_id,
                path=self.downloaded_as,
                size=os.stat(self.downloaded_as).st_size,
                creation_date=datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%f+00:00"
                ),
            )

    def set_metadata_statement(self: FileType, name: str, data: DSSE) -> None:
        """Set metadata statement.

        :param name: statement name
        :param data: data associated with it
        """
        if not isinstance(data, DSSE):
            raise StoreError(
                f"Metadata statement should be a DSSE envelope. Got {type(data)}"
            )
        self.metadata[name] = data.as_dict()

    def get_metadata_statement(self: FileType, name: str) -> DSSE | None:
        """Get metadata statement.

        :param name: statement name
        :return: a DSSE envelope
        """
        result_data = self.metadata.get(name)
        if result_data is None:
            return None

        if not isinstance(result_data, dict):
            try:
                # This work with mypy because result_data have Any type
                result_data = json.loads(result_data)
                if not isinstance(result_data, dict):
                    raise TypeError(
                        "Corrupted metadata: Cannot convert metadata into dictionary"
                    )
            except Exception as e:
                logger.exception(e)
                raise e

        return DSSE.load_dict(result_data)

    def update_metadata(self: FileType) -> None:
        """Push file updates to Store."""
        assert isinstance(self.store, StoreRWInterface)
        self.store.update_file_metadata(self.as_dict())

    @classmethod
    def metadata_path(cls: type[FileType], dest_dir: str, name: str) -> str:
        """Return the path to the metadata file associated to a File.

        :param dest_dir: The directory where the File is to be downloaded to.
        :param name: Same as the File.name attribute.
        :return: The path to the metadata file.
        """
        return os.path.join(dest_dir, name + "_meta.json")

    def download(
        self: FileType,
        dest_dir: str | None,
        as_name: str | None = None,
        unpack_dir: str | None = None,
        save_metadata: bool = True,
        remove_root_dir: RemoveRootDirType = True,
        unpack_cmd: Callable[..., None] | None = None,
        delete: bool = True,
        ignore: list[str] | None = None,
        tmp_dir_root: str | None = None,
    ) -> bool:
        """Download a file.

        Note that self.resource_id must be set before this method is called,
        since the file to download is identified using this identifier.
        Raise StoreError if this requirement is not met.

        In case the current component has unpack_dir or downloaded as set then
        the local resource is used rather than retrieving it from the store.

        :param dest_dir: directory in which we keep the archive. If None then
            the archive will be downloaded in a temporary location and deleted
            before the function returns. Having both unpack_dir and dest_dir
            set to None will result in a dummy operation.
        :param as_name: if set to None then the resulting filename is the File
            'name' + an extension. If not None as_name is used instead. The
            extension used is the extension of the filename attribute. If the
            name attribute or as_name already have the same extension as
            filename then the extension won't be repeated twice.
        :param unpack_dir: if not None a call to unpack_archive is done with
            destination set to unpack_dir. Note that the directory should
            exist otherwise StoreError will be raised.
        :param save_metadata: if True save a metadata file along with the
            downloaded file. Note that the option has no effect if dest_dir is
            set to None
        :param remove_root_dir: see e3.archive.unpack_archive. Relevant only if
            unpack_dir is not None. Default is True
        :param unpack_cmd: see e3.archive.unpack_archive. Relevant only if
            unpack_dir is not None. Default is None
        :param delete: see e3.archive.unpack_archive. Relevant only if
            unpack_dir is not None. Default is True
        :param ignore: see e3.archive.unpack_archive. Relevant only if
            unpack_dir is not None. Default is None
        :param tmp_dir_root: see e3.archive.unpack_archive. Relevant only when
            remove_root_dir is True.

        :raise: StoreError if any error is detected (file does not exist,
            destination directory does not exist, etc.).
        :return: True if a file was downloaded, False if the download was skipped
            because the file has already been downloaded and the local copy
            is up to date.
        """
        skip = True

        if self.resource_id is None:
            raise StoreError("Attempt to download a File without its resource_id set")

        if self.store is None:
            raise StoreError(f"File {self.name} is not bind to Store instance")

        # Compute name and filename
        file_ext = extension(self.filename)
        if dest_dir is None:
            # If dest_dir is None create a temporary file and preserve the
            # extension
            fd, downloaded_file = tempfile.mkstemp(suffix=file_ext)
            os.close(fd)
            meta_name = None
        else:
            if as_name is not None:
                meta_name = as_name
            else:
                meta_name = self.name

            basename = meta_name
            if not meta_name.endswith(file_ext):
                basename += file_ext

            downloaded_file = os.path.abspath(os.path.join(dest_dir, basename))

        # Check for previous metadata
        prev_source = None
        if dest_dir is not None:
            if not os.path.isdir(dest_dir):
                raise StoreError(f"non existent dir: {dest_dir}")
            prev_source = self.load_from_meta_file(
                dest_dir=dest_dir,
                name=cast(str, meta_name),
                store=self.store,
                ignore_errors=True,
            )

        if self.unpack_dir is not None:
            # If the source component unpack_dir is set it means that we just
            # need to synchronize the source dir to the target dir. In that
            # case not all cases are working.
            if not remove_root_dir:
                raise StoreError(
                    f"remove_root_dir required to sync unpacked resource "
                    f"{self.unpack_dir}"
                )

            if unpack_cmd is not None:
                raise StoreError(
                    f"unpack_cmd not supported on unpacked resource "
                    f"{self.unpack_dir}"
                )

            if not os.path.isdir(self.unpack_dir):
                raise StoreError(
                    f"unpacked resource directory {self.unpack_dir} does not exist"
                )

            if unpack_dir is None or not os.path.isdir(unpack_dir):
                raise StoreError(f"target directory {unpack_dir} does not exist")

            try:
                updated, deleted = sync_tree(
                    self.unpack_dir, unpack_dir, delete=delete, ignore=ignore
                )
                skip = not updated and not deleted
            except Exception as e:
                logger.exception(e)
                raise StoreError(f"cannot sync {self.unpack_dir}") from e

        else:
            # Should we download or copy the file
            if (
                prev_source is None
                or prev_source.resource_id != self.resource_id
                or not os.path.isfile(downloaded_file)
            ):
                if self.downloaded_as is not None:
                    # The resource is already on the local file system. Just copy it.
                    if (
                        Path(self.downloaded_as).resolve()
                        != Path(downloaded_file).resolve()
                    ):
                        cp(self.downloaded_as, downloaded_file)
                else:
                    # Usual case for which resource should be downloaded from the store
                    self.store.download_resource(self.resource_id, downloaded_file)

                # Ensure next steps are done
                skip = False

            if unpack_dir is not None and is_known_archive_format(downloaded_file):
                # Unpack is supported
                unpack_dir = os.path.abspath(unpack_dir)
                if not skip or (
                    prev_source is not None and prev_source.unpack_dir != unpack_dir
                ):
                    # If the resource is 'packed' then unpack it.
                    try:
                        unpack_archive(
                            filename=downloaded_file,
                            dest=unpack_dir,
                            remove_root_dir=remove_root_dir,
                            delete=delete,
                            unpack_cmd=unpack_cmd,
                            ignore=ignore,
                            tmp_dir_root=tmp_dir_root,
                        )
                        skip = False
                    except Exception as e:
                        logger.exception(e)
                        raise StoreError(
                            f"cannot extract archive {downloaded_file}"
                        ) from e

        self.unpack_dir = unpack_dir

        if dest_dir is None:
            rm(downloaded_file)
            self.downloaded_as = None
        else:
            self.downloaded_as = downloaded_file
            if save_metadata:
                self.save_to_meta_file(
                    dest_dir=dest_dir, name=meta_name  # type: ignore[arg-type]
                )
        return not skip

    def as_dict(self: FileType) -> FileDict:
        """Convert the current File instance into a python dictionary.

        :return: The dictionary representation of the file instance.
        """
        result: FileDict = {
            "_id": self.file_id,
            "build_id": self.build_id,
            "kind": self.kind.value,
            "name": self.name,
            "resource_id": self.resource_id,
            "filename": self.filename,
            "internal": self.internal,
            "alias": self.alias,
            "revision": self.revision,
            "metadata": self.metadata,
            "downloaded_as": self.downloaded_as,
            "unpack_dir": self.unpack_dir,
        }
        if self.build_info is not None:
            result["build"] = self.build_info.as_dict()

        if self.resource:
            result["resource"] = {
                "id": self.resource.id,
                "path": self.resource.path,
                "size": self.resource.size,
                "creation_date": self.resource.creation_date,
            }
        return result

    @classmethod
    def load(
        cls: type[FileType],
        data: FileDict,
        store: StoreReadInterface | StoreRWInterface | None = None,
    ) -> FileType:
        """Load and create a File class instance from a dictionary.

        :param data: The dictionary representing a file.
        :param store: The store class to use if store operations are needed.
        :return: The File instance.
        """
        from e3.anod.store.buildinfo import BuildInfo

        build_info: BuildInfo | None = None
        if "build" in data:
            build_info = BuildInfo.load(data["build"])

        # The `internal` default field value is related to the file kind.
        #
        # `internal` is used to said if some files must be distributed with a component
        # or not.
        #
        # For a binary file, the `internal` default value is `False` because this is a
        # file generated by a component build.
        #
        # For any other file type, if internal is not specified, then the default value
        # is `True` for security reason: If internal is not specified by mistake,
        # the risk of potential leaks is reduced.
        kind = data["kind"]
        internal = data.get("internal")
        if internal is None:
            internal = kind != "binary"

        try:
            result = cls(
                file_id=data["_id"],
                build_id=data["build_id"],
                kind=FileKind(kind),
                name=data["name"],
                resource_id=data["resource_id"],
                filename=data["filename"],
                internal=bool(internal),
                alias=data.get("alias"),
                revision=data.get("revision", ""),
                metadata=data.get("metadata"),
                resource_path=data.get("downloaded_as"),
                unpack_dir=data.get("unpack_dir"),
                build_info=build_info,
                store=store,
                resource=(
                    Resource(
                        id=data["resource"]["id"],
                        path=data["resource"]["path"],
                        size=data["resource"]["size"],
                        creation_date=data["resource"]["creation_date"],
                    )
                    if "resource" in data
                    else None
                ),
            )
        except Exception as e:
            logger.exception(e)
            logger.critical(f"cannot unserialize File from object: {data}")
            raise e

        return result

    @overload
    @classmethod
    def load_from_meta_file(
        cls: type[FileType],
        dest_dir: str,
        name: str,
        store: StoreReadInterface | StoreRWInterface | None = None,
        ignore_errors: Literal[False] = False,
    ) -> FileType:
        """See self.load_from_meta_file.

        This overload indicate that the method will always return a component if
        ignore_errors is False. If no component is found for any reason, raise an error.
        """

    @overload
    @classmethod
    def load_from_meta_file(  # noqa: F811
        cls: type[FileType],
        dest_dir: str,
        name: str,
        store: StoreReadInterface | StoreRWInterface | None = None,
        ignore_errors: Literal[True] = True,
    ) -> FileType | None:
        """See self.load_from_meta_file."""

    @classmethod
    def load_from_meta_file(  # noqa: F811
        cls: type[FileType],
        dest_dir: str,
        name: str,
        store: StoreReadInterface | StoreRWInterface | None = None,
        ignore_errors: bool = False,
    ) -> FileType | None:
        """Load file from a metadata file.

        :param dest_dir: directory in which the metadata is located
        :param name: file basename
        :param store: a store instance to bind to the returned object
        :param ignore_errors: if True, in case of errors return None.
            Otherwise, StoreError is raised.
        :return: a File instance
        """
        meta_path = cls.metadata_path(dest_dir=dest_dir, name=name)
        if not os.path.isfile(meta_path):
            if ignore_errors:
                return None
            raise StoreError(f"non existing metafile {meta_path}")
        try:
            with open(meta_path, "r") as fd:
                data = json.load(fd)
            return cls.load(data=data, store=store)
        except Exception as e:
            if ignore_errors:
                return None
            logger.exception(e)
            raise StoreError(
                f"error while loading metadata file {meta_path} ({e})"
            ) from e

    def save_to_meta_file(self: FileType, dest_dir: str, name: str) -> None:
        """Dump as json file component information.

        :param dest_dir: directory in which the metadata file should
            be saved
        :param name: file basename
        """
        with open(self.metadata_path(dest_dir=dest_dir, name=name), "w") as fd:
            fd.write(json.dumps(self.as_dict(), indent=2))

    @classmethod
    def upload_thirdparty(
        cls: type[FileType], store: StoreRWInterface, path: str, force: bool = False
    ) -> FileType:
        """Upload the given file to Store as a third party.

        :param store: A store read-write object.
        :param path: The patch to the file to upload.
        :param force: If True, do not raise an error if the file to upload
            already exists in Store.

        :raise: StoreError if the file already exists in Store (unless
            force is True).
        :return: A File instance corresponding to the uploaded file on Store.
        """
        from e3.anod.store.buildinfo import BuildInfo

        filename = os.path.basename(path)
        bi = BuildInfo.latest(store=store, setup="thirdparties", ready_only=False)
        f = cls(
            bi.id,
            kind=FileKind.thirdparty,
            name=filename,
            filename=filename,
            store=store,
        )
        f.bind_to_resource(path)

        # Check if third party already exist
        assert f.resource_id is not None

        previous = store.latest_thirdparty(filename, "all", f.resource_id)
        if previous is None:
            previous = store.latest_thirdparty(filename)

        logger.debug(f"Previous third party: {previous}")
        if previous is not None and not force:
            raise StoreError(f"Third party {filename} already exists.")

        result = cls.load(store.create_thirdparty(f.as_dict()), store=store)
        return result

    @classmethod
    def upload_thirdparty_from_dir(
        cls: type[FileType],
        store: StoreRWInterface,
        path: str,
        prefix: str,
        build_dir: str | None = None,
    ) -> str:
        """Generate a third party package from local directory and upload it.

        :param store: The store class used to interact with the store system.
        :param path: local directory from which an archive will be created
        :param prefix: prefix of the third party package name to create
        :param build_dir: where the generated packages will be stored

        This is meant to generate a tarball from a directory on the local
        filesystem and upload it as third party to Store. The date of the
        day is added to the package name. If the package already exists, a
        suffix is automatically added. If too many packages have been created
        that day with the same name the function will raise StoreError.

        :return: name of the uploaded package
        """
        today = datetime.now().strftime("%Y%m%d")
        filename = f"{prefix}-{today}.tgz"
        dest = build_dir or os.path.dirname(path)
        create_archive(
            filename=filename, from_dir=path, from_dir_rename=prefix, dest=dest
        )
        for idx in range(10):
            if idx != 0:
                new_filename = f"{prefix}-{today}-{idx}.tgz"
                mv(os.path.join(dest, filename), os.path.join(dest, new_filename))
                filename = new_filename
            previous = store.latest_thirdparty(filename)
            if previous is None:
                cls.upload_thirdparty(store, os.path.join(dest, filename))
                break
        else:
            raise StoreError("Too many third party packages created today!")

        return filename

    def __eq__(self: FileType, other: object) -> bool:
        """Compare two file object.

        :param other: the other object to compare with the current one.
        :return: False if other is not a file or if other is different to the
            current file.
        """
        if not isinstance(other, self.__class__):
            return False
        for attr_name, attr_val in list(self.__dict__.items()):
            if attr_name in ("downloaded_as", "unpack_dir", "store"):
                # This attribute is not meaningful when comparing two files.
                continue
            val = getattr(other, attr_name)
            if val != attr_val:
                logger.debug(
                    f"File attribute {attr_name!r} is different: "
                    f"other.{attr_name} = {val!r}, self.{attr_name} = {attr_val!r}"
                )
                return False
        return True

    def __ne__(self: FileType, other: object) -> bool:
        """Inverse of self.__eq__.

        :return: True if not self.__eq__(other).
        """
        return not self.__eq__(other)

    def __str__(self: FileType) -> str:
        """Convert a file to a str."""
        return f"{self.name}:{self.kind}:{self.file_id}"
