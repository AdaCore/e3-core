from __future__ import absolute_import

import e3.anod.error
import e3.diff
import e3.log
from e3.env import Env
from e3.fs import VCS_IGNORE_LIST, sync_tree


class Package(object):
    """Describe and generate a binary package."""

    def __init__(self, prefix, publish=False, nsis=None, version=None,
                 pkg_ext='.tar.gz', no_root_dir=False, **kwargs):
        """Create a binary package.

        :param prefix: prefix of the package to create, the name will be
            {prefix}-{version}-{platform}-bin.{exe,tar.gz}
            The version is by default set to Anod.sandbox.build_version and
            can be overriden by the version callback.
        :type prefix: str
        :param publish: if True, publish the package
        :type publish: bool
        :param nsis: a callback returning a dictionary containing needed data
            to build an NSIS package.
        :type nsis: () -> dict[str][str]  | None
        :param version: a callback returning the package version, if None the
            version is set to Anod.sandbox.build_version
        :type version: () -> str | None
        :param pkg_ext: set the extension of the binary package (ignored when
            nsis is used). The default is .tar.gz.
        :type pkg_ext: str
        :param no_root_dir: Create package without the root directory (zip
            only)
        :type no_root_dir: bool
        """
        # Ignore all unsupported parameters
        del kwargs
        self.prefix = prefix
        self.name = prefix + '-{version}-{platform}-bin'
        self.platform = Env().platform
        self.publish = publish
        self.pkg_ext = pkg_ext
        self.no_root_dir = no_root_dir
        self.nsis = nsis
        self.version = version


class Source(object):
    """Source package."""

    def __init__(self, name, publish, dest=None, unpack_cmd=None,
                 remove_root_dir=True, ignore=None):
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
        :param ignore: list of directories/filenames to ignore when
            synchronising the `dest` content. See documentation of
            gnatpython.fileutils.sync_tree
        :type ignore: None | list[str]
        """
        self.name = name
        self.publish = publish
        self.dest = dest
        self.unpack_cmd = unpack_cmd
        self.remove_root_dir = remove_root_dir
        self.ignore = ignore
        self.builder = None

    def set_builder(self, builder_function):
        """Set the SourceBuilder associated to this Source object."""
        self.builder = builder_function


class SharedSource(Source):
    """Shared sources are installed directly in the sandbox.

    This is useful when you need to use the same sources for different
    modules/platforms and you don't need to write in the sources
    directory
    """

    pass


class SourceBuilder(object):

    DEFAULT_PATCH_CMD = 1

    def __init__(self, name, fullname, checkout,
                 prepare_src=None, apply_patch=None,
                 kind='source'):
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
        self.checkout = checkout
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
        elif self.checkout is None:
            # Checkout set to None, it means that there is no way
            # to create a source package via Anod.
            # This can be true for third party packages
            return None

        # Else provide a default function if we have exactly 1 checkout
        if not self.checkout:
            raise e3.anod.error.SpecError(
                'no checkout associated to the builder %s' % self.name,
                'prepare_src')
        elif len(self.checkout) > 1:
            raise e3.anod.error.SpecError(
                'more than 1 checkout and no prepare_src function'
                ' given for %s' % self.name)

        # Set default function (a basic sync_tree call) that ignore
        # .svn, .git, .cvs, .cvsignore and .gitignore files
        return lambda repos, dest: sync_tree(
            repos.values()[0]['working_dir'], dest,
            ignore=VCS_IGNORE_LIST)

    @property
    def apply_patch(self):
        """Return the callback used to apply a patch.

        :return: the callback
        :rtype: (str, str, str) -> None
        """
        def default_apply_patch(_, patch_file, dest):
            """Default patch function to apply patches."""
            e3.log.debug('applying patch %s on %s', patch_file, dest)
            e3.diff.patch(patch_file, dest)

        def no_apply_patch(r, p, d):
            """Default function when no patch function is found."""
            # Unused parameters
            del r, p, d
            raise e3.anod.error.AnodError(
                'no apply_patch function defined in SourceBuilder %s'
                % self.name,
                'apply_path')

        if self.__apply_patch == self.DEFAULT_PATCH_CMD or (
                self.prepare_src is not None and
                self.__apply_patch is None and len(self.checkout) == 1):
            # Either the default patch function is forced or
            # a package can be created with Anod, no patch function is
            # provided and there is only a single repository to patch
            return default_apply_patch
        else:
            if self.__apply_patch is None:
                return no_apply_patch
            else:
                return self.__apply_patch

    def add_repository(self, repository):
        """Add new Repository object."""
        self.repositories[repository.name] = repository


class ThirdPartySourceBuilder(SourceBuilder):
    """SourceBuilder for thirdparty packages."""

    def __init__(self, name, fullname=None, checkout=None,
                 prepare_src=None, apply_patch=None,
                 kind='thirdparty'):
        """Create a SourceBuilder for a third party package.

        See SourceBuilder documentation
        """
        if apply_patch is None:
            apply_patch = self.DEFAULT_PATCH_CMD
        if fullname is None:
            fullname = name
        SourceBuilder.__init__(self, name, fullname, checkout,
                               prepare_src, apply_patch, kind)


class ExternalSourceBuilder(SourceBuilder):
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
        SourceBuilder.__init__(self,
                               name=name,
                               fullname=lambda: name,
                               checkout=None,
                               kind='source')
        if query_name is None:
            query_name = name
        self.source_query = {'name': query_name,
                             'bid': bid,
                             'setup': setup,
                             'date': date}
