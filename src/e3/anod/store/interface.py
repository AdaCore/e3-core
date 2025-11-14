from __future__ import annotations

import abc
import os
from typing import TYPE_CHECKING

from e3.error import E3Error
from e3.hash import sha1

if TYPE_CHECKING:
    from typing import Any, TypeVar, TypedDict, Literal

    from e3.anod.store.buildinfo import BuildInfoDict
    from e3.anod.store.component import ComponentDict
    from e3.anod.store.file import FileDict

    StoreContextManagerType = TypeVar(
        "StoreContextManagerType", bound="_StoreContextManager"
    )

    class BuildDataDict(TypedDict):
        sources: list[FileDict]
        components: list[ComponentDict]


class StoreError(E3Error):
    pass


def resource_id(path: os.PathLike[str] | str) -> str:
    """Given a path to a file return the resource id.

    :param path: a path to an existing path
    :return: a resource id
    """
    return sha1(path)


class _StoreContextManager(metaclass=abc.ABCMeta):
    """A class to define the context manager interface needed by a Store class."""

    @abc.abstractmethod
    def __enter__(self: StoreContextManagerType) -> StoreContextManagerType:
        """Enter in a new context.

        This method is called when used with the "with" keyword. For example:

        .. code-block:: python

            with _StoreContextManager() as x:
                pass

        :return: Self
        """

    @abc.abstractmethod
    def __exit__(self, *args: Any) -> None:
        """Exit a context.

        This method is called when exiting a "with" context. For example:

        .. code-block:: python

            with _StoreContextManager() as x:
                pass
            # __exit__ is call here
        """

    @abc.abstractmethod
    def close(self) -> None:
        """Close the current context.

        This method is used to close a context, generally not initiated using the
        `with` keyword. See `builtin.open` for more example.
        """


