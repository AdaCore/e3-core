import os

import e3.anod.error
import e3.diff
import e3.log
from e3.archive import create_archive
from e3.fs import VCS_IGNORE_LIST, mkdir, rm, sync_tree


class Package(object):
    """Describe and generate a binary package."""

    def __init__(self, prefix, publish=False, version=None):
        """Create a binary package.

        :param prefix: prefix of the package to create, the name will be
            {prefix}-{version}-{platform}-bin.{exe,tar.gz}
            The version is by default set to 'unknown' and
            can be overridden by the version callback.
        :type prefix: str
        :param publish: if True, publish the package (i.e. the package
            can be distributed to a customer).
        :type publish: bool
        :param version: a callback returning the package version, if None the
            version is set to Anod.sandbox.build_version
        :type version: () -> str | None
        """
        self.prefix = prefix
        self.name = prefix + "-{version}-{platform}-bin"
        self.publish = publish
        self.version = version

    def pkg_name(self, anod_instance):
        """Return the final package filename.

        :param anod_instance: the Anod instance that creates the package
        :type anod_instance: Anod
        :return: the name without extension of the package filename
        :rtype: str
        """
        if self.version is not None:
            version = self.version()
        else:
            version = "unknown"

        return self.name.format(version=version, platform=anod_instance.env.platform)

    def pkg_path(self, anod_instance):
        """Return the full path in which a package will be generated.

        :param anod_instance: the Anod instance that creates the package
        :type anod_instance: Anod
        :return: the full path to the generated archive
        :rtype: str
        """
        return os.path.join(
            anod_instance.build_space.binary_dir, self.pkg_name(anod_instance) + ".zip"
        )

    def create_package(self, anod_instance):
        """Generate a package as a ZIP archive.

        :param anod_instance: the Anod instance that creates the package
        :type anod_instance: Anod
        :return: the full path to the generated archive
        :rtype: str
        """
        pkg_name = self.pkg_name(anod_instance)
        pkg_path = self.pkg_path(anod_instance)

        # Reset binary dir
        rm(anod_instance.build_space.binary_dir, True)
        mkdir(anod_instance.build_space.binary_dir)

        # Create the zip archive
        create_archive(
            filename=os.path.basename(pkg_path),
            from_dir=anod_instance.build_space.pkg_dir,
            dest=os.path.dirname(pkg_path),
            from_dir_rename=pkg_name,
        )
        return pkg_path


class Source(object):
    """Source package."""

    def __init__(
        self,
        name,
        publish,
        dest=None,
        unpack_cmd=None,
        remove_root_dir=True,
        ignore=None,
    ):
        """Create a new source object.

        Register a source package and describe where it should be installed.

        :param name: source package short alias (the full package name will
            be written in the sources metadata)
        :type name: str
        :param publish: whether the source package should be distributed with
            the official releases
        :type publish: bool
        :param dest: subdirectory of the local `src_dir` where to extract the
            source package
        :type dest: str | None
        :param unpack_cmd: the function to call to install the source package
            See gnatpython.fileutils.unpack_archive for more information
        :param remove_root_dir: if True (default) the root directory of the
            archive is ignored
        :type remove_root_dir: bool
        :param ignore: unused during instantiation, kept for backward
            compatibiliy.
        """
        del ignore
        self.name = name
        self.publish = publish
        if dest is None:
            dest = ""
        else:
            if os.path.isabs(dest) or os.pardir in dest:
                raise e3.anod.error.SpecError("dest should be relative path")
        self.dest = dest
        self.unpack_cmd = unpack_cmd
        self.remove_root_dir = remove_root_dir
        self.builder = None
        self.other_sources = None

    def set_builder(self, builder_function):
        """Set the SourceBuilder associated to this Source object."""
        self.builder = builder_function

    def set_other_sources(self, other_sources):
        """Get the list of other sources to compute ``ignore`` property."""
        self.other_sources = other_sources

    @property
    def ignore(self):
        """Return list of paths to ignore when installing the source.

        By default, a source package is first unpacked and then install
        in the `dest` directory by using e3.fs.sync_tree. The ignore
        property returns a value that can be passed to e3.fs.sync_tree.

        :rtype: list[str]
        """
        ignore_list = []
        for other_source in self.other_sources:
            if other_source.name != self.name and other_source.dest:
                ignore_path = os.path.relpath(other_source.dest, self.dest)
                if not ignore_path.startswith(os.pardir):
                    ignore_list.append("/{}".format(ignore_path))
        return ignore_list


class SharedSource(Source):
    """Shared sources are installed directly in the sandbox.

    This is useful when you need to use the same sources for different
    modules/platforms and you don't need to write in the sources
    directory
    """

    pass


