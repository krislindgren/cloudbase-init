# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2014 Cloudbase Solutions Srl
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
import os
import sys
import unittest

if sys.platform == 'win32':
    from cloudbaseinit.metadata.services.osconfigdrive import windows
    from cloudbaseinit.utils.windows import physical_disk
from oslo.config import cfg

CONF = cfg.CONF


@unittest.skipUnless(sys.platform == "win32", "requires Windows")
class TestWindowsConfigDriveManager(unittest.TestCase):

    def setUp(self):
        self._config_manager = windows.WindowsConfigDriveManager()

    @mock.patch('cloudbaseinit.osutils.factory.get_os_utils')
    @mock.patch('os.path.exists')
    def _test_get_config_drive_cdrom_mount_point(self, mock_join,
                                                 mock_get_os_utils, exists):
        mock_osutils = mock.MagicMock()
        mock_get_os_utils.return_value = mock_osutils
        mock_osutils.get_cdrom_drives.return_value = ['fake drive']
        mock_osutils.get_volume_label.return_value = 'config-2'
        mock_join.return_value = exists

        response = self._config_manager._get_config_drive_cdrom_mount_point()

        mock_osutils.get_cdrom_drives.assert_called_once_with()
        mock_osutils.get_volume_label.assert_called_once_with('fake drive')

        if exists:
            self.assertEqual(response, 'fake drive')
        else:
            self.assertIsNone(response)

    def test_get_config_drive_cdrom_mount_point_exists_true(self):
        self._test_get_config_drive_cdrom_mount_point(exists=True)

    def test_get_config_drive_cdrom_mount_point_exists_false(self):
        self._test_get_config_drive_cdrom_mount_point(exists=False)

    @mock.patch('ctypes.cast')
    @mock.patch('ctypes.POINTER')
    @mock.patch('ctypes.wintypes.WORD')
    def test_c_char_array_to_c_ushort(self, mock_WORD, mock_POINTER,
                                      mock_cast):
        mock_buf = mock.MagicMock()

        response = self._config_manager._c_char_array_to_c_ushort(mock_buf,
                                                                  1)

        self.assertEqual(mock_cast.call_count, 2)
        mock_POINTER.assert_called_with(mock_WORD)
        mock_cast.assert_called_with(mock_buf.__getitem__(), mock_POINTER())
        self.assertEqual(response,
                         mock_cast().contents.value.__lshift__().__add__())

    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager._c_char_array_to_c_ushort')
    def _test_get_iso_disk_size(self, mock_c_char_array_to_c_ushort,
                                media_type, value, iso_id):

        boot_record_off = 0x8000
        volume_size_off = 80
        block_size_off = 128

        mock_phys_disk = mock.MagicMock()
        mock_buff = mock.MagicMock()
        mock_geom = mock.MagicMock()

        mock_phys_disk.get_geometry.return_value = mock_geom
        mock_geom.MediaType = media_type
        mock_geom.Cylinders = value
        mock_geom.TracksPerCylinder = 2
        mock_geom.SectorsPerTrack = 2
        mock_geom.BytesPerSector = 2
        mock_phys_disk.read.return_value = (mock_buff, 'fake value')
        mock_buff.__getitem__.return_value = iso_id
        mock_c_char_array_to_c_ushort.return_value = 100

        disk_size = mock_geom.Cylinders * mock_geom.TracksPerCylinder * \
            mock_geom.SectorsPerTrack * mock_geom.BytesPerSector

        offset = boot_record_off / mock_geom.BytesPerSector * \
            mock_geom.BytesPerSector

        buf_off_volume = boot_record_off - offset + volume_size_off
        buf_off_block = boot_record_off - offset + block_size_off

        response = self._config_manager._get_iso_disk_size(mock_phys_disk)
        mock_phys_disk.get_geometry.assert_called_once_with()
        if mock_geom.MediaType != physical_disk.Win32_DiskGeometry.FixedMedia:
            self.assertIsNone(response)
        elif disk_size <= offset + mock_geom.BytesPerSector:
            self.assertIsNone(response)
        else:
            mock_phys_disk.seek.assert_called_once_with(offset)
            mock_phys_disk.read.assert_called_once_with(
                mock_geom.BytesPerSector)
            if iso_id != 'CD001':
                self.assertIsNone(response)
            else:
                mock_c_char_array_to_c_ushort.assert_has_calls(
                    mock.call(mock_buff, buf_off_volume),
                    mock.call(mock_buff, buf_off_block))
                self.assertEqual(response, 10000)

    def test_test_get_iso_disk_size(self):
        self._test_get_iso_disk_size(
            media_type=physical_disk.Win32_DiskGeometry.FixedMedia,
            value=100, iso_id='CD001')

    def test_test_get_iso_disk_size_other_media_type(self):
        self._test_get_iso_disk_size(media_type="fake media type", value=100,
                                     iso_id='CD001')

    def test_test_get_iso_disk_size_other_disk_size_too_small(self):
        self._test_get_iso_disk_size(
            media_type=physical_disk.Win32_DiskGeometry.FixedMedia, value=0,
            iso_id='CD001')

    def test_test_get_iso_disk_size_other_id(self):
        self._test_get_iso_disk_size(
            media_type=physical_disk.Win32_DiskGeometry.FixedMedia,
            value=100, iso_id='other id')

    def test_write_iso_file(self):
        mock_buff = mock.MagicMock()
        mock_geom = mock.MagicMock()
        mock_geom.BytesPerSector = 2

        mock_phys_disk = mock.MagicMock()
        mock_phys_disk.read.return_value = (mock_buff, 10)

        fake_path = os.path.join('fake', 'path')

        mock_phys_disk.get_geometry.return_value = mock_geom
        with mock.patch('__builtin__.open', mock.mock_open(),
                        create=True) as f:
            self._config_manager._write_iso_file(mock_phys_disk, fake_path,
                                                 10)
            f().write.assert_called_once_with(mock_buff)
        mock_phys_disk.seek.assert_called_once_with(0)
        mock_phys_disk.read.assert_called_once_with(10)

    @mock.patch('os.makedirs')
    def _test_extract_iso_files(self, mock_makedirs, exit_code):
        fake_path = os.path.join('fake', 'path')
        fake_target_path = os.path.join(fake_path, 'target')
        args = [CONF.bsdtar_path, '-xf', fake_path, '-C', fake_target_path]
        mock_os_utils = mock.MagicMock()

        mock_os_utils.execute_process.return_value = ('fake out', 'fake err',
                                                      exit_code)
        if exit_code:
            self.assertRaises(Exception,
                              self._config_manager._extract_iso_files,
                              mock_os_utils, fake_path, fake_target_path)
        else:
            self._config_manager._extract_iso_files(mock_os_utils, fake_path,
                                                    fake_target_path)

        mock_os_utils.execute_process.assert_called_once_with(args, False)
        mock_makedirs.assert_called_once_with(fake_target_path)

    def test_extract_iso_files(self):
        self._test_extract_iso_files(exit_code=None)

    def test_extract_iso_files_exception(self):
        self._test_extract_iso_files(exit_code=1)

    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager._get_iso_disk_size')
    @mock.patch('cloudbaseinit.utils.windows.physical_disk.PhysicalDisk')
    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager._write_iso_file')
    def _test_extract_iso_disk_file(self, mock_write_iso_file,
                                    mock_PhysicalDisk, mock_get_iso_disk_size,
                                    exception):
        mock_osutils = mock.MagicMock()
        fake_path = os.path.join('fake', 'path')
        fake_path_physical = os.path.join(fake_path, 'physical')
        mock_osutils.get_physical_disks.return_value = [fake_path_physical]
        mock_get_iso_disk_size.return_value = 'fake iso size'

        if exception:
            mock_PhysicalDisk().open.side_effect = [Exception]

        response = self._config_manager._extract_iso_disk_file(
            osutils=mock_osutils, iso_file_path=fake_path)
        print mock_PhysicalDisk().open.mock_calls

        if not exception:
            mock_get_iso_disk_size.assert_called_once_with(
                mock_PhysicalDisk())
            mock_write_iso_file.assert_called_once_with(mock_PhysicalDisk(),
                                                        fake_path,
                                                        'fake iso size')
            self.assertTrue(response)
        else:
            self.assertFalse(response)

        mock_PhysicalDisk().open.assert_called_once_with()
        mock_osutils.get_physical_disks.assert_called_once_with()
        mock_PhysicalDisk().close.assert_called_once_with()

    def test_extract_iso_disk_file_disk_found(self):
        self._test_extract_iso_disk_file(exception=False)

    def test_extract_iso_disk_file_disk_not_found(self):
        self._test_extract_iso_disk_file(exception=True)

    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager._get_conf_drive_from_raw_hdd')
    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager._get_conf_drive_from_cdrom_drive')
    def test_get_config_drive_files(self,
                                    mock_get_conf_drive_from_cdrom_drive,
                                    mock_get_conf_drive_from_raw_hdd):

        fake_path = os.path.join('fake', 'path')
        mock_get_conf_drive_from_raw_hdd.return_value = False
        mock_get_conf_drive_from_cdrom_drive.return_value = True

        response = self._config_manager.get_config_drive_files(
            target_path=fake_path)

        mock_get_conf_drive_from_raw_hdd.assert_called_once_with(fake_path)
        mock_get_conf_drive_from_cdrom_drive.assert_called_once_with(
            fake_path)
        self.assertTrue(response)

    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager.'
                '_get_config_drive_cdrom_mount_point')
    @mock.patch('shutil.copytree')
    def _test_get_conf_drive_from_cdrom_drive(self, mock_copytree,
                                              mock_get_config_cdrom_mount,
                                              mount_point):
        fake_path = os.path.join('fake', 'path')
        mock_get_config_cdrom_mount.return_value = mount_point

        response = self._config_manager._get_conf_drive_from_cdrom_drive(
            fake_path)

        mock_get_config_cdrom_mount.assert_called_once_with()

        if mount_point:
            mock_copytree.assert_called_once_with(mount_point, fake_path)
            self.assertTrue(response)
        else:
            self.assertFalse(response)

    def test_get_conf_drive_from_cdrom_drive_with_mountpoint(self):
        self._test_get_conf_drive_from_cdrom_drive(
            mount_point='fake mount point')

    def test_get_conf_drive_from_cdrom_drive_without_mountpoint(self):
        self._test_get_conf_drive_from_cdrom_drive(
            mount_point=None)

    @mock.patch('os.remove')
    @mock.patch('os.path.exists')
    @mock.patch('tempfile.gettempdir')
    @mock.patch('uuid.uuid4')
    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager._extract_iso_disk_file')
    @mock.patch('cloudbaseinit.metadata.services.osconfigdrive.windows.'
                'WindowsConfigDriveManager._extract_iso_files')
    @mock.patch('cloudbaseinit.osutils.factory.get_os_utils')
    def _test_get_conf_drive_from_raw_hdd(self, mock_get_os_utils,
                                          mock_extract_iso_files,
                                          mock_extract_iso_disk_file,
                                          mock_uuid4, mock_gettempdir,
                                          mock_exists, mock_remove,
                                          found_drive):
        fake_target_path = os.path.join('fake', 'path')
        fake_iso_path = os.path.join('fake_dir', 'fake_id' + '.iso')

        mock_uuid4.return_value = 'fake_id'
        mock_gettempdir.return_value = 'fake_dir'
        mock_extract_iso_disk_file.return_value = found_drive
        mock_exists.return_value = found_drive

        response = self._config_manager._get_conf_drive_from_raw_hdd(
            fake_target_path)

        mock_get_os_utils.assert_called_once_with()
        mock_gettempdir.assert_called_once_with()
        mock_extract_iso_disk_file.assert_called_once_with(
            mock_get_os_utils(), fake_iso_path)
        if found_drive:
            mock_extract_iso_files.assert_called_once_with(
                mock_get_os_utils(), fake_iso_path, fake_target_path)
            mock_exists.assert_called_once_with(fake_iso_path)
            mock_remove.assert_called_once_with(fake_iso_path)
            self.assertTrue(response)
        else:
            self.assertFalse(response)

    def test_get_conf_drive_from_raw_hdd_found_drive(self):
        self._test_get_conf_drive_from_raw_hdd(found_drive=True)

    def test_get_conf_drive_from_raw_hdd_no_drive_found(self):
        self._test_get_conf_drive_from_raw_hdd(found_drive=False)