class StoreReadInterface(_StoreContextManager, metaclass=abc.ABCMeta):
    """A class that defines the Store read interface."""

    @classmethod
    def resource_id(cls, path: str) -> str:
        """Given a path to a file return the resource id.

        :param path: a path to an existing path
        :return: a resource id
        """
        return resource_id(path)

    @abc.abstractmethod
    def list_release_components(
        self,
        name: str,
        component: str = "all",
        version: str = "all",
        platform: str = "all",
    ) -> list[ComponentDict]:
        """List components for a given release name.

        :param name: The release name.
        :param component: A component name or 'all' to match all components.
        :param version: A component version or all to match all version.
        :param platform: A platform name or 'all' to match all platforms.
        :return: a list of component description.
            See e3.anod.store.component.Component.load implementation for the
            description of the expected structure.
        """

    @abc.abstractmethod
    def list_components(
        self,
        bid: str,
        component: str = "all",
        platform: str = "all",
    ) -> list[ComponentDict]:
        """List components for a given build id.

        :param bid: a build id
        :param component: a component name or 'all' to match all components
        :param platform: a platform name or 'all' to match all platforms
        :return: a list of component description.
            See e3.anod.store.component.Component.load implementation for the
            description of the expected structure.
        """

    @abc.abstractmethod
    def latest_components(
        self,
        setup: str,
        date: str | None = None,
        platform: str = "all",
        component: str = "all",
        specname: str | None = None,
        build_id: str = "all",
    ) -> list[ComponentDict]:
        """Get a list of latest components.

        :param setup: the setup name
        :param date: a build date or None
        :param platform: a platform name or 'all' to match all platforms
        :param component: a component name or 'all' to get all components
        :param specname: the name of the spec that generated the component or 'all' to
            include all "generator" specs
        :param build_id: a build id
        :return: a list of component description. See e3.anod.store.file.File.load.
            Note that no error is raised when no component matching the
            criteria is found (an empty list is returned).
        """

    @abc.abstractmethod
    def get_build_data(self, bid: str) -> BuildDataDict:
        """Fetch all data corresponding to a build id.

        :param bid: a build id
        :return: a dict with two keys: 'components' and 'sources'. If
            key as a list associated. See e3.anod.store.file.File.load
            and e3.anod.store.component.Component.load for description of
            the expected structure
        """

    @abc.abstractmethod
    def get_build_info(self, bid: str) -> BuildInfoDict:
        """Get build metadata.

        :param bid: a build id
        :return: a dict with the build metadata. See
            e3.anod.store.buildinfo.BuildInfo.load for description of the
            structure.
        """

    @abc.abstractmethod
    def get_build_info_list(
        self,
        date: str | None = "all",
        setup: str | None = "all",
        version: str | None = "all",
        nb_days: int = 1,
    ) -> list[BuildInfoDict]:
        """Get latest build metadata for the last *nb_days* days.

        :param date: a build date to start lookup from
        :param setup: a setup name
        :param version: a build version or 'all'. None has the same meaning as 'all'
        :param nb_days: maximum number of days to get build information for.
        :return: a dict with the build metadata. See
            e3.anod.store.buildinfo.BuildInfo.load for description of the structure.
        """

    @abc.abstractmethod
    def get_latest_build_info(
        self,
        setup: str,
        date: str | None = "all",
        version: str | None = "all",
        ready_only: bool = True,
    ) -> BuildInfoDict:
        """Get latest build metadata.

        :param setup: a setup name
        :param date: a build date or 'all'. None has the same meaning as 'all'
        :param version: a build version or 'all'. None has the same meaning as 'all'
        :param ready_only: if True discard build that are not marked 'isready'
        :return: a dict with the build metadata.
            See e3.anod.store.buildinfo.BuildInfo.load for description of the
            structure.
        """

    @abc.abstractmethod
    def get_source_info(
        self,
        name: str,
        bid: str,
        kind: str = "source",
    ) -> FileDict:
        """Get source metadata.

        Important note: if the source does not exist for the required bid then
        the latest source with a build id anterior to the requested one will
        be returned for the corresponding setup.

        :param name: The name of the source to get info for.
        :param bid: a build id
        :param kind: source kind. Can be currently 'source' or 'thirdparty'.
        :return: a dict representing a file structure
            (see e3.anod.store.file.File.load)
        """

    @abc.abstractmethod
    def download_resource(self, rid: str, path: str) -> str:
        """Download a resource.

        :param rid: the resource id
        :param path: destination
        :return: absolute path to the downloaded resource
        """

    @abc.abstractmethod
    def latest_thirdparty(
        self, name: str, tp_id: str = "all", rid: str = "all"
    ) -> FileDict | None:
        """Get third party metadata.

        :param name: Third party name.
        :param tp_id: Third party id or 'all'.
        :param rid: Third party resource_id or 'all'.
        :return: a dict representing a file structure or None if the third
            party does not exist. (See e3.anod.store.file.File.load)
        """

    @abc.abstractmethod
    def bulk_query(self, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Perform a list of queries (source and components) to Store.

        Each element of the queries list should conform to the following
        specifications:

        Source queries have the following format:

        .. code-block:: python

           {'query': 'source',
            'name':  'str'  # The name of the File to retrieve
            'kind':  'str'  # 'thirdparty' or 'source' (OPTIONAL)
            'bid':   'str'  #  NECESSARY if kind not is not 'thirdparty'}

        Component queries have the following format:

        .. code-block:: python

           {'query': 'component',
            'platform': 'str',
            'name': 'str',
            'setup': 'str',
            'date': 'str'  # OPTIONAL}

        The answer is a JSON array. Each item has the following format:

           {'query': dict    # A copy of the input query
            'msg':  str      # A message in case of error
            'response': dict # A query answer (a file or component structure)}


        :param queries: a list of queries
        :return: a list of answers
        """


class StoreWriteInterface(object, metaclass=abc.ABCMeta):
    """A class that defines the Store write interface."""

    @abc.abstractmethod
    def create_thirdparty(self, file_info: FileDict) -> FileDict:
        """Upload a new third party.

        :param file_info: a dict representing a file structure.
            (see e3.anod.store.file.File.load)
        :return: a dict representing the final file structure
            (see e3.anod.store.file.File.load)
        """

    @abc.abstractmethod
    def submit_component(self, component_info: ComponentDict) -> ComponentDict:
        """Upload a component to store.

        :param component_info: a dict representing a component
        :return: a dict representing the final component
        """

    @abc.abstractmethod
    def submit_file(self, file_info: FileDict) -> FileDict:
        """Upload a new file to store.

        :param file_info: a dict representing a file structure
        :return: a dict representing the final file structure
        """

    @abc.abstractmethod
    def mark_build_ready(self, bid: str) -> bool:
        """Mark a build id as ready.

        The mechanism is used to synchronize source packaging with
        component builds startup

        :param bid: a build id
        :return: True if success
        """

    @abc.abstractmethod
    def create_build_id(self, setup: str, date: str, version: str) -> BuildInfoDict:
        """Create a new build id.

        :param setup: the setup name
        :param date: the build date of the new build id
        :param version: the version of the new build id
        :return: a build id dict
        """

    @abc.abstractmethod
    def copy_build_id(self, bid: str, dest_setup: str) -> BuildInfoDict:
        """Copy a build id.

        :param bid: a build id
        :param dest_setup: setup destination different from source setup
        :return: a dict representing a build id
        """

    @abc.abstractmethod
    def update_file_metadata(self, file_info: FileDict) -> FileDict:
        """Update file resource metadata.

        :param file_info: a dict representing a file structure
        :return: a dict representing the updated file
        """

    @abc.abstractmethod
    def add_component_attachment(
        self, component_id: str, file_id: str, name: str
    ) -> None:
        """Add an attachment to a component.

        This function attach an ALREADY SUBMITTED file to a component.

        :param component_id: the component id.
        :param file_id: the id of the attachment file.
        :param name: the attachment name.
        """


class StoreRWInterface(StoreReadInterface, StoreWriteInterface):
    pass


class LocalStoreInterface(object, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def raw_add_build_info(self, build_info_data: BuildInfoDict) -> None:
        """Add a build info to the local store.

        :param build_info_data: build info data (i.e: result of BuildInfo.to_dict())
        """
        raise NotImplementedError  # all: no cover

    @abc.abstractmethod
    def add_build_info_from_store(
        self, from_store: StoreReadInterface, bid: str
    ) -> None:
        """Add a build info to the local store from another store instance.

        :param from_store: The other store instance where the buildinfo is retrieve.
        :param bid: The buildinfo ID to retrieve.
        """
        raise NotImplementedError  # all: no cover

    @abc.abstractmethod
    def raw_add_file(self, file_info: FileDict) -> None:
        """Add a file to the local store.

        :param file_info: a file dict (i.e: result of File.as_dict()).
        """
        raise NotImplementedError  # all: no cover

    @abc.abstractmethod
    def add_source_from_store(
        self,
        from_store: StoreReadInterface,
        name: str,
        bid: str | None = None,
        setup: str | None = None,
        date: str = "all",
        kind: Literal["source", "thirdparty"] = "source",
    ) -> None:
        """Add a file info and all associated informations to the db.

        The associated build id is also automatically added.

        .. note::
            If the file information is already present no call to the online store is
            performed.

            This method doesn't retrieve the resource pointed by the added file. Trying
            to download the file without calling `add_resource` will raise an error.

        :param from_store: instance of an online store to query.
        :param name: the source name to retrieve.
        :param bid: a build id.
        :param setup: a setup name.
        :param date: a build date.
        :param kind: kind can be either source or thirdparty.
        """
        raise NotImplementedError  # all: no cover

    @abc.abstractmethod
    def raw_add_component(self, component_info: ComponentDict) -> None:
        """Add a component to the local store.

        :param component_info: a Component dict (i.e: result of Component.to_dict()).
        """
        raise NotImplementedError  # all: no cover

    @abc.abstractmethod
    def add_component_from_store(
        self,
        from_store: StoreReadInterface,
        setup: str,
        name: str = "all",
        platform: str = "all",
        date: str | None = None,
        specname: str | None = None,
    ) -> None:
        """Add a component and all associated informatios to the db.

        The associated build id is also automatically added

        :param from_store: instance of an online store to query.
        :param setup: a setup name.
        :param name: a component name.
        :param platform: a platform name.
        :param date: a build date.
        :param specname: the spec name related to the component.
        """
        raise NotImplementedError  # all: no cover

    @abc.abstractmethod
    def save(self, filename: os.PathLike | None = None) -> None:
        """Save the local store database.

        This function can does nothing and is hightly related to the LocalStore
        implementation.

        :param filename: the file path to save the database.
        """
        raise NotImplementedError  # all: no cover

    @abc.abstractmethod
    def bulk_update_from_store(
        self, from_store: StoreReadInterface, queries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Perform a list of update queries (source and components) to Store.

        Each element of the queries list should conform to the specifications define by
        self.bulk_query.

        This function will populate the LocalStore depending of the queries.

        :param from_store: instance of an online store to query.
        :param queries: a list of queries
        :return: a list of answers
        """
        raise NotImplementedError  # all: no cover
