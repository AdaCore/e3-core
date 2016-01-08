import e3.archive
import e3.fs
import e3.log
import e3.os.fs
import os
import pytest
import tempfile

e3.log.activate()


@pytest.mark.parametrize('ext', ('.tar.gz', '.tar', '.zip'))
def test_unpack(ext):
    dir_to_pack = os.path.dirname(__file__)

    test_dir = os.path.basename(dir_to_pack)

    dest = tempfile.mkdtemp()

    archive_name = 'e3-core' + ext

    try:
        e3.archive.create_archive(
            archive_name,
            os.path.abspath(dir_to_pack),
            dest)
        assert os.path.exists(os.path.join(dest, archive_name))

        with pytest.raises(e3.archive.ArchiveError):
            e3.archive.unpack_archive(
                os.path.join(dest, archive_name),
                os.path.join(dest, 'dest'))

        e3.fs.mkdir(os.path.join(dest, 'dest'))
        e3.archive.unpack_archive(
            os.path.join(dest, archive_name),
            os.path.join(dest, 'dest'))

        assert os.path.exists(os.path.join(
            dest, 'dest', test_dir,
            os.path.basename(__file__)))

        e3.fs.mkdir(os.path.join(dest, 'dest2'))
        e3.archive.unpack_archive(
            os.path.join(dest, archive_name),
            os.path.join(dest, 'dest2'),
            selected_files=(
                e3.os.fs.unixpath(
                    os.path.join(test_dir, os.path.basename(__file__))), ),
            remove_root_dir=True)

        assert os.path.exists(os.path.join(
            dest, 'dest2', os.path.basename(__file__)))

        # Test wildcard if not .zip format
        # ??? not supported?
        if ext != '.zip':
            e3.fs.mkdir(os.path.join(dest, 'dest3'))
            e3.archive.unpack_archive(
                os.path.join(dest, archive_name),
                os.path.join(dest, 'dest3'),
                selected_files=(os.path.join(test_dir, '*.py'), ),
                remove_root_dir=True)

            assert os.path.exists(os.path.join(
                dest, 'dest3', os.path.basename(__file__)))

        e3.archive.create_archive(
            'e3' + ext,
            os.path.abspath(dir_to_pack),
            dest,
            from_dir_rename='e3rename')
        e3.fs.mkdir(os.path.join(dest, 'dest4'))
        e3.archive.unpack_archive(
            os.path.join(dest, 'e3' + ext),
            os.path.join(dest, 'dest4'))
        assert os.path.join(dest, 'dest4', 'e3rename')

        # force use of sync_tree
        e3.fs.rm(os.path.join(dest, 'dest4', 'e3rename',
                              os.path.basename(__file__)))
        e3.archive.unpack_archive(
            os.path.join(dest, 'e3' + ext),
            os.path.join(dest, 'dest4', 'e3rename'),
            remove_root_dir=True)
        assert os.path.exists(os.path.join(
            dest, 'dest4', 'e3rename', os.path.basename(__file__)))

    finally:
        e3.fs.rm(dest, True)
