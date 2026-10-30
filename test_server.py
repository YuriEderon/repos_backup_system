import os
import json
import shutil
import zipfile
import tempfile
import unittest
from io import BytesIO

import server
from server import (
    format_size,
    get_dir_size,
    get_file_count,
    clear_directory,
    BackupSystemHandler,
)


class TestFormatSize(unittest.TestCase):
    def test_zero_bytes(self):
        self.assertEqual(format_size(0), "0 B")

    def test_bytes(self):
        self.assertEqual(format_size(512), "512.00 B")

    def test_kilobytes(self):
        self.assertEqual(format_size(1024), "1.00 KB")

    def test_megabytes(self):
        self.assertEqual(format_size(1024 * 1024), "1.00 MB")

    def test_gigabytes(self):
        self.assertEqual(format_size(1024 ** 3), "1.00 GB")

    def test_fractional_kilobytes(self):
        self.assertEqual(format_size(1536), "1.50 KB")

    def test_fractional_megabytes(self):
        self.assertEqual(format_size(1024 * 1024 * 2.5), "2.50 MB")

    def test_large_value(self):
        self.assertEqual(format_size(1024 ** 3 * 5), "5.00 GB")


class TestGetDirSize(unittest.TestCase):
    def test_nonexistent_directory(self):
        self.assertEqual(get_dir_size("/nonexistent/path/that/doesnt/exist"), 0)

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(get_dir_size(tmpdir), 0)

    def test_directory_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.txt"), "w") as f:
                f.write("hello")
            self.assertEqual(get_dir_size(tmpdir), 5)

    def test_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "sub", "deep")
            os.makedirs(nested)
            with open(os.path.join(nested, "file.txt"), "w") as f:
                f.write("12345678")
            self.assertEqual(get_dir_size(tmpdir), 8)

    def test_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                with open(os.path.join(tmpdir, f"f{i}.txt"), "w") as f:
                    f.write("x" * 100)
            self.assertEqual(get_dir_size(tmpdir), 300)


class TestGetFileCount(unittest.TestCase):
    def test_nonexistent_directory(self):
        self.assertEqual(get_file_count("/nonexistent/path"), 0)

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(get_file_count(tmpdir), 0)

    def test_directory_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                open(os.path.join(tmpdir, f"f{i}.txt"), "w").close()
            self.assertEqual(get_file_count(tmpdir), 5)

    def test_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "sub")
            os.makedirs(nested)
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(nested, "b.txt"), "w").close()
            self.assertEqual(get_file_count(tmpdir), 2)


class TestClearDirectory(unittest.TestCase):
    def test_nonexistent_directory(self):
        clear_directory("/nonexistent/path")

    def test_clear_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                open(os.path.join(tmpdir, f"f{i}.txt"), "w").close()
            clear_directory(tmpdir)
            self.assertEqual(get_file_count(tmpdir), 0)

    def test_clear_nested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "sub")
            os.makedirs(nested)
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(nested, "b.txt"), "w").close()
            clear_directory(tmpdir)
            self.assertEqual(get_file_count(tmpdir), 0)
            self.assertTrue(os.path.exists(tmpdir))


def _make_handler():
    handler = BackupSystemHandler.__new__(BackupSystemHandler)
    handler.wfile = BytesIO()
    handler.rfile = BytesIO()
    handler.headers = {}
    handler.requestline = "GET /test HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 12345)

    def mock_send_response(code):
        handler._response_code = code

    def mock_send_header(key, value):
        handler.headers[key] = value

    def mock_end_headers():
        pass

    handler.send_response = mock_send_response
    handler.send_header = mock_send_header
    handler.end_headers = mock_end_headers

    return handler


