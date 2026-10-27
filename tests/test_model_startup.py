from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from backend.config import Settings
from scripts.serve_model import build_command


class ModelStartupTests(unittest.TestCase):
    def test_gguf_path_alias_and_cpu_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"model with spaces.gguf"; path.write_bytes(b"GGUF-test-header-only")
            settings=replace(Settings(),model="offline-tutor",model_path=str(path))
            command=build_command(settings,"/tools/llama-server")
            self.assertEqual(command[command.index("--model")+1],str(path))
            self.assertEqual(command[command.index("--alias")+1],"offline-tutor")
            self.assertEqual(command[command.index("--port")+1],"8080")
            self.assertEqual(command[command.index("--n-gpu-layers")+1],"0")

    def test_missing_and_non_gguf_model(self):
        with self.assertRaises(ValueError): build_command(Settings(),"llama-server")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"wrong.gguf"; path.write_bytes(b"not a gguf")
            with self.assertRaisesRegex(ValueError,"GGUF"):
                build_command(replace(Settings(),model="x",model_path=str(path)),"llama-server")


if __name__ == "__main__": unittest.main()
