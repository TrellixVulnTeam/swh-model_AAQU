# Copyright (C) 2018-2019 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import os
import tarfile
import tempfile
import unittest

from click.testing import CliRunner
import pytest

from swh.model import cli
from swh.model.hashutil import hash_to_hex
from swh.model.tests.test_from_disk import DataMixin


@pytest.mark.fs
class TestIdentify(DataMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.runner = CliRunner()

    def assertPidOK(self, result, pid):
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output.split()[0], pid)

    def test_no_args(self):
        result = self.runner.invoke(cli.identify)
        self.assertNotEqual(result.exit_code, 0)

    def test_content_id(self):
        """identify file content"""
        self.make_contents(self.tmpdir_name)
        for filename, content in self.contents.items():
            path = os.path.join(self.tmpdir_name, filename)
            result = self.runner.invoke(cli.identify, ["--type", "content", path])
            self.assertPidOK(result, "swh:1:cnt:" + hash_to_hex(content["sha1_git"]))

    def test_content_id_from_stdin(self):
        """identify file content"""
        self.make_contents(self.tmpdir_name)
        for _, content in self.contents.items():
            result = self.runner.invoke(cli.identify, ["-"], input=content["data"])
            self.assertPidOK(result, "swh:1:cnt:" + hash_to_hex(content["sha1_git"]))

    def test_directory_id(self):
        """identify an entire directory"""
        self.make_from_tarball(self.tmpdir_name)
        path = os.path.join(self.tmpdir_name, b"sample-folder")
        result = self.runner.invoke(cli.identify, ["--type", "directory", path])
        self.assertPidOK(result, "swh:1:dir:e8b0f1466af8608c8a3fb9879db172b887e80759")

    def test_snapshot_id(self):
        """identify a snapshot"""
        tarball = os.path.join(
            os.path.dirname(__file__), "data", "repos", "sample-repo.tgz"
        )
        with tempfile.TemporaryDirectory(prefix="swh.model.cli") as d:
            with tarfile.open(tarball, "r:gz") as t:
                t.extractall(d)
                repo_dir = os.path.join(d, "sample-repo")
                result = self.runner.invoke(
                    cli.identify, ["--type", "snapshot", repo_dir]
                )
                self.assertPidOK(
                    result, "swh:1:snp:abc888898124270905a0ef3c67e872ce08e7e0c1"
                )

    def test_origin_id(self):
        """identify an origin URL"""
        url = "https://github.com/torvalds/linux"
        result = self.runner.invoke(cli.identify, ["--type", "origin", url])
        self.assertPidOK(result, "swh:1:ori:b63a575fe3faab7692c9f38fb09d4bb45651bb0f")

    def test_symlink(self):
        """identify symlink --- both itself and target"""
        regular = os.path.join(self.tmpdir_name, b"foo.txt")
        link = os.path.join(self.tmpdir_name, b"bar.txt")
        open(regular, "w").write("foo\n")
        os.symlink(os.path.basename(regular), link)

        result = self.runner.invoke(cli.identify, [link])
        self.assertPidOK(result, "swh:1:cnt:257cc5642cb1a054f08cc83f2d943e56fd3ebe99")

        result = self.runner.invoke(cli.identify, ["--no-dereference", link])
        self.assertPidOK(result, "swh:1:cnt:996f1789ff67c0e3f69ef5933a55d54c5d0e9954")

    def test_show_filename(self):
        """filename is shown by default"""
        self.make_contents(self.tmpdir_name)
        for filename, content in self.contents.items():
            path = os.path.join(self.tmpdir_name, filename)
            result = self.runner.invoke(cli.identify, ["--type", "content", path])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                result.output.rstrip(),
                "swh:1:cnt:%s\t%s" % (hash_to_hex(content["sha1_git"]), path.decode()),
            )

    def test_hide_filename(self):
        """filename is hidden upon request"""
        self.make_contents(self.tmpdir_name)
        for filename, content in self.contents.items():
            path = os.path.join(self.tmpdir_name, filename)
            result = self.runner.invoke(
                cli.identify, ["--type", "content", "--no-filename", path]
            )
            self.assertPidOK(result, "swh:1:cnt:" + hash_to_hex(content["sha1_git"]))

    def test_auto_content(self):
        """automatic object type detection: content"""
        with tempfile.NamedTemporaryFile(prefix="swh.model.cli") as f:
            result = self.runner.invoke(cli.identify, [f.name])
            self.assertEqual(result.exit_code, 0)
            self.assertRegex(result.output, r"^swh:\d+:cnt:")

    def test_auto_directory(self):
        """automatic object type detection: directory"""
        with tempfile.TemporaryDirectory(prefix="swh.model.cli") as dirname:
            result = self.runner.invoke(cli.identify, [dirname])
            self.assertEqual(result.exit_code, 0)
            self.assertRegex(result.output, r"^swh:\d+:dir:")

    def test_auto_origin(self):
        """automatic object type detection: origin"""
        result = self.runner.invoke(cli.identify, ["https://github.com/torvalds/linux"])
        self.assertEqual(result.exit_code, 0)
        self.assertRegex(result.output, r"^swh:\d+:ori:")

    def test_verify_content(self):
        """identifier verification"""
        self.make_contents(self.tmpdir_name)
        for filename, content in self.contents.items():
            expected_id = "swh:1:cnt:" + hash_to_hex(content["sha1_git"])

            # match
            path = os.path.join(self.tmpdir_name, filename)
            result = self.runner.invoke(cli.identify, ["--verify", expected_id, path])
            self.assertEqual(result.exit_code, 0)

            # mismatch
            with open(path, "a") as f:
                f.write("trailing garbage to make verification fail")
            result = self.runner.invoke(cli.identify, ["--verify", expected_id, path])
            self.assertEqual(result.exit_code, 1)
