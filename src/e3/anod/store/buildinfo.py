from __future__ import annotations

from e3.anod.store.component import Component
from e3.anod.store.file import File
from e3.anod.store.interface import StoreError, StoreWriteInterface
from e3.error import E3Error
from datetime import datetime, timedelta, timezone
from e3.log import getLogger
import time
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import TypedDict, TypeVar

    from e3.anod.store.interface import (
        StoreReadInterface,
        StoreRWInterface,
        BuildDataDict,
    )

    BuildInfoType = TypeVar("BuildInfoType", bound="BuildInfo")

    class BuildInfoDict(TypedDict):
        _id: str
        setup: str
        isready: bool
        build_date: str
        creation_date: str
        build_version: str


logger = getLogger("e3.anod.store.buildinfo")


class BuildInfo(object):
    """BuildInfo structure.

    :ivar build_date: The build date.
    :vartype build_date: str
    :ivar setup: The build setup.
    :vartype setup: str
    :ivar creation_date: The build's creation date.
    :vartype creation_date: str
    :ivar id: The build's ID.
    :vartype id: str
    :ivar build_version: The build version. ??? Deserve a better description.
    :vartype build_version: str
    :ivar isready: True if the build is complete and ready to be
        downloaded. False otherwise.
    :vartype isready: bool
    """

    @classmethod
    def load(
        cls: type[BuildInfoType],
        data: BuildInfoDict,
        store: StoreReadInterface | StoreRWInterface | None = None,
    ) -> BuildInfoType:
        """Create a BuildInfo from the result of a Store build info request.

        :param data: The dictionary returned by Store after a build info request.
        :param store: a Store instance
        """
        return cls(
            build_date=str(data["build_date"]),
            setup=str(data["setup"]),
            creation_date=data["creation_date"],
            id=str(data["_id"]),
            build_version=str(data["build_version"]),
            isready=data.get("isready", False),
            store=store,
        )

    def __init__(
        self: BuildInfoType,
        build_date: str,
        setup: str,
        creation_date: str,
        id: str,  # noqa: A002
        build_version: str,
        isready: bool,
        store: StoreReadInterface | StoreRWInterface | None = None,
    ) -> None:
        """Initialize the BuildInfo object.

        :param build_date: Same as the attribute.
        :param setup: Same as the attribute.
        :param creation_date: Same as the attribute.
        :param build_id: Same as the attribute.
        :param build_version: Same as the attribute.
        :param isready: Same as the attribute.
        :param store: a store instance
        """
        self.build_date = build_date
        self.setup = setup
        self.creation_date = creation_date
        self.id = id
        self.build_version = build_version
        self.isready = isready
        self.store = store

    def __str__(self: BuildInfoType) -> str:
        """Convert a buildinfo to a str."""
        return "%-8s | %-16s | %-16s | %s | %s | %s" % (
            self.build_date,
            self.setup,
            self.build_version,
            self.id,
            self.creation_date,
            "ready" if self.isready else "notready",
        )

    def __eq__(self: BuildInfoType, other: object) -> bool:
        """Compare two buildinfo object.

        :param other: the other object to compare with the current one.
        :return: False if other is not a buildinfo or if other is different to the
            current buildinfo.
        """
        if not isinstance(other, self.__class__):
            return False
        for attr_name, attr_val in list(self.__dict__.items()):
            if attr_name == "store":
                # This attribute is not meaningful when comparing two files.
                continue
            if getattr(other, attr_name) != attr_val:
                logger.debug(f"BuildInfo attribute {attr_name!r} is different")
                return False
        return True

    def __ne__(self: BuildInfoType, other: object) -> bool:
        """Inverse of self.__eq__.

        :return: True if not self.__eq__(other).
        """
        return not self.__eq__(other)

    def get_build_data(self: BuildInfoType) -> BuildDataDict:
        """Call self.store.get_build_data.

        :raises AttributeError: If self.store is None.
        :return: Same as StoreReadInterface.get_build_data.
        """
        if not self.store:
            raise AttributeError("self.store is None")
        return self.store.get_build_data(bid=self.id)

    def mark_ready(self: BuildInfoType) -> bool:
        """Call self.store.mark_build_ready.

        :raises AttributeError: If self.store is None or not a StoreWriteInterface.
        :return: True in case of success, False otherwise.
        """
        if not isinstance(self.store, StoreWriteInterface):
            raise AttributeError(
                f"self.store is not a StoreWriteInterface: {type(self.store)}"
            )
        self.isready = self.store.mark_build_ready(bid=self.id)
        return self.isready

    def get_source_list(self: BuildInfoType) -> list[File]:
        """Get the list of source files associated to our BuildInfo object.

        :raises AttributeError: If self.store is None.
        :return: A list of File objects.
        """
        if not self.store:
            raise AttributeError("self.store is None")
        result = self.store.get_build_data(bid=self.id)
        return [File.load(f, store=self.store) for f in result.get("sources", [])]

    def get_source_info(self: BuildInfoType, name: str, kind: str = "source") -> File:
        """Return the File with the given name and kind.

        :param name: the file object name.
        :param kind: the file object kind.
        :raises AttributeError: If self.store is None.
        :return: A File.
        """
        if not self.store:
            raise AttributeError("self.store is None")
        return File.load(
            self.store.get_source_info(bid=self.id, name=name, kind=kind),
            store=self.store,
        )

    def get_component(self: BuildInfoType, name: str, platform: str) -> Component:
        """Get a component for a given build id.

        :param name: component name
        :param platform: platform
        :raises AttributeError: If self.store is None.
        :return: a component
        """
        result = self.get_component_list(name=name, platform=platform)
        if len(result) == 0:
            raise StoreError(f"cannot find component {name} ({platform})")
        elif len(result) != 1:
            raise StoreError(f"multiple component {name} ({platform}) found")
        return result[0]

    def get_component_list(
        self: BuildInfoType, name: str = "all", platform: str = "all"
    ) -> list[Component]:
        """Get a component list for the given build id.

        :param name: component name
        :param platform: platform name
        :raises AttributeError: If self.store is None.
        :return: A list of Component.
        """
        if not self.store:
            raise AttributeError("self.store is None")
        result = self.store.list_components(self.id, component=name, platform=platform)
        return [
            Component.load(data=comp_data, store=self.store) for comp_data in result
        ]

    @classmethod
    def latest(
        cls: type[BuildInfoType],
        store: StoreReadInterface | StoreRWInterface,
        setup: str,
        build_version: str = "all",
        build_date: str | None = "all",
        ready_only: bool = True,
    ) -> BuildInfoType:
        """Find a build.

        :param store: A Store instance.
        :param setup: A setup name.
        :param build_version: The build version.
        :param build_date: The build date, in 'YYYYMMDD' format.
            If None or 'all', the latest BuildInfo with any date
            is selected.
        :param ready_only: If True (default), return only build ids
            that are in a ready state.
        :return: A build object
        """
        return cls.load(
            data=store.get_latest_build_info(
                setup=setup,
                date=build_date,
                version=build_version,
                ready_only=ready_only,
            ),
            store=store,
        )

    @classmethod
    def list(
        cls: type[BuildInfoType],
        store: StoreReadInterface | StoreRWInterface,
        build_date: str = "all",
        setup: str = "all",
        build_version: str = "all",
        nb_days: int = 1,
    ) -> list[BuildInfoType]:
        """Find a build in a date range.

        :param store: Store instance to get build list from.
        :param build_date: build date, in 'YYYYMMDD' format the returned build
            info should match (along with *nb_days*).
        :param setup: setup the returned build info should match.
        :param build_version: version the returned build info should match.
        :param nb_days: maximum number of days to retrieve.

        :return: A build object
        """
        build_info_dicts: list[BuildInfoDict] = store.get_build_info_list(
            setup=setup,
            date=build_date,
            version=build_version,
            nb_days=nb_days,
        )

        return [
            cls.load(build_info_dict, store=store)
            for build_info_dict in build_info_dicts
        ]

    @classmethod
    def create(
        cls: type[BuildInfoType],
        store: StoreRWInterface,
        setup: str,
        version: str,
        date: str | None = None,
        *,
        mark_ready: bool = False,
    ) -> BuildInfoType:
        """Create a new build id.

        :param store: The store instance to use. Must be able to write.
        :param setup: setup name.
        :param version: version.
        :param date: build date.
        :param mark_ready: Mark the buildinfo as ready after creating it.
        """
        if date is None:
            date = cls.today_build_date()

        res = cls.load(
            data=store.create_build_id(setup=setup, date=date, version=version),
            store=store,
        )
        if mark_ready:
            res.mark_ready()
        return res

    @classmethod
    def from_id(
        cls: type[BuildInfoType],
        store: StoreReadInterface | StoreRWInterface,
        build_id: str,
    ) -> BuildInfoType:
        """Return a build object based on its id.

        :param store: Store instance.
        :param build_id: the build id.
        :return: a BuildInfo object.
        """
        return cls.load(data=store.get_build_info(bid=build_id), store=store)

    @classmethod
    def today_build_date(cls: type[BuildInfoType]) -> str:
        """Return the today build date using the YYYYMMDD format.

        The today build date is the current date minus 1 day.
        """
        return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")

    @classmethod
    def wait(
        cls: type[BuildInfoType],
        store: StoreReadInterface | StoreRWInterface,
        setup: str,
        build_date: str | None = None,
        timeout: float = 36000.0,
        retry_delay: float = 60.0,
    ) -> BuildInfoType:
        """Wait until the today buildinfo is available.

        :param store: the store instance used.
        :param setup: the setup of the buildinfo waited.
        :param build_date: the date of the build info to wait for.
        :param timeout: the global amount of time to wait.
        :param retry_delay: the amount of time  to wait before trying again in the loop.
        :return: a buildinfo object.
        :raises E3Error: If the timeout is exceeded.
        """
        if build_date is None:
            build_date = cls.today_build_date()

        start_time = datetime.now(timezone.utc)
        build_info = None

        while build_info is None:
            try:
                build_info = cls.latest(store=store, setup=setup, build_date=build_date)
            except StoreError as e:
                # This is not necessarily an error, as this can also happen
                # when requesting the build info for a setup/date which does
                # not exist (for instance, if it has not been created yet).
                # Nevertheless, log that error; while it may cause the same
                # message to be repeated many times while we wait for
                # the build ID to be created, this message can also be
                # helpful in case of an actual error.
                logger.info(
                    f"Unable to get build_info (setup={setup}, date={build_date}): {e}"
                )

            if build_info is not None:
                break

            if datetime.now(timezone.utc) - start_time > timedelta(seconds=timeout):
                raise E3Error(
                    "timeout while waiting for build_id "
                    f"(setup={setup}, date={build_date})"
                )

            time.sleep(float(retry_delay))

        return build_info

    def copy(
        self: BuildInfoType, dest_setup: str, mark_as_ready: bool = True
    ) -> BuildInfoType:
        """Copy the current build id into another setup.

        Note that only sources elements are copied.

        :param dest_setup: setup of new build id
        :param mark_as_ready: if True mark the resulting build id as ready
        :raises AttributeError: If self.store is None or not a StoreWriteInterface.
        :return: a BuildInfo object
        """
        if not isinstance(self.store, StoreWriteInterface):
            raise AttributeError(
                f"self.store is not a StoreWriteInterface: {type(self.store)}"
            )
        if self.setup == dest_setup:
            raise StoreError(f"Cannot copy into the same setup: {self.setup}")

        data = self.store.copy_build_id(bid=self.id, dest_setup=dest_setup)
        result = self.load(data=data, store=self.store)
        if mark_as_ready:
            result.mark_ready()
        return result

    def as_dict(self: BuildInfoType) -> BuildInfoDict:
        """Return a dictionary representation of self.

        Feeding to this class' "load" method the value returned by
        this method creates a new BuildInfo value that is equal to self.

        :return: The dictionary representation of self.
        """
        return {
            "build_date": self.build_date,
            "setup": self.setup,
            "creation_date": self.creation_date,
            "_id": self.id,
            "build_version": self.build_version,
            "isready": self.isready,
        }

    def to_dict(self: BuildInfoType) -> BuildInfoDict:
        """Return a dictionary representation of self.

        This function is only here for compatibility purpose and will be removed later.

        .. seealso:: py:meth:`as_dict`.
        """
        import warnings

        warnings.warn(
            "`BuildInfo.to_dict` is deprecated, use `BuildInfo.as_dict` instead",
            DeprecationWarning,
        )
        return self.as_dict()