class TestApiStatus(unittest.TestCase):
    def setUp(self):
        self._orig_source = server.SOURCE_DIR
        self._orig_backup = server.BACKUP_DIR
        self.test_source = tempfile.mkdtemp()
        self.test_backup = tempfile.mkdtemp()
        server.SOURCE_DIR = self.test_source
        server.BACKUP_DIR = self.test_backup

    def tearDown(self):
        server.SOURCE_DIR = self._orig_source
        server.BACKUP_DIR = self._orig_backup
        shutil.rmtree(self.test_source, ignore_errors=True)
        shutil.rmtree(self.test_backup, ignore_errors=True)

    def test_returns_json_with_saves_and_backups(self):
        handler = _make_handler()
        handler.handle_api_status()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertIn("saves", data)
        self.assertIn("backups", data)

    def test_saves_exists_true(self):
        handler = _make_handler()
        handler.handle_api_status()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data["saves"]["exists"])

    def test_saves_file_count(self):
        open(os.path.join(self.test_source, "a.txt"), "w").close()
        open(os.path.join(self.test_source, "b.txt"), "w").close()
        handler = _make_handler()
        handler.handle_api_status()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data["saves"]["fileCount"], 2)

    def test_saves_total_size(self):
        with open(os.path.join(self.test_source, "big.txt"), "w") as f:
            f.write("x" * 2048)
        handler = _make_handler()
        handler.handle_api_status()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data["saves"]["totalSize"], "2.00 KB")

    def test_backup_count(self):
        with zipfile.ZipFile(os.path.join(self.test_backup, "b1.zip"), "w") as zf:
            zf.writestr("a", "data")
        with zipfile.ZipFile(os.path.join(self.test_backup, "b2.zip"), "w") as zf:
            zf.writestr("b", "data")
        handler = _make_handler()
        handler.handle_api_status()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data["backups"]["count"], 2)

    def test_backup_creates_dir_if_missing(self):
        missing = os.path.join(tempfile.gettempdir(), "test_backup_missing")
        server.BACKUP_DIR = missing
        try:
            handler = _make_handler()
            handler.handle_api_status()
            self.assertTrue(os.path.exists(missing))
        finally:
            shutil.rmtree(missing, ignore_errors=True)


class TestApiListBackups(unittest.TestCase):
    def setUp(self):
        self._orig_backup = server.BACKUP_DIR
        self.test_backup = tempfile.mkdtemp()
        server.BACKUP_DIR = self.test_backup

    def tearDown(self):
        server.BACKUP_DIR = self._orig_backup
        shutil.rmtree(self.test_backup, ignore_errors=True)

    def test_empty_directory(self):
        handler = _make_handler()
        handler.handle_api_list_backups()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data, [])

    def test_returns_backup_list(self):
        with zipfile.ZipFile(os.path.join(self.test_backup, "test.zip"), "w") as zf:
            zf.writestr("test.txt", "content")
        handler = _make_handler()
        handler.handle_api_list_backups()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["filename"], "test.zip")
        self.assertIn("date", data[0])
        self.assertIn("size", data[0])

    def test_sorted_newest_first(self):
        import time
        for name in ["old.zip", "mid.zip", "new.zip"]:
            with zipfile.ZipFile(os.path.join(self.test_backup, name), "w") as zf:
                zf.writestr("f", "d")
            time.sleep(0.05)
        handler = _make_handler()
        handler.handle_api_list_backups()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        names = [b["filename"] for b in data]
        self.assertEqual(names, ["new.zip", "mid.zip", "old.zip"])

    def test_nonexistent_directory(self):
        server.BACKUP_DIR = "/nonexistent/path"
        handler = _make_handler()
        handler.handle_api_list_backups()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data, [])


