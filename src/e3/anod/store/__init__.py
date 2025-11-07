from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
import os
import json
import sqlite3
import time
from packaging.version import Version
from typing import TYPE_CHECKING

from e3.event import unique_id
from e3.fs import cp
from e3.log import getLogger
from e3.anod.store.interface import (
    StoreError,
    StoreReadInterface,
    StoreWriteInterface,
    StoreRWInterface,
    LocalStoreInterface,
    _StoreContextManager,
)

if TYPE_CHECKING:
    from typing import Any, Literal, Union

    from e3.anod.store.file import FileDict, ResourceDict
    from e3.anod.store.component import ComponentDict, ComponentAttachmentDict
    from e3.anod.store.buildinfo import BuildInfoDict
    from e3.anod.store.interface import BuildDataDict


logger = getLogger("e3.anod.store")


class _Store(_StoreContextManager):

    if TYPE_CHECKING:
        DB_IDType = Union[str, int]
        DB_BoolType = Union[bool, int]
        DB_OptionalStrType = Union[str, None]
        DB_OptionalIDType = Union[DB_IDType, None]

        # BuildInfo Types

        BuildInfoField = Literal[
            "id", "build_date", "setup", "creation_date", "build_version", "isready"
        ]

        BuildInfoTuple = tuple[
            DB_IDType,  # id
            str,  # build_date
            str,  # setup
            str,  # creation_date
            str,  # build_version
            DB_BoolType,  # isready
        ]

        # Resource Types

        ResourceField = Literal[
            "id",
            "resource_id",
            "path",
            "size",
            "creation_date",
        ]
        ResourceTuple = tuple[
            DB_IDType,  # id
            str,  # resource_id
            str,  # path
            int,  # size
            str,  # creation_date
        ]

        # File Types

        FileField = Literal[
            "id",
            "name",
            "alias",
            "filename",
            "build_id",
            "kind",
            "resource_id",
            "revision",
            "metadata",
            "creation_date",
        ]
        FileTuple = tuple[
            DB_IDType,  # id
            str,  # name
            str,  # alias
            str,  # filename
            DB_IDType,  # build_id
            str,  # kind
            str,  # resource_id
            str,  # revision
            str,  # metadata
            str,  # creation_date
        ]

        # Component Files Types

        ComponentFileField = Literal[
            "id",
            "kind",
            "file_id",
            "component_id",
            "internal",
            "attachment_name",
        ]
        ComponentFileTuple = tuple[
            DB_IDType,  # id
            str,  # kind
            str,  # file_id
            str,  # component_id
            DB_BoolType,  # internal
            DB_OptionalStrType,  # attachment_name
        ]

        # Component Releases Types

        ComponentReleaseField = Literal[
            "id",
            "name",
            "component_id",
        ]
        ComponentReleaseTuple = tuple[
            DB_IDType,  # id
            str,  # name
            DB_IDType,  # file_id
        ]

        # Component Types

        ComponentField = Literal[
            "id",
            "name",
            "platform",
            "version",
            "specname",
            "build_id",
            "creation_date",
            "is_valid",
            "is_published",
            "readme_id",
            "metadata",
        ]
        ComponentTuple = tuple[
            DB_IDType,  # id
            str,  # name
            str,  # platform
            str,  # version
            DB_OptionalStrType,  # specname
            DB_IDType,  # build_id
            str,  # creation_date
            DB_BoolType,  # is_valid
            DB_BoolType,  # is_published
            DB_OptionalIDType,  # readme_id
            str,  # metadata
        ]

        AnyField = Union[
            BuildInfoField,
            ResourceField,
            FileField,
            ComponentFileField,
            ComponentReleaseField,
            ComponentField,
        ]

        AnyFieldSequence = Union[
            Sequence[BuildInfoField],
            Sequence[ResourceField],
            Sequence[FileField],
            Sequence[ComponentFileField],
            Sequence[ComponentReleaseField],
            Sequence[ComponentField],
        ]

        AnyTuple = Union[
            BuildInfoTuple,
            ResourceTuple,
            FileTuple,
            ComponentFileTuple,
            ComponentReleaseTuple,
            ComponentTuple,
        ]

        AnyTupleList = Union[
            list[BuildInfoTuple],
            list[ResourceTuple],
            list[FileTuple],
            list[ComponentFileTuple],
            list[ComponentReleaseTuple],
            list[ComponentTuple],
        ]

    class TableName(str, Enum):
        buildinfos = "buildinfos"
        resources = "resources"
        files = "files"
        component_files = "component_files"
        component_releases = "component_releases"
        components = "components"

        # !!! We must replace the default TableName.__str__ Otherwise, we are losing the
        # automatic casting ability, forcing us to use the `value` property.
        #
        # Note: Using the `value` property will ask us to rework the typing of this
        # file.
        __str__ = str.__str__

    def __init__(self, db: os.PathLike[str] | str | None = None) -> None:
        """Initialize the Store class.

        This will create the database and its tables (if needed).

        :param db: A path to the database. If None, a new database is created with the
            name `.store.db`.
        """
        self.db_path = os.fspath(db or ".store.db")
        self.connection = sqlite3.connect(self.db_path)
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_Store.TableName.buildinfos}("
            "    id TEXT NOT NULL PRIMARY KEY,"
            "    build_date TEXT NOT NULL,"
            "    setup TEXT NOT NULL,"
            "    creation_date TEXT NOT NULL DEFAULT("
            "        STRFTIME('%Y-%m-%dT%H:%M:%f+00:00', 'now')"
            "    ),"
            "    build_version TEXT NOT NULL,"
            "    isready INTEGER NOT NULL DEFAULT 0 CHECK(isready in (0, 1))"
            ")"
        )
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_Store.TableName.resources}("
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "    resource_id TEXT NOT NULL UNIQUE,"
            "    path TEXT NOT NULL,"
            "    size INTEGER NOT NULL,"
            "    creation_date TEXT NOT NULL DEFAULT("
            "        STRFTIME('%Y-%m-%dT%H:%M:%f+00:00', 'now')"
            "    )"
            ")"
        )
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_Store.TableName.files}("
            "   id TEXT NOT NULL PRIMARY KEY,"
            "   name TEXT NOT NULL,"
            "   alias TEXT NOT NULL,"
            "   filename TEXT NOT NULL,"
            "   build_id INTEGER NOT NULL,"
            "   kind TEXT NOT NULL,"
            "   resource_id TEXT NOT NULL,"
            "   revision TEXT NOT NULL,"
            "   metadata TEXT NOT NULL,"
            "   creation_date TEXT NOT NULL DEFAULT("
            "       STRFTIME('%Y-%m-%dT%H:%M:%f+00:00', 'now')"
            "   )"
            ")"
        )
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_Store.TableName.component_files}("
            "   id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "   kind TEXT NOT NULL,"
            "   file_id TEXT NOT NULL,"
            "   component_id TEXT NOT NULL,"
            "   internal INTEGER NOT NULL DEFAULT 1 CHECK(internal IN (0, 1)),"
            "   attachment_name TEXT,"
            "   CHECK("
            "       (attachment_name IS NOT NULL AND kind='attachment') "
            "       OR kind IN ('file', 'source')"
            "   )"
            ")"
        )
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_Store.TableName.component_releases}("
            "   id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "   name TEXT NOT NULL,"
            "   component_id TEXT NOT NULL"
            ")"
        )
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_Store.TableName.components}("
            "   id TEXT NOT NULL PRIMARY KEY,"
            "   name TEXT NOT NULL,"
            "   platform TEXT NOT NULL,"
            "   version TEXT NOT NULL,"
            "   specname TEXT,"  # Can be Null
            "   build_id TEXT NOT NULL,"
            "   creation_date TEXT NOT NULL DEFAULT("
            "       STRFTIME('%Y-%m-%dT%H:%M:%f+00:00', 'now')"
            "   ),"
            "   is_valid INTEGER NOT NULL DEFAULT 1 CHECK(is_valid in (0, 1)),"
            "   is_published INTEGER NOT NULL DEFAULT 0 CHECK(is_published in (0, 1)),"
            # Component has at least one file
            "   readme_id TEXT,"
            "   metadata TEXT NOT NULL"
            ")"
        )
        self.connection.commit()

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> _Store:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close commit all changes and close the database connection."""
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def _select(
        self,
        table: _Store.TableName,
        dynamic_where_rules: _Store.AnyFieldSequence,
        dynamic_where_values: Sequence[int | str | None],
        *,
        static_where_rules: Sequence[str] = (),
        order_by: str = "id DESC",
        use_or_filter: bool = False,
    ) -> _Store.AnyTupleList:
        """SELECT sql wrapper.

        This method is used for two purpose:
            - Factorize some code.
            - Allow static checking on table name.

        :param table: The SQL table to read.
        :param dynamic_where_rules: A str sequence to filter the returning value.
            This sequence can contain '?' which will be replaced accordingly with
            data in where_values. This sequence cannot be empty.
        :param dynamic_where_values: A sequence of values that will replace any '?'
            found in dynamic_where_rules. Can be empty if dynamic_where_rules doesn't
            contain any '?'.
        :param static_where_rules: Others where rules, but without any '?' into.
        :param order_by: A field name to determine the select order.
        :param use_or_filter: If multiple where_rules are provide and if this parameter
            is true, use 'OR' to join all rules together, otherwise 'AND' is used.
        :return: A list of tuple.
        """
        where_rules = [f"{tmp}=?" for tmp in dynamic_where_rules]
        where_rules.extend(static_where_rules)

        join_filter = " OR " if use_or_filter else " AND "
        where_clause = join_filter.join(where_rules)

        sql = f"SELECT * FROM {table} "
        if where_clause:
            sql = f"{sql}WHERE {where_clause} "
        sql = f"{sql}ORDER BY {order_by}"

        return self.cursor.execute(sql, dynamic_where_values).fetchall()

    def _select_one(
        self,
        table: _Store.TableName,
        rid: _Store.DB_IDType,
        *,
        field_name: _Store.AnyField = "id",
    ) -> _Store.AnyTuple:
        """SELECT sql wrapper that return only one element.

        This wrapper search for an element with a specific ID on the database.

        :param table: The SQL table to read.
        :param rid: The id to use.
        :param field_name: The 'id' field name in the database.
        :return: A tuple of element.
        :raise anod.store.interface.StoreError: if no or more than one element
            found.
        """
        res = self._select(table, [field_name], [rid])  # type: ignore[arg-type, list-item]
        if not res:
            raise StoreError(f"No element with {field_name}={rid} found")
        if len(res) != 1:
            raise StoreError(  # defensive code
                f"Database corrupted: multiple element with {field_name}={rid} found"
            )
        return res[0]

    @classmethod
    def _tuple_to_buildinfo(cls, req_tuple: _Store.BuildInfoTuple) -> BuildInfoDict:
        """Convert a tuple to a BuildInfoDict.

        :param req_tuple: The result of a database request that should be converted into
            a BuildInfoDict.
        :return: The `dict` representation of a `BuildInfo` object.
        """
        bid, bdate, setup, creation_date, bversion, isready = req_tuple
        return {
            "_id": str(bid),
            "setup": setup,
            "isready": bool(isready),
            "build_date": bdate,
            "creation_date": creation_date,
            "build_version": bversion,
        }

    @classmethod
    def _tuple_to_resource(cls, req_tuple: _Store.ResourceTuple) -> ResourceDict:
        """Convert a tuple to a ResourceDict.

        :param req_tuple: The result of a database request that should be converted into
            a ResourceDict.
        :return: The `dict` representation of a resource.
        """
        _, resource_id, path, size, creation_date = req_tuple
        return {
            "id": resource_id,
            "path": path,
            "size": size,
            "creation_date": creation_date,
        }

    def _tuple_to_file(
        self,
        req_tuple: _Store.FileTuple,
        *,
        resource: ResourceDict | None = None,
        buildinfo: BuildInfoDict | None = None,
        internal: bool | None = None,
    ) -> FileDict:
        """Convert a tuple to a FileDict.

        This method takes optional arguments. These arguments are others pre-calculated
        dict. The goal is to avoid making unnecessary request to the database.

        :param req_tuple: The result of a database request that should be converted into
            a FileDict.
        :param resource: The resource dict linked to this file. If None, this dict is
            retrieved from the database.
        :param buildinfo: The buildinfo dict linked to this file. If None, this dict is
            retrieved from the database.
        :param internal: None if unknown, True if the file is intern to a component,
            False otherwise.
        :return: The `dict` representation of a `File` object.
        """
        (
            fid,
            name,
            alias,
            filename,
            build_id,
            kind,
            resource_id,
            revision,
            metadata,
            _creation_date,
        ) = req_tuple

        # Check that the buildinfo passed is the right one. This is because, when
        # submitting a component, the component buildinfo will be passed to this method.
        #
        # We assume that the component buildinfo will be, most of the time, the same
        # of the associated file buildinfo, allowing us to avoid some call to the
        # database.
        if not buildinfo or buildinfo["_id"] != build_id:
            buildinfo = self._tuple_to_buildinfo(
                self._select_one(_Store.TableName.buildinfos, build_id)  # type: ignore[arg-type]
            )

        if not resource or resource["id"] != resource_id:
            resource = self._tuple_to_resource(
                self._select_one(
                    _Store.TableName.resources, resource_id, field_name="resource_id"  # type: ignore[arg-type]
                )
            )

        if internal is None:
            internal = kind != "binary"

        return {
            "_id": str(fid),
            "kind": kind,
            "name": name,
            "alias": alias,
            "filename": filename,
            "revision": revision,
            "metadata": json.loads(metadata) if metadata else {},
            "build_id": str(build_id),
            "resource_id": resource_id,
            "build": buildinfo,
            "resource": resource,
            "internal": bool(internal),
            "unpack_dir": None,
            "downloaded_as": resource["path"] or None,
        }

    def _tuple_list_to_buildinfo_list(
        self, req_tuples: list[_Store.BuildInfoTuple]
    ) -> list[BuildInfoDict]:
        """Convert a list of tuples into a list of BuildInfoDict.

        :param req_tuples: The list of results of a database request that should be
            converted into a list of BuildInfoDict.
        :return: A list of BuildinfoDict.
        """
        return [self._tuple_to_buildinfo(reqt) for reqt in req_tuples]

    def _tuple_list_to_file_list(
        self,
        req_tuples: list[_Store.FileTuple],
        *,
        buildinfo: BuildInfoDict | None = None,
    ) -> list[FileDict]:
        """Convert a list of tuples into a list of FileDict.

        This method takes optional arguments. These arguments are others
        pre-calculated dict. The goal is to avoid making unnecessary request to the
        database.

        :param req_tuples: The list of results of a database request that should be
            converted into a list of FileDict.
        :param buildinfo: The buildinfo dict linked to these files. If None, this dict
            is retrieved from the database.
        :return: A list of FileDict.
        """
        return [self._tuple_to_file(reqt, buildinfo=buildinfo) for reqt in req_tuples]

    def _select_inner_join(
        self,
        table: _Store.TableName,
        fields: list[tuple[_Store.TableName, _Store.AnyField | Literal["*"]]],
        inner_join: _Store.TableName,
        on: tuple[
            tuple[_Store.TableName, _Store.AnyField],
            tuple[_Store.TableName, _Store.AnyField],
        ],
        dynamic_where_rules: Sequence[tuple[_Store.TableName, _Store.AnyField]],
        dynamic_where_values: Sequence[int | str],
        *,
        static_where_rules: Sequence[str] = (),
        order_by: tuple[_Store.TableName, str] | None = None,
        use_or_filter: bool = False,
    ) -> list[tuple[str | int | None, ...]]:
        """Run a SELECT JOIN request on the database.

        For example, the following call:

        .. code-block:: python

            self._select_inner_join(
                _Store.TableName.files,
                [(_Store.TableName.files, "*")],
                _Store.TableName.component_files,
                (
                    (_Store.TableName.files, "id"),
                    (_Store.TableName.component_files, "file_id"),
                ),
                [
                    (_Store.TableName.component_files, "component_id"),
                    (_Store.TableName.component_files, "kind"),
                ],
                [component_id, kind],
            )

        Result into the following SQL request:

        .. code-block:: sql

            SELECT files.* FROM files
                INNER JOIN component_files ON files.id=component_files.file_id
                WHERE component_files.component_id=? AND component_files.kind=?

        .. note::
            In the previous query, the ‘?’ will be replaced by, in order of encounter,
            <component_id> and <kind>.


        :param table: The database table name.
        :param fields: The list of tuples representing the database fields to retrieve.
            The tuple should first contain the table name of this field, and next the
            field itself.
        :param inner_join: The table name to inner join.
        :param on: The inner join on condition as a tuple of two tuple.
            This condition is restricted to only one "equal" condition and tuples
            inside it have the same format that the fields parameters. Logically, table
            names in this field should be unique.
        :param dynamic_where_rules: See _select.where_rules. The only difference is that
            here, we want a tuple sequence to be able to specify which table the field
            comes from.
        :param dynamic_where_values: See _select.where_values.
        :param static_where_rules: See _select.static_where_rules.
        :param order_by: A tuple of two element. The first element is one of the "INNER
            JOIN" tables and the second the fields to use. For example, if an "INNER
            JOIN" request between buildinfo and files is used, to sort the output
            depending on the buildinfo creation_date field, the value for this param
            should be ("buildinfos", "creation_date").
        :param use_or_filter: See _select.use_or_filter.
        :return: A list of tuples matching the actual database request.
        """
        selected_field = ",".join([f"{tab}.{field}" for tab, field in fields])
        on_cond = f"{on[0][0]}.{on[0][1]}={on[1][0]}.{on[1][1]}"
        where = [f"{tab}.{field}=?" for tab, field in dynamic_where_rules]
        where.extend(static_where_rules)
        where_clause = " OR ".join(where) if use_or_filter else " AND ".join(where)
        order_by_sql = f" ORDER BY {'.'.join(order_by)}" if order_by else ""

        req = self.cursor.execute(
            f"SELECT {selected_field} FROM {table} "  # nosec B608
            f"INNER JOIN {inner_join} ON {on_cond} "
            f"WHERE {where_clause}{order_by_sql}",
            dynamic_where_values,
        )
        return req.fetchall()

    def _list_component_files(
        self,
        kind: Literal["file"] | Literal["source"] | Literal["attachment"],
        component_id: _Store.DB_IDType,
        *,
        component_buildinfo: BuildInfoDict | None = None,
    ) -> list[FileDict] | dict[str, FileDict]:
        """Retrieve the files of a component.

        :param kind: The file kind to retrieve.
        :param component_id: The component id associated to these files.
        :param component_buildinfo: A buildinfo dict to avoid unnecessary call to the
            database.
        :return: A list of files if the kind is not attachment, otherwise return an
            attachment dict.
        """
        is_attachment = kind == "attachment"
        fields: list[tuple[_Store.TableName, _Store.AnyField | Literal["*"]]] = (
            [
                (_Store.TableName.component_files, "attachment_name"),
                (_Store.TableName.component_files, "internal"),
                (_Store.TableName.files, "*"),
            ]
            if is_attachment
            else [
                (_Store.TableName.component_files, "internal"),
                (_Store.TableName.files, "*"),
            ]
        )
        req = self._select_inner_join(
            _Store.TableName.files,
            fields,
            _Store.TableName.component_files,
            (
                (_Store.TableName.files, "id"),
                (_Store.TableName.component_files, "file_id"),
            ),
            [
                (_Store.TableName.component_files, "component_id"),
                (_Store.TableName.component_files, "kind"),
            ],
            [component_id, kind],
        )
        res: dict[str, FileDict] | list[FileDict]
        if is_attachment:
            res = {}
            for req_tuple in req:
                assert (
                    len(req_tuple) >= 1
                ), "Should never occur: empty database response"
                name, internal, *file_tuple = req_tuple
                # We are sure here that 'name' is a string.
                res[name] = self._tuple_to_file(  # type: ignore[index]
                    file_tuple, buildinfo=component_buildinfo, internal=internal  # type: ignore[arg-type]
                )
        else:
            res = []
            for req_tuple in req:
                internal, *file_tuple = req_tuple
                res.append(
                    self._tuple_to_file(  # type: ignore[index]
                        file_tuple, buildinfo=component_buildinfo, internal=internal  # type: ignore[arg-type]
                    )
                )
        return res

    def _tuple_to_comp(
        self,
        req_tuple: _Store.ComponentTuple,
        *,
        releases: list[str] | None = None,
        files: list[FileDict] | None = None,
        sources: list[FileDict] | None = None,
        attachments: dict[str, FileDict] | None = None,
        readme: FileDict | None = None,
        buildinfo: BuildInfoDict | None = None,
    ) -> ComponentDict:
        """Convert a tuple to component.

        Optional parameters are only used to avoid unnecessary call to the database.

        :param req_tuple: The tuple to convert.
        :param releases: A list of releases linked to the component.
        :param files: A list of files.
        :param sources: A list of sources.
        :param attachments: An attachment dict.
        :param readme: A FileDict.
        :param buildinfo: A BuildInfoDict.
        """
        _unused_values: object
        (
            comp_id,
            name,
            platform,
            version,
            specname,
            build_id,
            creation_date,
            is_valid,
            is_published,
            readmeid,
            metadata,
            *_unused_values,
        ) = req_tuple

        # If no buildinfo is provided or a wrong one, retrieve the correct buildinfo
        # for this component.
        if not buildinfo or buildinfo["_id"] != build_id:
            buildinfo = self._tuple_to_buildinfo(
                self._select_one(_Store.TableName.buildinfos, build_id)  # type: ignore[arg-type]
            )

        # If no releases is provided, retrieve the correct releases for this component.
        if releases is None:
            releases = [  # type: ignore[misc]
                name
                for _, name, _ in self._select(
                    _Store.TableName.component_releases, ["component_id"], [comp_id]  # type: ignore[arg-type]
                )
            ]

        return {
            "_id": str(comp_id),
            "name": name,
            "platform": platform,
            "version": version,
            "specname": specname,
            "releases": releases,
            "build_id": str(build_id),
            "creation_date": creation_date,
            "is_valid": bool(is_valid),
            "is_published": bool(is_published),
            "files": (
                files  # type: ignore[typeddict-item]
                if files is not None
                else self._list_component_files("file", comp_id)
            ),
            # Retrieve component sources if sources is not provided
            "sources": (
                sources  # type: ignore[typeddict-item]
                if sources is not None
                else self._list_component_files(
                    "source", comp_id, component_buildinfo=buildinfo
                )
            ),
            # Retrieve component readme if readme is not provided
            "readme": (
                readme
                or (
                    self._tuple_to_file(
                        self._select_one(_Store.TableName.files, readmeid),  # type: ignore[arg-type]
                        buildinfo=buildinfo,
                    )
                    if readmeid
                    else None
                )
            ),
            # Retrieve component attachments if attachments is not provided
            "attachments": (
                attachments  # type: ignore[typeddict-item]
                if attachments is not None
                else self._list_component_files(
                    "attachment", comp_id, component_buildinfo=buildinfo
                )
            )
            or None,
            "build": buildinfo,
            "metadata": json.loads(metadata) if metadata else {},
        }

    def _tuple_list_to_comp_list(
        self, req_tuples: list[_Store.ComponentTuple]
    ) -> list[ComponentDict]:
        """Convert a list of tuples into a list of ComponentDict.

        :param req_tuples: The list of tuples to convert.
        :return: A list a ComponentDict.
        """
        return [self._tuple_to_comp(reqt) for reqt in req_tuples]


class _StoreWrite(_Store):
    def _insert_or_update(
        self, table: _Store.TableName, sql: str, values: list[str | int | None]
    ) -> _Store.AnyTuple:
        """Execute an INSERT or UPDATE statement.

        This method will take care of the returning value of this statement.
        If Sqlite version >= 3.35, the code will add the RETURNING keyword to the
        request. Otherwise, an additional select statement is done to retrieve
        the value inserted or updated.

        :param table: The table name.
        :param sql: The sql statement to execute.
        :param values: The values used to fill the potential '?' in the sql statement.
        :return: A tuple.
        """
        # Coverage here is not really relevant because one of these branch will never
        # be executed, depending on the sqlite_version used.
        if Version(sqlite3.sqlite_version) >= Version("3.35"):  # pragma: no cover
            sql += " RETURNING *"
            res = self.cursor.execute(sql, values).fetchone()
        else:  # pragma: no cover
            self.cursor.execute(sql, values)
            if self.cursor.lastrowid is None:
                raise StoreError("sqlite3.cursor.lastrowid return unexpected None")
            res = self._select_one(table, self.cursor.lastrowid)
        return res

    def _insert(
        self,
        table: _Store.TableName,
        fields: _Store.AnyFieldSequence,
        values: list[str | int | None],
    ) -> _Store.AnyTuple:
        """Insert a new row in a table.

        :param table: The table name.
        :param fields: The fields to file in the row.
        :param values: The values to insert.
        :return: A tuple.
        """
        return self._insert_or_update(
            table,
            f"INSERT INTO {table}({','.join(fields)}) "
            f"VALUES({','.join(['?'] * len(fields))})",
            values,
        )

    def _update(
        self,
        table: _Store.TableName,
        rowid: str | int,
        toset: _Store.AnyFieldSequence,
        values: list[str | int | None],
    ) -> _Store.AnyTuple:
        """Update a row in a table.

        :param table: The table name.
        :param rowid: The row id to update.
        :param toset: The list of row fields to update.
        :param values: The values to update.
        :return: A tuple.
        """
        elm_to_set = [f"{tmp}=?" for tmp in toset]
        return self._insert_or_update(
            table,
            f"UPDATE {table} SET {','.join(elm_to_set)} WHERE id=?",
            values + [rowid],
        )


class StoreWriteOnly(_StoreWrite, StoreWriteInterface):
    def create_thirdparty(self, file_info: FileDict) -> FileDict:
        """See e3.anod.store.interface.StoreWriteInterface."""
        file_info["kind"] = "thirdparty"
        file_info["revision"] = ""
        return self.submit_file(file_info)

    def _insert_to_component_files(
        self,
        kind: Literal["file"] | Literal["source"] | Literal["attachment"],
        file_list: Sequence[tuple[str | None, FileDict]],
        component_id: str | int,
    ) -> None:
        """Insert a list of files to the component_files database table.

        :param kind: The kind of file to insert.
        :param file_list: A sequence of tuples. The first element of this tuple must
            be None if the kind != attachment. Otherwise, this represents the
            attachment name. The second element should always be a FileDict.
        :param component_id: The component id linked to these files.
        """
        for att_name, f in file_list:
            internal = f.get("internal", True)
            if internal is None:
                internal = True
            self._insert(
                _Store.TableName.component_files,
                ["kind", "file_id", "component_id", "internal", "attachment_name"],  # type: ignore[arg-type]
                [kind, f["_id"], component_id, internal, att_name],
            )

    def submit_component(self, component_info: ComponentDict) -> ComponentDict:
        """See e3.anod.store.interface.StoreWriteInterface."""
        # Upload only readmes, binaries and attachments, as sources are supposed to be
        # already there.

        # Retrieve readme and upload it.
        readme_id = None

        readme = component_info.get("readme")
        if readme:
            readme = self._submit_file(readme)
            readme_id = readme["_id"]

        # Retrieve binaries an upload them.
        files = [self._submit_file(file_info) for file_info in component_info["files"]]

        # Retrieve attachments and upload them.
        attachments_with_name: dict[str, FileDict] = {}

        attachments: dict[str, FileDict] | Sequence[ComponentAttachmentDict] | None
        attachments = component_info.get("attachments")

        if attachments:
            if isinstance(attachments, dict):
                for name, file_dict in attachments.items():
                    attachments_with_name[name] = self._submit_file(file_dict)
            # The Component dict ask for a list in that case, however, from this code
            # point of view, we only need an implementation of __contains__ and
            # __iter__, having a list, a tuple or a set doesn't matter here.
            elif isinstance(attachments, Sequence):
                for att in attachments:
                    if att["name"] in attachments_with_name:
                        raise StoreError("Two attachments cannot use the same name")
                    attachments_with_name[att["name"]] = self._submit_file(
                        att["att_file"]
                    )
            else:
                raise TypeError(
                    "Unknown attachments type: expected Sequence or dict, "
                    f"got {type(attachments)}"
                )

        # The buildinfo should already be created at this point. If not, raise an error.
        component_build_id = component_info.get("build", {}).get(
            "_id", component_info.get("build_id")
        )
        if not component_build_id:
            raise StoreError("No build id associate with the component to submit")

        # Insert the component itself.
        req_tuple = self._insert(
            _Store.TableName.components,
            [  # type: ignore[arg-type]
                "id",
                "name",
                "platform",
                "version",
                "specname",
                "build_id",
                "is_valid",
                "is_published",
                "readme_id",
                "metadata",
            ],
            [
                unique_id(),
                component_info["name"],
                component_info["platform"],
                component_info["version"],
                component_info.get("specname"),
                component_build_id,
                int(component_info.get("is_valid", True)),
                int(component_info.get("is_published", False)),
                readme_id or None,
                (
                    json.dumps(component_info["metadata"])
                    if component_info.get("metadata")
                    else "{}"
                ),
            ],
        )
        # Create relation between files/sources/attachment and the new component.
        comp_id = req_tuple[0]
        self._insert_to_component_files("file", [(None, f) for f in files], comp_id)
        sources = component_info["sources"]
        self._insert_to_component_files(
            "source", [(None, src) for src in sources], comp_id
        )
        self._insert_to_component_files(
            "attachment", list(attachments_with_name.items()), comp_id
        )
        # Add the list of releases linked to this component.
        #   Note: The releases key can be present, but set to None.
        releases_list = component_info.get("releases") or []
        for release in releases_list:
            self._insert(
                _Store.TableName.component_releases,
                ["name", "component_id"],  # type: ignore[arg-type]
                [release, comp_id],
            )

        # Commit all changes
        self.connection.commit()

        return self._tuple_to_comp(
            req_tuple,  # type: ignore[arg-type]
            releases=releases_list,
            files=files,
            sources=sources,
            attachments=attachments_with_name,
            readme=readme,
            buildinfo=component_info.get("build"),
        )

    def submit_file(self, file_info: FileDict) -> FileDict:
        """See e3.anod.store.interface.StoreWriteInterface."""
        res = self._submit_file(file_info)
        self.connection.commit()
        return res

    def mark_build_ready(self, bid: str) -> bool:
        """See e3.anod.store.interface.StoreWriteInterface."""
        _, _, _, _, isready, *_ = self._update(
            _Store.TableName.buildinfos, bid, ["isready"], [1]  # type: ignore[arg-type, misc]
        )
        self.connection.commit()
        return bool(isready)

    def create_build_id(self, setup: str, date: str, version: str) -> BuildInfoDict:
        """See e3.anod.store.interface.StoreWriteInterface."""
        req_tuple = self._insert(
            _Store.TableName.buildinfos,
            ["id", "build_date", "setup", "build_version"],  # type: ignore[arg-type]
            [unique_id(), date, setup, version],
        )
        self.connection.commit()
        return self._tuple_to_buildinfo(req_tuple)  # type: ignore[arg-type]

    def copy_build_id(self, bid: str, dest_setup: str) -> BuildInfoDict:
        """See e3.anod.store.interface.StoreWriteInterface."""
        req_tuple = self._insert_or_update(
            _Store.TableName.buildinfos,
            f"INSERT INTO {_Store.TableName.buildinfos}("
            "   id, build_date, setup, build_version"
            ") "
            "  SELECT ?, build_date, ?, build_version"
            f"       FROM {_Store.TableName.buildinfos} WHERE id=?",
            [unique_id(), dest_setup, bid],
        )
        self.connection.commit()
        return self._tuple_to_buildinfo(req_tuple)  # type: ignore[arg-type]

    def update_file_metadata(self, file_info: FileDict) -> FileDict:
        """See e3.anod.store.interface.StoreWriteInterface."""
        # Retrieve Buildinfo. At this point of the code, it should be already created.
        buildinfo = file_info.get("build")
        build_id = file_info.get("build_id", buildinfo["_id"] if buildinfo else None)
        if not build_id:
            raise StoreError("No build id associate to this file")

        if buildinfo and build_id != buildinfo["_id"]:
            raise StoreError("Malformed file: build_id field != build._id")

        # Ensure the current file is already uploaded.
        fid = file_info.get("_id")
        if not fid:
            raise StoreError("Cannot update a non uploaded file: id field missing")

        # Update its metadata
        req_tuple = self._update(
            _Store.TableName.files,
            fid,
            ["metadata"],  # type: ignore[arg-type]
            [json.dumps(file_info["metadata"]) if file_info["metadata"] else "{}"],
        )
        self.connection.commit()
        return self._tuple_to_file(req_tuple, buildinfo=buildinfo)  # type: ignore[arg-type]

    def _add_component_attachment(
        self, component_id: str, file_id: str, name: str
    ) -> None:
        """See e3.anod.store.interface.StoreWriteInterface."""
        self._insert(
            _Store.TableName.component_files,
            ["kind", "file_id", "component_id", "attachment_name"],  # type: ignore[arg-type]
            ["attachment", file_id, component_id, name],
        )

    def add_component_attachment(
        self, component_id: str, file_id: str, name: str
    ) -> None:
        """See e3.anod.store.interface.StoreWriteInterface."""
        self._add_component_attachment(component_id, file_id, name)
        self.connection.commit()

    ### PRIVATE ###

    def _submit_file(self, file_info: FileDict) -> FileDict:
        """Private method.

        Same as self.submit_file except that it does not commit the change.
        Mainly for optimization purpose.
        """
        downloaded_as = file_info.get("downloaded_as", "")
        resource_id = file_info.get("resource_id", "")

        if not downloaded_as:
            raise StoreError("Trying to submit file without 'downloaded_as' field")
        if not resource_id:
            raise StoreError("Trying to submit file without 'resource_id' field")

        resource_path = os.path.abspath(downloaded_as)
        if not os.path.isfile(resource_path):
            raise StoreError(f"{resource_path}: not found or is not a file")

        resource_tmp = self._select(
            _Store.TableName.resources, ["resource_id"], [resource_id]  # type: ignore[arg-type]
        )
        if resource_tmp:
            rid, resource_id, path, *rest = resource_tmp[0]
            # Check if the path is still valid, if not, we got a new valid path,
            # so we just need to update the database.
            if not os.path.isfile(path):
                self._update(
                    _Store.TableName.resources, rid, ["path"], [resource_path]  # type: ignore[arg-type]
                )
                path = resource_path
            resource = self._tuple_to_resource(tuple([rid, resource_id, path] + rest))  # type: ignore[arg-type, operator]
        else:  # Create the resource entry
            resource = self._tuple_to_resource(
                self._insert(  # type: ignore[arg-type]
                    _Store.TableName.resources,
                    ["resource_id", "path", "size"],  # type: ignore[arg-type]
                    [
                        resource_id,
                        resource_path,
                        os.stat(resource_path).st_size,
                    ],
                )
            )

        # Create the file entry
        req_tuple = self._insert(
            _Store.TableName.files,
            [  # type: ignore[arg-type]
                "id",
                "name",
                "alias",
                "filename",
                "build_id",
                "kind",
                "resource_id",
                "revision",
                "metadata",
            ],
            [
                unique_id(),
                file_info["name"],
                file_info["alias"],
                file_info["filename"],
                file_info["build_id"],
                file_info["kind"],
                resource_id,
                file_info["revision"],
                json.dumps(file_info["metadata"]) if file_info["metadata"] else "{}",
            ],
        )
        res = self._tuple_to_file(req_tuple, resource=resource)  # type: ignore[arg-type]
        res["downloaded_as"] = file_info["downloaded_as"]
        return res


class StoreReadOnly(_Store, StoreReadInterface):
    def get_build_info(self, bid: str) -> BuildInfoDict:
        """See e3.anod.store.interface.StoreReadInterface."""
        return self._get_buildinfo(["id"], [bid], only_one=True)

    def get_latest_build_info(
        self,
        setup: str,
        date: str | None = "all",
        version: str | None = "all",
        ready_only: bool = True,
    ) -> BuildInfoDict:
        """See e3.anod.store.interface.StoreReadInterface."""
        dyn_where_rules: list[_Store.BuildInfoField] = ["setup"]
        dyn_where_values: list[str] = [setup]
        static_where_rules: list[str] = []

        if date and date != "all":
            dyn_where_rules.append("build_date")
            dyn_where_values.append(date)
        if version and version != "all":
            dyn_where_rules.append("build_version")
            dyn_where_values.append(version)
        if ready_only:
            static_where_rules.append("isready=1")

        return self._get_buildinfo(
            dyn_where_rules,
            dyn_where_values,
            static_where_rules=static_where_rules,
            only_one=False,
        )

    def list_release_components(
        self,
        name: str,
        component: str = "all",
        version: str = "all",
        platform: str = "all",
    ) -> list[ComponentDict]:
        """See e3.anod.store.interface.StoreReadInterface."""
        res = self._tuple_list_to_comp_list(
            self._select_inner_join(  # type: ignore[arg-type]
                _Store.TableName.component_releases,
                [(_Store.TableName.components, "*")],
                _Store.TableName.components,
                (
                    (_Store.TableName.component_releases, "component_id"),
                    (_Store.TableName.components, "id"),
                ),
                [(_Store.TableName.component_releases, "name")],
                [name],
            )
        )

        if (
            (component and component != "all")
            or (version and version != "all")
            or (platform and platform != "all")
        ):
            res = [
                elm
                for elm in res
                if not (
                    (component and component != "all" and elm["name"] != component)
                    or (version and version != "all" and elm["version"] != version)
                    or (platform and platform != "all" and elm["platform"] != platform)
                )
            ]
        return res

    def latest_components(
        self,
        setup: str,
        date: str | None = None,
        platform: str = "all",
        component: str = "all",
        specname: str | None = None,
        build_id: str = "all",
    ) -> list[ComponentDict]:
        """See e3.anod.store.interface.StoreReadInterface."""
        where_rules = [f"{_Store.TableName.buildinfos}.setup=?"]
        where_values = [setup]
        if date and date != "all":
            where_rules.append(f"{_Store.TableName.buildinfos}.build_date=?")
            where_values.append(date)
        if component and component != "all":
            where_rules.append(f"{_Store.TableName.components}.name=?")
            where_values.append(component)
        if platform and platform != "all":
            where_rules.append(f"{_Store.TableName.components}.platform=?")
            where_values.append(platform)
        if specname and specname != "all":
            where_rules.append(f"{_Store.TableName.components}.specname=?")
            where_values.append(specname)
        if build_id and build_id != "all":
            where_rules.append(f"{_Store.TableName.components}.build_id=?")
            where_values.append(build_id)

        # Return "unique" component (aka: Only one component for a given name/platform)
        #
        # The "Readable" SQL request:
        #
        #   WITH latest_components AS (
        #       SELECT components.*, ROW_NUMBER() OVER (
        #           PARTITION BY components.name
        #           ORDER BY components.creation_date DESC
        #       ) AS lc
        #       FROM components
        #       INNER JOIN buildinfos
        #       ON components.build_id=buildinfos.id
        #       WHERE {' AND '.join(where_rules)}
        #   )
        #   SELECT * FROM latest_components WHERE lc=1 ORDER BY creation_date DESC
        return self._tuple_list_to_comp_list(
            self.cursor.execute(
                "WITH latest_components AS ("  # nosec: B608
                f"SELECT {_Store.TableName.components}.*, ROW_NUMBER() OVER ("
                "PARTITION BY "
                f"{_Store.TableName.components}.name, "
                f"{_Store.TableName.components}.platform "
                f"ORDER BY {_Store.TableName.components}.creation_date DESC"
                ") AS lc "
                f"FROM {_Store.TableName.components} "
                f"INNER JOIN {_Store.TableName.buildinfos} "
                f"ON {_Store.TableName.components}.build_id="
                f"{_Store.TableName.buildinfos}.id "
                f"WHERE {' AND '.join(where_rules)}"
                ")"
                "SELECT * FROM latest_components WHERE lc=1 "
                "ORDER BY creation_date DESC",
                where_values,
            ).fetchall()
        )

    def list_components(
        self,
        bid: str,
        component: str = "all",
        platform: str = "all",
    ) -> list[ComponentDict]:
        """See e3.anod.store.interface.StoreReadInterface."""
        where_rules: list[_Store.ComponentField] = ["build_id"]
        where_values: list[str] = [bid]
        if component and component != "all":
            where_rules.append("name")
            where_values.append(component)
        if platform and platform != "all":
            where_rules.append("platform")
            where_values.append(platform)
        return self._tuple_list_to_comp_list(
            self._select(_Store.TableName.components, where_rules, where_values)  # type: ignore[arg-type]
        )

    def get_build_data(self, bid: str) -> BuildDataDict:
        """See e3.anod.store.interface.StoreReadInterface."""
        fields: list[Literal["build_id"]] = ["build_id"]
        return {
            "sources": self._tuple_list_to_file_list(
                self._select(  # type: ignore[arg-type]
                    _Store.TableName.files,
                    fields,
                    [bid],
                    static_where_rules=["kind IN ('source', 'thirdparty')"],
                    order_by="creation_date DESC",
                )
            ),
            "components": self._tuple_list_to_comp_list(
                self._select(
                    _Store.TableName.components,
                    fields,
                    [bid],
                    order_by="creation_date DESC",  # type: ignore[arg-type]
                )
            ),
        }

    def get_build_info_list(
        self,
        date: str | None = "all",
        setup: str | None = "all",
        version: str | None = "all",
        nb_days: int = 1,
    ) -> list[BuildInfoDict]:
        """See e3.anod.store.interface.StoreReadInterface.get_build_info_list."""
        date = date or "all"

        static_where_rules: tuple[str, ...]
        if not date or date == "all":
            static_where_rules = ()
        else:
            assert len(date) == 8
            year = date[:4]
            month = date[4:6]
            day = date[6:8]

            date = f"{year}-{month}-{day}"

            static_where_rules = (
                "(substr(build_date, 1, 4) || '-' || substr(build_date, 5, 2) || '-' "
                "|| substr(build_date, 7, 2)) "
                f"BETWEEN date('{date}', '-' || '{nb_days}' || ' days') "
                f"AND date('{date}')",
            )

        setup = setup or "all"
        version = version or "all"

        where_rules: list[_Store.BuildInfoField] = []
        where_values: list[str] = []

        if setup != "all":
            where_rules.append("setup")
            where_values.append(setup)
        if version != "all":
            where_rules.append("build_version")
            where_values.append(version)

        return self._tuple_list_to_buildinfo_list(
            self._select(  # type: ignore[arg-type]
                _Store.TableName.buildinfos,
                dynamic_where_rules=where_rules,
                dynamic_where_values=where_values,
                static_where_rules=static_where_rules,
            )
        )

    def get_source_info(
        self,
        name: str,
        bid: str,
        kind: str = "source",
    ) -> FileDict:
        """See e3.anod.store.interface.StoreReadInterface."""
        # When looking for sources (kind="source"), the build ID doesn't matter that
        # much.
        #
        # New sources should be generated when a change occur, and so may not be
        # linked to a "today" build id.
        #
        # To deal with that, the build id is used as a limit. We are looking for source
        # that match the current build id or that have been generated BEFORE the
        # current build ID.
        #
        # The SQL request to make:
        #
        #   SELECT files.* INNER JOIN buildinfos
        #   ON buildinfos.id=files.build_id
        #   WHERE files.name={name} AND files.kind={kind} AND (
        #       files.build_id={bid} OR (
        #           files.kind='source' AND buildinfos.creation_date <= (
        #               SELECT creation_date FROM buildinfos WHERE id={bid}
        #           )
        #       )
        #   )
        #
        # Note: According to the presented SQL query, the INNER JOIN is useless when
        # kind is not equal to "source". This doesn't matter because SQLite will
        # optimize the request and will not check the buildinfos table in that case.
        req = self._select_inner_join(
            table=_Store.TableName.files,
            fields=[(_Store.TableName.files, "*")],
            inner_join=_Store.TableName.buildinfos,
            on=(
                (_Store.TableName.buildinfos, "id"),
                (_Store.TableName.files, "build_id"),
            ),
            dynamic_where_rules=[
                (_Store.TableName.files, "name"),
                (_Store.TableName.files, "kind"),
            ],
            dynamic_where_values=[name, kind, bid, bid],
            static_where_rules=[
                f"({_Store.TableName.files}.build_id=? "
                f"OR ({_Store.TableName.files}.kind IN ('source', 'thirdparty') "
                f"AND {_Store.TableName.buildinfos}.creation_date <= ("
                f"SELECT creation_date FROM {_Store.TableName.buildinfos} WHERE id=?)))"
            ],
            order_by=(_Store.TableName.buildinfos, "creation_date DESC"),
        )
        if not req:
            raise StoreError(f"File({name=}, {kind=}, {bid=}) not found")
        return self._tuple_to_file(req[0])  # type: ignore[arg-type]

    def download_resource(self, rid: str, path: str) -> str:
        """See e3.anod.store.interface.StoreReadInterface."""
        _, _, resource_path, *rest = self._select_one(
            _Store.TableName.resources, rid, field_name="resource_id"
        )
        cp(resource_path, path)  # type: ignore[arg-type]
        return os.path.abspath(path)

    def latest_thirdparty(
        self, name: str, tp_id: str = "all", rid: str = "all"
    ) -> FileDict | None:
        """See e3.anod.store.interface.StoreReadInterface."""
        return self._get_file(
            name=name,
            kind="thirdparty",
            fid=tp_id,
            rid=rid,
            possibly_empty=True,
        )

    def bulk_query(self, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """See e3.anod.store.interface.StoreReadInterface."""
        results = []
        for query in queries:
            result = {"query": query, "response": None, "msg": ""}

            if "query" not in query:
                result["msg"] = "Invalid query: missing 'query' key"

            elif query["query"] == "component":
                MANDATORY_KEYS = frozenset(("setup", "platform", "name"))
                if not all(query.get(key) for key in MANDATORY_KEYS):
                    result["msg"] = (
                        "Invalid component query: "
                        f"one or more mandatory keys ({', '.join(MANDATORY_KEYS)}) is "
                        f"missing from query {query}"
                    )
                else:
                    try:
                        components = self.latest_components(
                            setup=query["setup"],
                            date=query.get("date"),
                            platform=query["platform"],
                            component=query["name"],
                        )
                    except Exception as e:
                        result["msg"] = str(e)
                    else:
                        if components:
                            result["response"] = components[0]  # type: ignore[assignment]
                        else:
                            result["msg"] = "No component matching criteria"

            elif query["query"] == "source":
                if "name" not in query:
                    result["msg"] = "Invalid source query: missing name"
                else:
                    try:
                        if query.get("kind", "source") == "thirdparty":
                            result["response"] = self.latest_thirdparty(  # type: ignore[assignment]
                                name=query["name"]
                            )
                        else:
                            if "bid" not in query:
                                result["msg"] = "Invalid source query: missing build ID"
                            else:
                                result["response"] = self.get_source_info(  # type: ignore[assignment]
                                    bid=query["bid"], name=query["name"]
                                )
                    except Exception as e:
                        result["msg"] = str(e)
            else:
                result["msg"] = f"Invalid query type {query['query']!r}"

            results.append(result)
        return results

    ### PRIVATE ###

    def _get_file(
        self,
        name: str | None = None,
        fid: str | None = None,
        kind: str | None = None,
        bid: str | None = None,
        rid: str | None = None,
        possibly_empty: bool = False,
    ) -> FileDict | None:
        """Retrieve a file.

        :param name: The file name
        :param fid: The file id
        :param kind: The file kind
        :param bid: The file buildinfo id
        :param rid: The id of the resource of the file
        :param possibly_empty: If true the method can return an empty result. Otherwise,
            if no result is available, this method raises a StoreError.

        :raise anod.store.interface.StoreError: if possibly_empty is False and
            no result is found.
        """
        if (not name or name == "all") and (not fid or fid == "all"):
            raise ValueError("Cannot find file without name or file id")

        where_rules: list[_Store.FileField] = []
        where_values: list[str] = []

        if kind and kind != "all":
            where_rules.append("kind")
            where_values.append(kind)
        if name and name != "all":
            where_rules.append("name")
            where_values.append(name)
        if fid and fid != "all":
            where_rules.append("id")
            where_values.append(fid)
        if bid and bid != "all":
            where_rules.append("build_id")
            where_values.append(bid)
        if rid and rid != "all":
            where_rules.append("resource_id")
            where_values.append(rid)

        file_list = self._select(
            _Store.TableName.files,
            where_rules,
            where_values,
            order_by="creation_date DESC",
        )
        if not file_list:
            if not possibly_empty:
                raise StoreError("No file found")
            return None

        return self._tuple_to_file(file_list[0])  # type: ignore[arg-type]

    def _get_buildinfo(
        self,
        dynamic_where_rules: Sequence[_Store.BuildInfoField],
        dynamic_where_values: Sequence[str],
        *,
        static_where_rules: Sequence[str] = (),
        only_one: bool = True,
    ) -> BuildInfoDict:
        """Retrieve a buildinfo.

        :param dynamic_where_rules: See _Store._select
        :param dynamic_where_values: See _Store._select
        :param static_where_rules: See _Store._select
        :param only_one: If true, no multiple results is allowed.

        :raise anod.store.interface.StoreError: Raises a StoreError if no result
            is found or if only_one is true and more than one result is
            available.
        """
        possible_buildinfos = self._select(
            _Store.TableName.buildinfos,
            dynamic_where_rules,
            dynamic_where_values,
            static_where_rules=static_where_rules,
            order_by="build_date DESC, creation_date DESC",
        )

        if not possible_buildinfos:
            raise StoreError("No buildinfo found")
        if only_one and len(possible_buildinfos) != 1:
            # This error should never occur, or it means that the database is corrupted.
            # Can be tested, but it's not an interesting test so skip this line
            # from the coverage.
            raise StoreError("Too many buildinfo found")  # pragma: no cover
        return self._tuple_to_buildinfo(possible_buildinfos[0])  # type: ignore[arg-type]


class Store(StoreReadOnly):
    pass


class StoreRW(StoreRWInterface, Store, StoreWriteOnly):
    pass


class LocalStore(StoreRW, LocalStoreInterface):
    def __init__(
        self,
        db: os.PathLike[str] | str | None = None,
        online_store: StoreReadInterface | StoreRWInterface | None = None,
    ) -> None:
        """Initialise the LocalStore class.

        :param db: The path to the current sqlite database file.
        :param online_store: A store interface from which data is retrieved if needed.
        """
        super().__init__(db)
        self.online_store = online_store

    def download_resource(
        self,
        resource_id: str,
        path: str,
        *,
        online_store: StoreReadInterface | None = None,
    ) -> str:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.download_resource`
        """
        online_store = online_store or self.online_store

        if online_store is not None:
            return online_store.download_resource(resource_id, path)
        else:
            raise NotImplementedError

    def _raw_add_build_info(self, build_info: BuildInfoDict) -> bool:
        """Private interface method implementation.

        This function will not commit the change to the database automatically. Return
        True if something should be committed.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.raw_add_build_info`

        :return: True if some change should be committed to the dabase, False otherwise.
        """
        tmp = dict(build_info)
        tmp["id"] = build_info["_id"]
        tmp.pop("_id", None)
        try:
            self._insert(
                _Store.TableName.buildinfos,
                list(tmp.keys()),  # type: ignore[arg-type]
                list(tmp.values()),  # type: ignore[arg-type]
            )
        except sqlite3.IntegrityError as err:
            if "UNIQUE constraint failed: buildinfos.id" not in str(err):
                raise err
            return False
        else:
            return True

    def raw_add_build_info(self, build_info: BuildInfoDict) -> None:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.raw_add_build_info`
        """
        if self._raw_add_build_info(build_info):
            self.connection.commit()

    def add_build_info_from_store(
        self, from_store: StoreReadInterface, bid: str
    ) -> None:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.add_build_info_from_store`
        """
        try:
            _ = self.get_build_info(bid)
        except StoreError:
            self.raw_add_build_info(from_store.get_build_info(bid))

    def _raw_add_file(self, file_info: FileDict) -> bool:
        """Private interface method implementation.

        This function will not commit the change to the database automatically. Return
        True if something should be committed.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.raw_add_file`

        :return: True if some change should be committed to the dabase, False otherwise.
        """
        if not file_info.get("metadata"):
            file_info["metadata"] = {}
        if not file_info.get("downloaded_as"):
            file_info["downloaded_as"] = None
        if not file_info.get("unpack_dir"):
            file_info["unpack_dir"] = None

        name = file_info["name"]
        bid = file_info["build_id"]
        kind = file_info["kind"]

        # Check if the file is already in our database.
        try:
            existing_file_info = self.get_source_info(name, bid, kind=kind)
        except StoreError:
            # Not found, we have to insert it.
            pass
        else:
            # The file already exists, so just return.
            file_info.update(existing_file_info)
            return False

        resource_id = file_info["resource_id"]

        # Create the file entry
        self._insert(
            _Store.TableName.files,
            [  # type: ignore[arg-type]
                "id",
                "name",
                "alias",
                "filename",
                "build_id",
                "kind",
                "resource_id",
                "revision",
                "metadata",
                # No creation_date, this is not part of a File representation.
            ],
            [
                file_info["_id"],
                name,
                file_info["alias"],
                file_info["filename"],
                bid,
                kind,
                resource_id,
                file_info["revision"],
                json.dumps(file_info["metadata"]) if file_info["metadata"] else "{}",
            ],
        )
        # As get_source_info looks backward the final build id associated  with the
        # returned source may differ from the one in the request. Be sure to register
        # the build id associated with the source.
        self._raw_add_build_info(file_info["build"])

        downloaded_as = file_info.get("downloaded_as")
        resource_path = os.path.abspath(downloaded_as) if downloaded_as else ""

        resource_tmp = self._select(
            _Store.TableName.resources, ["resource_id"], [resource_id]  # type: ignore[arg-type]
        )
        if resource_tmp:
            row_id, resource_id, path, *rest = resource_tmp[0]
            # Check if the path is still valid, if not, we got a new valid path,
            # so we just need to update the database.
            if os.path.isfile(path):
                resource = self._tuple_to_resource(resource_tmp[0])  # type: ignore[arg-type]
            else:
                resource = self._tuple_to_resource(
                    self._update(
                        _Store.TableName.resources, row_id, ["path"], [resource_path]  # type: ignore[arg-type]
                    )
                )
        else:  # Create the resource entry
            resource = self._tuple_to_resource(
                self._insert(  # type: ignore[arg-type]
                    _Store.TableName.resources,
                    ["resource_id", "path", "size", "creation_date"],  # type: ignore[arg-type]
                    [
                        resource_id,
                        resource_path,
                        os.stat(resource_path).st_size if resource_path else 0,
                        file_info["resource"]["creation_date"],
                    ],
                )
            )

        file_info["resource"] = resource
        if resource["path"]:
            file_info["downloaded_as"] = resource["path"]
        return True

    def raw_add_file(self, file_info: FileDict) -> None:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.raw_add_file`
        """
        if self._raw_add_file(file_info):
            self.connection.commit()

    def add_source_from_store(
        self,
        from_store: StoreReadInterface,
        name: str,
        bid: str | None = None,
        setup: str | None = None,
        date: str = "all",
        kind: Literal["source", "thirdparty"] = "source",
    ) -> None:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.add_source_from_store`
        """
        if not bid:
            assert setup is not None
            bi = from_store.get_latest_build_info(setup=setup, date=date)
            self.raw_add_build_info(bi)
        else:
            try:
                bi = self.get_build_info(bid)
            except StoreError:
                bi = from_store.get_build_info(bid)
                self.raw_add_build_info(bi)

        self.raw_add_file(from_store.get_source_info(name, bi["_id"], kind=kind))

    def _raw_add_component(self, component_info: ComponentDict) -> bool:
        """Private interface method implementation.

        This function will not commit the change to the database automatically. Return
        True if something should be committed.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.raw_add_component`

        :return: True if some change should be committed to the dabase, False otherwise.
        """
        comp_id = component_info["_id"]
        # Check if the component is already in our database.
        try:
            tmp = self._tuple_to_comp(
                self._select_one(Store.TableName.components, comp_id)  # type: ignore[arg-type]
            )
        except StoreError as err:
            if f"No element with id={comp_id} found" not in str(err):
                raise err
        else:
            # The file already exists, so just return.
            component_info.update(tmp)
            return False

        if not comp_id:
            raise StoreError("cannot add a raw component without id")

        for file in (*component_info["files"], *component_info["sources"]):
            self._raw_add_file(file)

        # Retrieve attachments and upload them.
        attachments_with_name: dict[str, FileDict] = {}
        attachments: dict[str, FileDict] | Sequence[ComponentAttachmentDict] | None
        attachments = component_info.get("attachments")
        if attachments:
            if isinstance(attachments, dict):
                for name, file_dict in attachments.items():
                    self._raw_add_file(file_dict)
                    attachments_with_name[name] = file_dict
            # The Component dict ask for a list in that case, however, from this code
            # point of view, we only need an implementation of __contains__ and
            # __iter__, having a list, a tuple or a set doesn't matter here.
            elif isinstance(attachments, Sequence):
                for att in attachments:
                    if att["name"] in attachments_with_name:
                        raise StoreError("Two attachments cannot use the same name")
                    self._raw_add_file(att["att_file"])
                    attachments_with_name[att["name"]] = att["att_file"]
            else:
                raise TypeError(
                    "Unknown attachments type: expected Sequence or dict, "
                    f"got {type(attachments)}"
                )

        # Add the list of releases linked to this component.
        #   Note: The releases key can be present, but set to None.
        releases_list = component_info.get("releases") or []
        for release in releases_list:
            self._insert(
                _Store.TableName.component_releases,
                ["name", "component_id"],  # type: ignore[arg-type]
                [release, comp_id],
            )

        self._raw_add_build_info(component_info["build"])

        component_build_id = component_info.get("build", {}).get(
            "_id", component_info.get("build_id")
        )
        if not component_build_id:
            raise StoreError("No build id associate with the component to submit")

        readme_id = None
        readme = component_info.get("readme")
        if readme:
            self._raw_add_file(readme)
            readme_id = readme["_id"]

        # Insert the component itself.
        self._insert(
            _Store.TableName.components,
            [  # type: ignore[arg-type]
                "id",
                "name",
                "platform",
                "version",
                "specname",
                "build_id",
                "creation_date",
                "is_valid",
                "is_published",
                "readme_id",
                "metadata",
            ],
            [
                component_info["_id"],
                component_info["name"],
                component_info["platform"],
                component_info["version"],
                component_info.get("specname"),
                component_build_id,
                component_info["creation_date"],
                int(component_info.get("is_valid", True)),
                int(component_info.get("is_published", False)),
                readme_id or None,
                (
                    json.dumps(component_info["metadata"])
                    if component_info.get("metadata")
                    else "{}"
                ),
            ],
        )

        # Create relation between files/sources/attachment and the new component.
        self._insert_to_component_files(
            "file", [(None, f) for f in component_info["files"]], comp_id
        )
        sources = component_info["sources"]
        self._insert_to_component_files(
            "source", [(None, src) for src in sources], comp_id
        )
        self._insert_to_component_files(
            "attachment", list(attachments_with_name.items()), comp_id
        )
        # Add the list of releases linked to this component.
        #   Note: The releases key can be present, but set to None.
        releases_list = component_info.get("releases") or []
        for release in releases_list:
            self._insert(
                _Store.TableName.component_releases,
                ["name", "component_id"],  # type: ignore[arg-type]
                [release, comp_id],
            )
        return True

    def raw_add_component(self, component_info: ComponentDict) -> None:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.raw_add_component`
        """
        if self._raw_add_component(component_info):
            self.connection.commit()

    def add_component_from_store(
        self,
        from_store: StoreReadInterface,
        setup: str,
        name: str = "all",
        platform: str = "all",
        date: str | None = None,
        specname: str | None = None,
    ) -> None:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.add_component_from_store`
        """
        comps = from_store.latest_components(
            setup=setup, date=date, component=name, platform=platform, specname=specname
        )
        if not comps:
            raise StoreError(
                "Cannot find any component matching the following criteria: "
                f"{setup=}, {date=}, {name=}, {platform=}, {specname=}"
            )

        for comp in comps:
            self._raw_add_component(comp)
        self.connection.commit()

    def save(self, filename: os.PathLike[str] | str | None = None) -> None:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.save`
        """
        if filename and filename != self.db_path:
            cp(self.db_path, filename)
        # Make sure everything is flushed to the database.
        self.connection.commit()

    def bulk_update_from_store(
        self, from_store: StoreReadInterface, queries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Interface method implementation.

        .. seealso::

            :py:meth:`e3.anod.store.interface.LocalStore.bulk_update_from_store`
        """
        # List of queries done from store
        queries_done = []
        # Track a list of bid we need inside the database
        required_bids = set()

        local_db_results = []

        for unprocessed_query in queries:
            # First do request preprocessing to ensure that the request is valid from a
            # Store point of view.
            query = unprocessed_query
            if unprocessed_query.get("query", "") == "source":
                query = {"kind": "source", "bid": ""}
                query.update(unprocessed_query)

                if not query["bid"] and "setup" in query:
                    try:
                        query["bid"] = from_store.get_latest_build_info(
                            setup=query["setup"], date=query.get("date")
                        )["_id"]
                    except StoreError:
                        pass

                if query.get("bid"):
                    required_bids.add(query["bid"])

            # Then check for entries that are already in the local database
            if query.get("query", "") == "source":
                try:
                    src_info = self.get_source_info(
                        name=query["name"],
                        bid=query["bid"],
                        kind=query["kind"],
                    )
                    # For regular sources consider the query resolved only if
                    # the bid of the returned source correspond to the bid of
                    # the query. For thirdparties source (kind=thirdparty),
                    # checking the presence is enough.
                    if (
                        query["kind"] == "source"
                        and src_info["build"]["_id"] != query["bid"]
                    ):
                        queries_done.append(query)
                    else:
                        local_db_results.append(
                            {"query": query, "msg": "", "response": src_info}
                        )

                except StoreError:
                    # Result is not in the offline db
                    queries_done.append(query)
            else:
                # This is a component query. For the moment we don't know
                # how to cache it.
                queries_done.append(query)

        # Perform online queries

        # Total number of requests
        queries_num = len(queries_done)

        # Compute chunk size and number of chunks
        try:
            chunk_size = int(os.environ.get("E3_CATHOD_BULK_CHUNK_SIZE", "100"))
        except ValueError:
            chunk_size = 100

        if chunk_size <= 0:
            chunk_size = 100

        chunk_num = queries_num // chunk_size + (0 if queries_num % chunk_size else 1)

        logger.info(
            f"Perform {queries_num} queries to Store ({chunk_num} requests of "
            f"size < {chunk_size})"
        )
        all_results = []

        for index, store_queries_chunk in enumerate(
            (
                queries_done[i : i + chunk_size]
                for i in range(0, queries_num, chunk_size)
            )
        ):
            start_time = time.time()
            logger.debug(f" Query chunk {index + 1}/{chunk_num}")
            results = from_store.bulk_query(store_queries_chunk)
            query_time = time.time() - start_time
            logger.debug(f" Query chunk {index + 1}/{chunk_num} time: {query_time}s")
            all_results.extend(results)

            for result in results:
                if result["response"] is None:
                    continue

                if (
                    result["query"].get("query", "") == "source"
                    or result["query"].get("type", "") == "source"
                ):
                    self.raw_add_file(result["response"])
                else:
                    self.raw_add_component(result["response"])

            for required_bid in required_bids:
                self.add_build_info_from_store(from_store, required_bid)
        return all_results + local_db_results
