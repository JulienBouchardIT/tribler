import json
import os
import shutil
from binascii import unhexlify
from unittest.mock import Mock
from urllib.parse import quote_plus, unquote_plus

from pony.orm import db_session

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE, UBUNTU_1504_INFOHASH
from tribler_core.tests.tools.test_as_server import TESTS_DIR
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.path_util import pathname2url
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import succeed

SAMPLE_CHANNEL_FILES_DIR = TESTS_DIR / "data" / "sample_channel"


class TestTorrentInfoEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestTorrentInfoEndpoint, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    async def test_get_torrentinfo(self):
        """
        Testing whether the API returns a correct dictionary with torrent info.
        """
        # We intentionally put the file path in a folder with a:
        # - "+" which is a reserved URI character
        # - "\u0191" which is a unicode character
        files_path = self.session_base_dir / u'http_torrent_+\u0191files'
        os.mkdir(files_path)
        shutil.copyfile(TORRENT_UBUNTU_FILE, files_path / 'ubuntu.torrent')

        file_server_port = self.get_port()
        await self.setUpFileServer(file_server_port, files_path)

        def verify_valid_dict(json_data):
            metainfo_dict = json.loads(unhexlify(json_data['metainfo']), encoding='latin-1')
            # FIXME: This check is commented out because json.dump garbles pieces binary data during transfer.
            # To fix it, we must switch to some encoding scheme that is able to encode and decode raw binary
            # fields in the dicts.
            # However, for this works fine at the moment because we never use pieces data in the GUI.
            #self.assertTrue(TorrentDef.load_from_dict(metainfo_dict))
            self.assertTrue('info' in metainfo_dict)

        self.session.dlmgr = Mock()
        self.session.dlmgr.downloads = {}
        self.session.dlmgr.metainfo_requests = {}
        self.session.dlmgr.get_channel_downloads = lambda: []
        self.session.dlmgr.shutdown = lambda: succeed(None)

        await self.do_request('torrentinfo', expected_code=400)
        await self.do_request('torrentinfo?uri=def', expected_code=400)

        path = "file:" + pathname2url(TESTS_DATA_DIR / "bak_single.torrent")
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % path, expected_code=200))

        # Corrupt file
        path = "file:" + pathname2url(TESTS_DATA_DIR / "test_rss.xml")
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

        # FIXME: !!! HTTP query for torrent produces dicts with unicode. TorrentDef creation can't handle unicode. !!!
        path = "http://localhost:%d/ubuntu.torrent" % file_server_port
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % quote_plus(path), expected_code=200))


        path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}'
                          f'&dn=test torrent&tr=http://ubuntu.org/ann')

        hops_list = []

        def get_metainfo(infohash, timeout=20, hops=None, url=None):
            if hops is not None:
                hops_list.append(hops)
            with open(TESTS_DATA_DIR / "ubuntu-15.04-desktop-amd64.iso.torrent", mode='rb') as torrent_file:
                torrent_data = torrent_file.read()
            tdef = TorrentDef.load_from_memory(torrent_data)
            self.assertIsNotNone(url)
            self.assertEqual(url, unquote_plus(path))
            return succeed(tdef.get_metainfo())

        self.session.dlmgr.get_metainfo = get_metainfo
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % path, expected_code=200))

        path = 'magnet:?xt=urn:ed2k:354B15E68FB8F36D7CD88FF94116CDC1'  # No infohash
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=400)

        def get_metainfo_timeout(*args, **kwargs):
            return succeed(None)

        path = quote_plus('magnet:?xt=urn:btih:%s&dn=%s' % ('a' * 40, 'test torrent'))
        self.session.dlmgr.get_metainfo = get_metainfo_timeout
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

        self.session.dlmgr.get_metainfo = get_metainfo
        verify_valid_dict(await self.do_request('torrentinfo?uri=%s' % path, expected_code=200))

        await self.do_request('torrentinfo?uri=%s&hops=0' % path, expected_code=200)
        self.assertListEqual([0], hops_list)

        await self.do_request('torrentinfo?uri=%s&hops=foo' % path, expected_code=400)

        path = 'http://fdsafksdlafdslkdksdlfjs9fsafasdf7lkdzz32.n38/324.torrent'
        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)

        with db_session:
            self.assertEqual(self.session.mds.TorrentMetadata.select().count(), 2)

        mock_download = Mock()
        path = quote_plus(f'magnet:?xt=urn:btih:{hexlify(UBUNTU_1504_INFOHASH)}&dn=test torrent')
        self.session.dlmgr.downloads = {UBUNTU_1504_INFOHASH:mock_download}
        result = await self.do_request('torrentinfo?uri=%s' % path, expected_code=200)
        self.assertTrue(result["download_exists"])

        # Check that we do not return "downloads_exists" if the download is metainfo only download
        self.session.dlmgr.downloads = {UBUNTU_1504_INFOHASH:mock_download}
        self.session.dlmgr.metainfo_requests = {UBUNTU_1504_INFOHASH:[mock_download]}
        result = await self.do_request('torrentinfo?uri=%s' % path, expected_code=200)
        self.assertFalse(result["download_exists"])

        # Check that we return "downloads_exists" if there is a metainfo download for the infohash,
        # but there is also a regular download for the same infohash
        self.session.dlmgr.downloads = {UBUNTU_1504_INFOHASH:mock_download}
        self.session.dlmgr.metainfo_requests = {UBUNTU_1504_INFOHASH:[Mock()]}
        result = await self.do_request('torrentinfo?uri=%s' % path, expected_code=200)
        self.assertTrue(result["download_exists"])


    @timeout(10)
    async def test_on_got_invalid_metainfo(self):
        """
        Test whether the right operations happen when we receive an invalid metainfo object
        """
        def get_metainfo(infohash, *_, **__):
            return succeed("abcd")

        self.session.dlmgr = Mock()
        self.session.dlmgr.get_metainfo = get_metainfo
        self.session.dlmgr.shutdown = lambda: succeed(None)
        self.session.dlmgr.shutdown_downloads = lambda: succeed(None)
        self.session.dlmgr.checkpoint_downloads = lambda: succeed(None)
        path = 'magnet:?xt=urn:btih:%s&dn=%s' % (hexlify(UBUNTU_1504_INFOHASH), quote_plus('test torrent'))

        await self.do_request('torrentinfo?uri=%s' % path, expected_code=500)