class SourceBuilder(object):

    DEFAULT_PATCH_CMD = 1

    def __init__(
        self,
        name,
        fullname,
        checkout,
        prepare_src=None,
        apply_patch=None,
        kind="source",
    ):
        """Define a builder for the source package.

        :param name: short name of the package (as used by build_source_list
            and test_source_list).
        :type name: str
        :param fullname: callback providing the full package name
        :type fullname: () -> str
        :param checkout: list of repository names needed to build the
            source package
        :type checkout: list[str] | None
        :param prepare_src: a function (repo_dict, dest) where
            repo_dict is a dictionary of {repo_name: working directory}
            dest is the path to the dest directory
            If None, just rsync from working directory to dest
            Note that it is supported only if the SourceBuilder object has
            only one Repository object. The repository working directories
            should be considered read only
        :type prepare_src: (dict[str][str], str) -> None | None
        :param apply_patch: a function(repository, patch_file, dest) where
            repository is the name of the repository used to create a patch
            patch_file is a patch to apply
            dest is the path to the dest directory
            If apply_patch is set to DEFAULT_PATCH_CMD, use the default
            apply_patch command
        :type apply_patch: (str, str, str) -> None | None
        :param kind: type of source 'source' or 'thirdparty'
        :type kind: str
        """
        self.name = name
        self.checkout = checkout if checkout is not None else []
        self.repositories = {}
        self.kind = kind
        self.from_spec = None
        self.source_query = None
        self.__fullname = fullname
        self.__prepare_src = prepare_src
        self.__apply_patch = apply_patch

    def fullname(self, *args, **kwargs):
        # ??? add support for the GPL mode
        return self.__fullname(*args, **kwargs)

    @property
    def prepare_src(self):
        """Return the callback used to prepare the source package.

        :return: the callback or None if no prepare_src is defined
        :rtype: (dict[str][str], str) -> None | None
        :raise: SpecError
        """
        if self.__prepare_src is not None:
            return self.__prepare_src

        # Else provide a default function if we have exactly 1 checkout
        if not self.checkout:
            raise e3.anod.error.SpecError(
                "no checkout associated to the builder %s" % self.name, "prepare_src"
            )
        elif len(self.checkout) > 1:
            raise e3.anod.error.SpecError(
                "more than 1 checkout and no prepare_src function"
                " given for %s" % self.name
            )

        # Set default function (a basic sync_tree call) that ignore
        # .svn, .git, .cvs, .cvsignore and .gitignore files
        return lambda repos, dest: sync_tree(
            list(repos.values())[0]["working_dir"], dest, ignore=VCS_IGNORE_LIST
        )

    @property
    def apply_patch(self):
        """Return the callback used to apply a patch.

        :return: the callback
        :rtype: (str, str, str) -> None
        """

        def default_apply_patch(_, patch_file, dest):
            """Apply a patch file using e3.diff.patch."""
            e3.log.debug("applying patch %s on %s", patch_file, dest)
            e3.diff.patch(patch_file, dest)

        def no_apply_patch(r, p, d):
            """Raise an error (no apply_patch function defined)."""
            # Unused parameters
            del r, p, d
            raise e3.anod.error.AnodError(
                "no apply_patch function defined in SourceBuilder %s" % self.name,
                "apply_path",
            )

        if self.__apply_patch == self.DEFAULT_PATCH_CMD or (
            self.prepare_src is not None
            and self.__apply_patch is None
            and len(self.checkout) == 1
        ):
            # Either the default patch function is forced or
            # a package can be created with Anod, no patch function is
            # provided and there is only a single repository to patch
            return default_apply_patch
        else:
            if self.__apply_patch is None:
                return no_apply_patch
            else:
                return self.__apply_patch


class UnmanagedSourceBuilder(SourceBuilder):
    """Source builder for sources not managed by anod."""

    @property
    def prepare_src(self):
        """Do not create source package."""
        return None


class ThirdPartySourceBuilder(UnmanagedSourceBuilder):
    """SourceBuilder for thirdparty packages."""

    def __init__(self, name):
        """Create a SourceBuilder for a third party package.

        :param name: full package name (including extension)
        :type name: str
        """
        super(ThirdPartySourceBuilder, self).__init__(
            name=name,
            fullname=lambda: name,
            checkout=None,
            apply_patch=self.DEFAULT_PATCH_CMD,
            kind="thirdparty",
        )


class ExternalSourceBuilder(UnmanagedSourceBuilder):
    """SourceBuilder to reference sources produced outside the setup."""

    def __init__(self, name, bid=None, setup=None, date=None, query_name=None):
        """Initialize ExternalSourceBuilder.

        :param name: source name
        :type name: str
        :param bid: build id. If not None then setup and date parameters
            are ignored
        :type bid: str
        :param setup: setup in which the source has been created. If bid
            is None then this parameter is mandatory
        :type setup: str
        :param date: date of the required source
        :type date: str
        :param query_name: name of the source in 'setup'. Defaults to 'name'
            if None.
        :type query_name: str
        """
        super(ExternalSourceBuilder, self).__init__(
            name=name, fullname=lambda: name, checkout=None, kind="source"
        )
        if query_name is None:
            query_name = name
        self.source_query = {
            "name": query_name,
            "bid": bid,
            "setup": setup,
            "date": date,
        }
