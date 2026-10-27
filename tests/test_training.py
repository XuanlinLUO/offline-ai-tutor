import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from training.check_dataset import validate_dataset
from training.common import execute_factory
from training.train_lora import build_config


def row(text):
    return {"instruction": text, "input": "", "output": "问题分析\n解题步骤\n最终答案\n知识点讲解"}


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"; self.data.mkdir()
        (self.data / "train.json").write_text(json.dumps([row("题目一"), row("题目二")]), encoding="utf-8")
        (self.data / "validation.json").write_text(json.dumps([row("题目三")]), encoding="utf-8")
        self.base = self.root / "base"; self.base.mkdir()
        (self.base / "config.json").write_text('{"model_type":"qwen3"}')

    def tearDown(self): self.temp.cleanup()

    def test_normalized_overlap_rejected(self):
        (self.data / "validation.json").write_text(json.dumps([row("题 目 一")]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "相同题目"): validate_dataset(self.data)

    def test_wrong_step_order_rejected(self):
        bad = row("第四题"); bad["output"] = "最终答案\n问题分析\n解题步骤\n知识点讲解"
        (self.data / "train.json").write_text(json.dumps([bad]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "顺序"): validate_dataset(self.data)

    def test_lora_config_and_precision(self):
        args = argparse.Namespace(base_model=self.base, dataset_dir=self.data, output_dir=self.root / "adapter",
            dry_run=True, rank=8, alpha=16, epochs=3.0, learning_rate=1e-4, batch_size=1, accumulation=8,
            cutoff_len=2048, targets="all", template="qwen3_nothink", precision="fp16", seed=42,
            environment_reference="test-only")
        config, metadata = build_config(args)
        self.assertEqual(config["finetuning_type"], "lora")
        self.assertTrue(config["fp16"]); self.assertFalse(config["bf16"])
        self.assertEqual(metadata["dataset"]["train"]["count"], 2)

    def test_dry_run_is_only_a_plan(self):
        output = self.root / "adapter"
        with contextlib.redirect_stdout(io.StringIO()), patch("training.common.shutil.which", return_value=None):
            manifest = execute_factory("train", {"output_dir":str(output),"lora_rank":8}, output,
                                       "lora", {}, dry_run=True, run_dir=self.root / "run")
        value = json.loads(manifest.read_text())
        self.assertEqual(value["status"], "planned")
        self.assertEqual(value["artifacts"], [])
        self.assertFalse(output.exists())
        self.assertFalse((manifest.parent / "process.log").exists())

    def factory(self, script):
        path = self.root / "fake_factory.py"
        path.write_text("#!" + sys.executable + "\n" + script)
        path.chmod(0o755)
        return str(path)

    def test_real_process_log_and_artifact_record(self):
        executable = self.factory('''import json,sys
from pathlib import Path
c=json.loads(Path(sys.argv[2]).read_text())
p=Path(c["output_dir"]);p.mkdir()
(p/"adapter_config.json").write_text(json.dumps({"peft_type":"LORA","r":c["lora_rank"]}))
(p/"adapter_model.safetensors").write_bytes(b"mock artifact used only by tests")
print("mock process output")
''')
        output = self.root / "adapter"
        with contextlib.redirect_stdout(io.StringIO()), patch("training.common.shutil.which", return_value=executable):
            manifest = execute_factory("train", {"output_dir":str(output), "lora_rank":8}, output,
                                       "lora", {}, run_dir=self.root / "run")
        value = json.loads(manifest.read_text())
        self.assertEqual(value["status"], "completed")
        self.assertEqual(len(value["artifacts"]), 2)
        self.assertIn("mock process output", (manifest.parent / "process.log").read_text())

    def test_nonzero_exit_is_recorded_as_failed(self):
        executable = self.factory("import sys\nprint('test failure')\nsys.exit(3)\n")
        run = self.root / "run"
        with contextlib.redirect_stdout(io.StringIO()), patch("training.common.shutil.which", return_value=executable):
            with self.assertRaises(RuntimeError):
                execute_factory("train", {}, self.root / "adapter", "lora", {}, run_dir=run)
        value = json.loads((run / "run_manifest.json").read_text())
        self.assertEqual(value["status"], "failed"); self.assertEqual(value["return_code"], 3)

    def test_zero_exit_without_adapter_is_not_success(self):
        executable = self.factory("print('no artifact generated')\n")
        run = self.root / "run"
        with contextlib.redirect_stdout(io.StringIO()), patch("training.common.shutil.which", return_value=executable):
            with self.assertRaises(FileNotFoundError):
                execute_factory("train", {"lora_rank":8}, self.root / "adapter", "lora", {}, run_dir=run)
        self.assertEqual(json.loads((run / "run_manifest.json").read_text())["status"], "failed")


if __name__ == "__main__": unittest.main()
