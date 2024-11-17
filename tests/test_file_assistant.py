import unittest
from unittest.mock import patch, MagicMock
import asyncio
import tempfile
import shutil
from pathlib import Path
from mbpy.assistant.file_assistant import HierarchicalLanguageAgent

class TestHierarchicalLanguageAgent(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.agent = HierarchicalLanguageAgent(path=self.test_dir, model_src="gpt-2")

    def tearDown(self):
        # Remove the temporary directory after tests
        shutil.rmtree(self.test_dir)

    @patch('mbpy.file_assistant.async_scandir')
    def test_discover_children(self, mock_scandir):
        mock_entry = MagicMock()
        mock_entry.is_dir.return_value = True
        mock_entry.name = "child_dir"
        mock_entry.path = Path(self.test_dir) / "child_dir"
        mock_scandir.return_value = [mock_entry]

        asyncio.run(self.agent._discover_children())
        self.assertIn("child_dir", self.agent.children)

    @patch('mbpy.file_assistant.async_scandir')
    def test_create_directory_hash(self, mock_scandir):
        mock_entry = MagicMock()
        mock_entry.is_file.return_value = True
        mock_entry.name = "file.py"
        mock_entry.path = Path(self.test_dir) / "file.py"
        mock_entry.stat.return_value.st_mtime = 123456789
        mock_entry.stat.return_value.st_size = 1024
        mock_scandir.return_value = [mock_entry]

        hash_value = asyncio.run(self.agent._create_directory_hash())
        self.assertIsInstance(hash_value, str)

if __name__ == '__main__':
    unittest.main()
