"""Handling of Store components."""

from __future__ import annotations

import datetime
import json
import os

from dateutil import parser as dateutil_parser
from typing import overload, TypedDict, TYPE_CHECKING

from e3.anod.store.file import File
from e3.anod.store.interface import StoreError, StoreRWInterface
from e3.log import getLogger

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Literal, TypeVar

    from e3.archive import RemoveRootDirType
    from e3.anod.store.interface import StoreReadInterface
    from e3.anod.store.buildinfo import BuildInfo, BuildInfoDict
    from e3.anod.store.file import FileDict

    ComponentType = TypeVar("ComponentType", bound="Component")

    class ComponentAttachmentDict(TypedDict, total=True):
        name: str
        att_file: FileDict

    class ComponentDict(TypedDict, total=False):
        name: str
        specname: str | None
        _id: str | None
        build_id: str
        creation_date: str
        version: str
        is_valid: bool
        is_published: bool
        platform: str
        files: list[FileDict]
        sources: list[FileDict]
        releases: list[str] | None
        readme: FileDict | None
        attachments: dict[str, FileDict] | list[ComponentAttachmentDict] | None
        build: BuildInfoDict


logger = getLogger("e3.anod.store.component")


class Component(object):
    """A Store component.

    A component is an entity that regroups binaries, sources and additional
    metadata.

    :ivar str build_id: build id
    :ivar str name: component name
    :ivar str platform: platform
    :ivar str version: version
    :ivar str | None specname: the name of the spec that created the component
    :ivar list[File] | None files: list of binary files
    :ivar list[File] | None sources: list of sources
    :ivar File | None readme: readme file if present
    :ivar list[str] | None releases: list of releases
    :ivar bool is_valid: True if the component is valid
    :ivar bool is_published: True if published
    :ivar str | None component_id: ID of the component if defined
    :ivar datetime.datetime | None creation_date: component creation date
    :ivar BuildInfo | None build_info: build info
    :ivar StoreReadInterface | StoreRWInterface | None | None store: The store
        instance defined for this component
    """

    def __init__(
        self: ComponentType,
        build_id: str,
        name: str,
        platform: str,
        version: str,
        specname: str | None = None,
        files: list[File] | None = None,
        sources: list[File] | None = None,
        readme: File | None = None,
        attachments: dict[str, File] | list[ComponentAttachmentDict] | None = None,
        releases: list[str] | None = None,
        is_valid: bool = True,
        is_published: bool = False,
        component_id: str | None = None,
        creation_date: datetime.datetime | None = None,
        build_info: BuildInfo | None = None,
        store: StoreReadInterface | StoreRWInterface | None = None,
    ) -> None:
        """Initialize a Component."""
        self.component_id = component_id
        self.build_id = build_id
        self.name = name
        self.platform = platform
        self.version = version
        self.specname = specname
        self.files = [] if files is None else files
        self.sources = [] if sources is None else sources
        self.readme = readme
        # Using direct access to `attachment` is deprecated.
        # Use the methods
        #   - add_attachment
        #   - get_attachments
        #   - remove_attachment
        #
        # once the attachments are initialized  through the __init__ constructor.
        self.attachments: dict[str, File]
        if isinstance(attachments, list):
            self.attachments = {
                tmp["name"]: File.load(tmp["att_file"]) for tmp in attachments
            }
        else:
            self.attachments = attachments or {}

        self.releases = releases or []
        self.is_valid = is_valid
        self.is_published = is_published
        self.build_info = build_info

        if creation_date is None:
            self.creation_date = datetime.datetime.now(datetime.timezone.utc)
        else:
            assert isinstance(creation_date, datetime.datetime)
            self.creation_date = creation_date

        self.store = store

    def add_attachment(
        self: ComponentType, key: str, file: File, overwrite_existing: bool = False
    ) -> str | None:
        """Add a file in this component's attachments.

        Add given *file* to this component's attachments. A key made of
        *key*,*file.filename* is returned if the file was actually attached.

        If ``key,file.filename`` is already in the list of attachments, and
        *overwrite_existing* is **False**, **None** is returned.

        :param key: The key defining the type of attachment. For instance,
            ``"acats"``. A coma and the *file*'s ``filename`` is appended to
            this key to populate the attachment's dictionary.
        :param file: The file to be appended to this component's attachments.
        :param  overwrite_existing: If *True*, the given *file* is added to this
            component's attachments, even if a file with the same *key* and
            *file.filename* is already attached.

        :return: The key of the attached file, or **None** if the file could
            not be attached.
        """
        file_key: str = f"{key},{file.filename}"
        # Add this file to a dict.
        if file_key not in self.attachments or overwrite_existing:
            self.attachments[file_key] = file
        else:
            # File is not added because the attachment is already there,
            # and the `overwrite_existing` parameter is set to False.
            return None

        return file_key

    def get_attachments(self: ComponentType, key: str | None = None) -> dict[str, File]:
        """Get the list of attachments matching *key*.

        If an attachment key starts with ``<key>,``, it is added to the returned
        list.

        If *key* is set to **None**, all elements are returned.

        :param key: The attachment key to match. If set to **None**, all
            attachments are returned.

        :return: A list of dictionaries. Each dictionary is simply made of
            the matching key and the attached file.
        """
        attachments: dict[str, File] = {}
        file_key: str = key if key is not None else ""
        # Attachments parsing depends on the attachments type.
        for att_key, att_file in self.attachments.items():
            if not file_key or att_key.startswith(file_key):
                attachments[att_key] = att_file

        return attachments

    @classmethod
    def metadata_path(cls: type[ComponentType], dest_dir: str, name: str) -> str:
        """Return path to file containing component metadata.

        :param dest_dir: directory in which the metadata file can be found
        :param name: file basename
        :return: a path to the metadata file
        """
        return os.path.join(dest_dir, name + "_component.json")

    def remove_attachment(self: ComponentType, key: str | None = None) -> bool:
        """Remove an attachment by key.

        To remove all `"spdx"` attachments (for instance), use
        `component.remove_attachment("spdx")`.

        :param key: The attachment key to match. If **None**, all attachments
            are removed.

        :return: **True** if an attachment is actually removed, **False** if
            no attachment matching *key* could be removed.
        """
        removed: bool = False
        if key is None:
            if self.attachments:
                removed = True
            self.attachments.clear()
        else:
            # Use a copy of the keys (hence the use of list()) to avoid
            # iterating on a changing dict.
            for attachment_key in list(self.attachments):
                if attachment_key.startswith(key):
                    del self.attachments[attachment_key]
                    removed = True
        return removed

    def save_to_meta_file(
        self: ComponentType, dest_dir: str, name: str | None = None
    ) -> None:
        """Dump as json file component information.

        :param dest_dir: directory in which the metadata file should
            be saved
        :param name: file basename
        """
        as_name: str = name or self.name
        with open(self.metadata_path(dest_dir, as_name), "w") as fd:
            fd.write(json.dumps(self.as_dict(), indent=2))

    def submit_attachment(self: ComponentType, key: str, file: File) -> ComponentDict:
        """Submit an attachment to a store component.

        Add an attachment to an existing component, upload the file to Store,
        and update the list of attachments for that component.

        :param key: The type of attachment (`"spdx"` for instance).
        :param file: The file to be uploaded and attached to this component.

        :return: The updated component.

        :raise StoreError: If the current store is not a writable instance
        :raise StoreError: If submitting *file* did not return a valid ID
        :raise FileNotFoundError: If *file* has no valid `download_as` field
            (meaning the file does not exist on the file system)
        :raise ValueError: If this component is invalid (no valid ID)
        :raise ValueError: If *file* has no resource ID
        :raise ValueError: If the file could not be added to the attachments
        """
        if not self.component_id:
            raise ValueError(f"Invalid component {self.name!r} (no ID)")
        elif not file.resource_id:
            raise ValueError(f"Missing resource id for {file.name!r}")
        elif not file.downloaded_as:
            raise FileNotFoundError(f"Invalid file {file.name!r}")

        if not isinstance(self.store, StoreRWInterface):
            raise StoreError("Not a writable store instance")

        att_key: str | None = self.add_attachment(
            key=key, file=file, overwrite_existing=True
        )

        # As overwrite_existing is True, this may not happen.
        if att_key is None:
            raise ValueError(f"Could not add {file.name!r} to attachments")

        # Upload file to store.
        submitted_file: FileDict = self.store.submit_file(file.as_dict())

        if not submitted_file["_id"]:
            raise StoreError(f"Invalid submitted file ID for {file.name!r}")

        self.store.add_component_attachment(
            component_id=self.component_id, file_id=submitted_file["_id"], name=att_key
        )

        return self.as_dict()

    @overload
    @classmethod
    def load_from_meta_file(
        cls: type[ComponentType],
        dest_dir: str,
        name: str,
        store: StoreReadInterface | None = None,
        ignore_errors: Literal[False] = False,
    ) -> ComponentType: ...

    @overload
    @classmethod
    def load_from_meta_file(  # noqa: F811
        cls: type[ComponentType],
        dest_dir: str,
        name: str,
        store: StoreReadInterface | None = None,
        ignore_errors: Literal[True] = True,
    ) -> ComponentType | None: ...

    @classmethod
    def load_from_meta_file(  # noqa: F811
        cls: type[ComponentType],
        dest_dir: str,
        name: str,
        store: StoreReadInterface | None = None,
        ignore_errors: bool = False,
    ) -> ComponentType | None:
        """Load components from a metadata file.

        :param dest_dir: directory in which the metadata is located
        :param name: file basename
        :param store: a store instance to bind to the returned object
        :param ignore_errors: if True, in case of errors return None.
            Otherwise, StoreError is raised.
        :return: a component instance
        """
        meta_path = cls.metadata_path(dest_dir=dest_dir, name=name)
        if not os.path.isfile(meta_path):
            if ignore_errors:
                return None
            else:
                raise StoreError(f"non existing metafile {meta_path}")
        try:
            with open(meta_path, "r") as fd:
                data = json.load(fd)
            return cls.load(data=data, store=store)
        except Exception as e:
            if ignore_errors:
                return None
            else:
                logger.exception(e)
                raise StoreError(
                    f"error while loading component metadata file {meta_path} ({e})"
                ) from None

    def as_dict(self: ComponentType) -> ComponentDict:
        """Return a dictionary representation of self.

        Feeding to this class' "load" method the value returned by
        this method creates a new Component value that is equal to self.

        :return: The dictionary representation of self.
        :rtype: dict
        """
        result: ComponentDict = {
            "name": self.name,
            "specname": self.specname,
            "_id": self.component_id,
            "build_id": self.build_id,
            "creation_date": self.creation_date.isoformat(),
            "version": self.version,
            "is_valid": self.is_valid,
            "is_published": self.is_published,
            "platform": self.platform,
            "files": [f.as_dict() for f in self.files],
            "sources": [f.as_dict() for f in self.sources],
            "releases": self.releases,
            "readme": self.readme.as_dict() if self.readme else None,
            "attachments": (
                {name: f.as_dict() for name, f in self.attachments.items()}
                if self.attachments
                else None
            ),
        }

        if self.build_info is not None:
            result["build"] = self.build_info.to_dict()

        return result

    @classmethod
    def load(
        cls: type[ComponentType],
        data: ComponentDict,
        store: StoreReadInterface | StoreRWInterface | None = None,
    ) -> ComponentType:
        """Create a Component from the result of a Store request.

        :param data: The dictionary returned by Store.
        :param store: a Store instance
        """
        from e3.anod.store.buildinfo import BuildInfo

        readme = None
        if data["readme"]:
            readme = File.load(data["readme"], store=store)

        attachments = None
        if data["attachments"]:
            if isinstance(data["attachments"], list):
                attachments = {
                    d["name"]: File.load(d["att_file"], store=store)
                    for d in data["attachments"]
                }
            else:
                attachments = {
                    name: File.load(att, store=store)
                    for name, att in data["attachments"].items()
                }

        build_info = None
        if "build" in data:
            build_info = BuildInfo.load(data["build"])

        return cls(
            component_id=str(data["_id"]) if data["_id"] is not None else data["_id"],
            build_id=str(data["build_id"]),
            name=str(data["name"]),
            platform=str(data["platform"]),
            files=[File.load(f, store=store) for f in data["files"]],
            sources=[File.load(f, store=store) for f in data["sources"]],
            releases=data["releases"],
            creation_date=dateutil_parser.parse(data["creation_date"]),
            attachments=attachments,
            version=str(data["version"]),
            specname=data.get("specname"),
            is_valid=bool(data["is_valid"]),
            readme=readme,
            is_published=bool(data["is_published"]),
            build_info=build_info,
            store=store,
        )

    @classmethod
    def latest(
        cls: type[ComponentType],
        store: StoreReadInterface | StoreRWInterface,
        setup: str,
        date: str | None = None,
        platform: str = "all",
        component: str = "all",
        specname: str | None = None,
        build_id: str = "all",
    ) -> list[ComponentType]:
        """Get a list of latest components.

        :param store: a store instance
        :param setup: setup name
        :param date: a build date. If not None then this means that only
            components from a given build date are considered.
        :param platform: a platform name. If set to ```all``` then latest
            component for each platform is returned.
        :param component: a component name. If set to ```all``` then latest
            component for each component name is returned.
        :param specname: the name of the spec that produced the component. If not None
            then this means that only components generated from the given specname are
            considered.
        :param build_id: the build id to use or "all".
        :return: a list of Components
        """
        comps = store.latest_components(
            setup=setup,
            date=date,
            platform=platform,
            component=component,
            specname=specname,
            build_id=build_id,
        )
        return [cls.load(data=comp, store=store) for comp in comps]

    def download(
        self: ComponentType,
        dest_dir: str | None,
        as_name: str | None = None,
        unpack_dir: str | None = None,
        save_metadata: bool = True,
        remove_root_dir: RemoveRootDirType = True,
        unpack_cmd: Callable[..., None] | None = None,
        delete: bool = True,
        ignore: list[str] | None = None,
        tmp_dir_root: str | None = None,
    ) -> bool | None:
        """Download the binary file associated with a component.

        :param dest_dir: directory in which the archive is kept. If None then
            the archive will be downloaded in a temporary location and deleted
            before the function returns. Having both unpack_dir and dest_dir
            set to None will result in a dummy operation.
        :param as_name: if set to None then the resulting filename is the binary
            'name' + an extension. If not None as_name is used instead. The
            extension used is the extension of the filename attribute. If the
            name attribute or as_name already have the same extension as
            filename then the extension won't be repeated twice.
        :param unpack_dir: if not None a call to unpack_archive is done with
            destination set to unpack_dir.
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

        :return: None if there are no binary associated, True if the file has
            been downloaded, or False if the file was already downloaded
        """
        if len(self.files) == 0:
            return None
        if len(self.files) != 1:
            # If we have several files but only one is not marked internal then
            # consider that file. Otherwise, raise an error
            external_files = [f for f in self.files if not f.internal]
            if len(external_files) == 1:
                binary = external_files[0]
            else:
                raise StoreError("cannot download: multiple external files found")
        else:
            binary = self.files[0]

        return binary.download(
            dest_dir=dest_dir,
            as_name=as_name,
            unpack_dir=unpack_dir,
            save_metadata=save_metadata,
            remove_root_dir=remove_root_dir,
            unpack_cmd=unpack_cmd,
            delete=delete,
            ignore=ignore,
            tmp_dir_root=tmp_dir_root,
        )

    def push(self: ComponentType) -> ComponentType:
        """Push the component to store, using self.store to do so.

        This operation requires self.store to be a StoreRWInterface; otherwise,
        this method will crash.

        :raise AttributeError: If self.store is not a StoreRWInterface interface.
        :return: A newly created Component instance of the final component. The current
            instance is also updated accordingly.
        """
        result = self.load(
            data=self.store.submit_component(self.as_dict()), store=self.store  # type: ignore[union-attr]
        )
        self.__update(result)
        return result

    def __update(self: ComponentType, component: Component) -> None:
        """Update this component data.

        This method is used to update the value of the current component from another.

        This is especially used after a component is pushed to our store to update this
        component with the uploaded one, because after pushing a component,
        some internal values may change (for example, a component_id will be
        generated).

        :param component: The component object used to update the current one.
        """
        self.component_id = component.component_id
        self.build_id = component.build_id
        self.name = component.name
        self.platform = component.platform
        self.version = component.version
        self.specname = component.specname
        self.files = component.files
        self.sources = component.sources
        self.readme = component.readme
        self.attachments = component.attachments
        self.releases = component.releases
        self.is_valid = component.is_valid
        self.is_published = component.is_published
        self.build_info = component.build_info
        self.creation_date = component.creation_date

    def __eq__(self: ComponentType, other: object) -> bool:
        """Compare two component object.

        :param other: the other object to compare with the current one.
        :return: False if other is not a component or if other is different to the
            current component.
        """
        if not isinstance(other, self.__class__):
            return False
        for attr_name, attr_val in list(self.__dict__.items()):
            if attr_name == "store":
                # The store attribute does not affect the equality when comparing two
                # components.
                continue
            val = getattr(other, attr_name)
            if val != attr_val:
                logger.debug(
                    f"Component attribute {attr_name!r} differ: "
                    f"other.{attr_name} = {val!r}, self.{attr_name} = {attr_val!r}"
                )
                return False
        return True

    def __ne__(self: ComponentType, other: object) -> bool:
        """Inverse of self.__eq__.

        :return: True if not self.__eq__(other).
        """
        return not self.__eq__(other)
