import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "jimeng_t2i.py"
SPEC = importlib.util.spec_from_file_location("jimeng_t2i", SCRIPT)
JIMENG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JIMENG)


class JimengRunnerTests(unittest.TestCase):
    def run_main(self, returned_counts, requested_count=4):
        submitted_counts = []
        task_image_counts = {}

        def fake_request(action, payload, _ak, _sk, request_timeout=60):
            self.assertGreater(request_timeout, 0)
            if action == "CVSync2AsyncSubmitTask":
                submitted_counts.append(payload["batch_size"])
                task_number = len(submitted_counts)
                task_id = f"task-{task_number}"
                task_image_counts[task_id] = returned_counts[task_number - 1]
                return {"code": 10000, "message": "Success", "data": {"task_id": task_id}}
            task_id = payload["task_id"]
            encoded = [
                base64.b64encode(f"{task_id}-image-{index}".encode()).decode()
                for index in range(task_image_counts[task_id])
            ]
            return {"code": 10000, "message": "Success", "request_id": f"request-{task_id}",
                    "data": {"status": "done", "binary_data_base64": encoded}}

        with tempfile.TemporaryDirectory() as temp_dir:
            argv = [str(SCRIPT), "--prompt", "test prompt", "--count", str(requested_count),
                    "--poll-interval", "0.001", "--output-dir", temp_dir]
            output = io.StringIO()
            with mock.patch.object(JIMENG, "signed_request", side_effect=fake_request), \
                    mock.patch.object(JIMENG.time, "sleep"), \
                    mock.patch.object(sys, "argv", argv), \
                    mock.patch.dict(os.environ, {
                        "VOLCENGINE_ACCESS_KEY_ID": "test-ak",
                        "VOLCENGINE_SECRET_ACCESS_KEY": "test-sk",
                    }), contextlib.redirect_stdout(output):
                JIMENG.main()
            result = json.loads(output.getvalue())
            manifest = json.loads(Path(result["raw_result_path"]).read_text(encoding="utf-8"))
            image_names = [Path(item["local_path"]).name for item in result["images"]]
            return result, manifest, submitted_counts, image_names

    def test_business_success_code_10000(self):
        self.assertIsNone(JIMENG.response_error({"code": 10000, "message": "Success"}))

    def test_full_batch_finishes_with_one_task(self):
        result, manifest, submitted, names = self.run_main([4])
        self.assertEqual(submitted, [4])
        self.assertEqual(result["generated_count"], 4)
        self.assertEqual(len(result["task_ids"]), 1)
        self.assertEqual(manifest["requested_count"], 4)
        self.assertEqual(names, ["image_0.png", "image_1.png", "image_2.png", "image_3.png"])

    def test_short_batches_are_filled_serially(self):
        result, manifest, submitted, names = self.run_main([1, 1, 1, 1])
        self.assertEqual(submitted, [4, 3, 2, 1])
        self.assertEqual(result["requested_count"], 4)
        self.assertEqual(result["generated_count"], 4)
        self.assertEqual(len(result["task_ids"]), 4)
        self.assertEqual(len(manifest["tasks"]), 4)
        self.assertEqual(names, ["image_0.png", "image_1.png", "image_2.png", "image_3.png"])


if __name__ == "__main__":
    unittest.main()