class TestApiBackup(unittest.TestCase):
    def setUp(self):
        self._orig_source = server.SOURCE_DIR
        self._orig_backup = server.BACKUP_DIR
        self.test_source = tempfile.mkdtemp()
        self.test_backup = tempfile.mkdtemp()
        server.SOURCE_DIR = self.test_source
        server.BACKUP_DIR = self.test_backup

    def tearDown(self):
        server.SOURCE_DIR = self._orig_source
        server.BACKUP_DIR = self._orig_backup
        shutil.rmtree(self.test_source, ignore_errors=True)
        shutil.rmtree(self.test_backup, ignore_errors=True)

    def test_creates_zip_file(self):
        with open(os.path.join(self.test_source, "save.txt"), "w") as f:
            f.write("game_data")
        handler = _make_handler()
        handler.handle_api_backup()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("REPO_Backup_", data["filename"])
        zip_files = [f for f in os.listdir(self.test_backup) if f.endswith(".zip")]
        self.assertEqual(len(zip_files), 1)

    def test_zip_contains_source_files(self):
        with open(os.path.join(self.test_source, "save.txt"), "w") as f:
            f.write("important_data")
        handler = _make_handler()
        handler.handle_api_backup()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        zip_path = os.path.join(self.test_backup, data["filename"])
        with zipfile.ZipFile(zip_path, "r") as zf:
            self.assertIn("save.txt", zf.namelist())
            self.assertEqual(zf.read("save.txt").decode(), "important_data")

    def test_source_not_found(self):
        server.SOURCE_DIR = "/nonexistent/path"
        handler = _make_handler()
        handler.handle_api_backup()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(data["success"])

    def test_response_includes_size_and_date(self):
        with open(os.path.join(self.test_source, "a.txt"), "w") as f:
            f.write("data")
        handler = _make_handler()
        handler.handle_api_backup()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertIn("size", data)
        self.assertIn("date", data)


class TestApiRestore(unittest.TestCase):
    def setUp(self):
        self._orig_source = server.SOURCE_DIR
        self._orig_backup = server.BACKUP_DIR
        self.test_source = tempfile.mkdtemp()
        self.test_backup = tempfile.mkdtemp()
        server.SOURCE_DIR = self.test_source
        server.BACKUP_DIR = self.test_backup

    def tearDown(self):
        server.SOURCE_DIR = self._orig_source
        server.BACKUP_DIR = self._orig_backup
        shutil.rmtree(self.test_source, ignore_errors=True)
        shutil.rmtree(self.test_backup, ignore_errors=True)

    def test_missing_filename(self):
        handler = _make_handler()
        handler.handle_api_restore({})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(data["success"])

    def test_file_not_found(self):
        handler = _make_handler()
        handler.handle_api_restore({"filename": "nonexistent.zip"})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(data["success"])

    def test_restores_files(self):
        zip_path = os.path.join(self.test_backup, "backup.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("restored.txt", "restored_data")
        handler = _make_handler()
        handler.handle_api_restore({"filename": "backup.zip"})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertTrue(os.path.exists(os.path.join(self.test_source, "restored.txt")))
        with open(os.path.join(self.test_source, "restored.txt")) as f:
            self.assertEqual(f.read(), "restored_data")

    def test_clears_existing_source_before_restore(self):
        with open(os.path.join(self.test_source, "old.txt"), "w") as f:
            f.write("old_data")
        zip_path = os.path.join(self.test_backup, "backup.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("new.txt", "new_data")
        handler = _make_handler()
        handler.handle_api_restore({"filename": "backup.zip"})
        self.assertFalse(os.path.exists(os.path.join(self.test_source, "old.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.test_source, "new.txt")))

    def test_path_traversal_blocked(self):
        handler = _make_handler()
        handler.handle_api_restore({"filename": "../../etc/passwd"})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(data["success"])


class TestApiDelete(unittest.TestCase):
    def setUp(self):
        self._orig_backup = server.BACKUP_DIR
        self.test_backup = tempfile.mkdtemp()
        server.BACKUP_DIR = self.test_backup

    def tearDown(self):
        server.BACKUP_DIR = self._orig_backup
        shutil.rmtree(self.test_backup, ignore_errors=True)

    def test_missing_filename(self):
        handler = _make_handler()
        handler.handle_api_delete({})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(data["success"])

    def test_file_not_found(self):
        handler = _make_handler()
        handler.handle_api_delete({"filename": "nonexistent.zip"})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(data["success"])

    def test_deletes_file(self):
        zip_path = os.path.join(self.test_backup, "backup.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test.txt", "content")
        
        self.assertTrue(os.path.exists(zip_path))
        handler = _make_handler()
        handler.handle_api_delete({"filename": "backup.zip"})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertFalse(os.path.exists(zip_path))

    def test_path_traversal_blocked(self):
        handler = _make_handler()
        handler.handle_api_delete({"filename": "../../etc/passwd"})
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(data["success"])


if __name__ == "__main__":
    unittest.main()
