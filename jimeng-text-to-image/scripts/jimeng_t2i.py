#!/usr/bin/env python3
"""Volcengine Jimeng text-to-image 3.0 runner using only the Python stdlib."""

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HOST = "visual.volcengineapi.com"
ENDPOINT = f"https://{HOST}"
VERSION = "2022-08-31"
REGION = "cn-north-1"
SERVICE = "cv"
REQ_KEY = "jimeng_t2i_v30"


def parser():
    p = argparse.ArgumentParser(description="Generate images with Volcengine Jimeng 3.0")
    p.add_argument("--payload-file", type=Path, help="UTF-8 JSON file containing non-secret inputs")
    p.add_argument("--prompt")
    p.add_argument("--negative-prompt")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--count", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--use-pre-llm", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--add-logo", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--poll-interval", type=float)
    p.add_argument("--timeout", type=float)
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--dry-run", action="store_true")
    return p


DEFAULTS = {
    "negative_prompt": "",
    "width": 1328,
    "height": 1328,
    "count": 4,
    "seed": -1,
    "use_pre_llm": True,
    "add_logo": False,
    "poll_interval": 3,
    "timeout": 180,
    "output_dir": "outputs",
}

ALLOWED_PAYLOAD_KEYS = {"prompt", *DEFAULTS}
FORBIDDEN_SECRET_KEYS = {"ak", "sk", "access_key_id", "secret_access_key"}


def load_args():
    a = parser().parse_args()
    payload = {}
    if a.payload_file:
        try:
            payload = json.loads(a.payload_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            fail(f"cannot read payload file: {e}", "INVALID_PAYLOAD_FILE")
        if not isinstance(payload, dict):
            fail("payload file must contain a JSON object", "INVALID_PAYLOAD_FILE")
        secret_keys = FORBIDDEN_SECRET_KEYS.intersection(payload)
        if secret_keys:
            fail("payload file must not contain credentials", "SECRET_IN_PAYLOAD")
        unknown_keys = set(payload).difference(ALLOWED_PAYLOAD_KEYS)
        if unknown_keys:
            fail(f"unknown payload fields: {', '.join(sorted(unknown_keys))}", "INVALID_PAYLOAD_FIELD")
    for key in ALLOWED_PAYLOAD_KEYS:
        cli_value = getattr(a, key, None)
        value = cli_value if cli_value is not None else payload.get(key, DEFAULTS.get(key))
        setattr(a, key, value)
    a.output_dir = Path(a.output_dir)
    return a


def fail(message, code="LOCAL_ERROR", request_id=None, exit_code=2):
    print(json.dumps({"status": "error", "code": str(code), "message": message,
                      "request_id": request_id}, ensure_ascii=False))
    raise SystemExit(exit_code)


def validate(a):
    if not isinstance(a.prompt, str) or not a.prompt.strip():
        fail("prompt is required", "MISSING_PROMPT")
    if len(a.prompt) > 800:
        fail("prompt exceeds 800 characters", "PROMPT_TOO_LONG")
    if len(a.prompt) > 120:
        print("warning: prompt exceeds the recommended 120 characters", file=sys.stderr)
    if not (1 <= a.count <= 4):
        fail("count must be between 1 and 4", "INVALID_COUNT")
    if a.width <= 0 or a.height <= 0 or a.timeout <= 0 or a.poll_interval <= 0:
        fail("dimensions, timeout, and poll interval must be positive", "INVALID_ARGUMENT")


def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def signed_request(action, payload, ak, sk, request_timeout=60):
    now = dt.datetime.now(dt.timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = now.strftime("%Y%m%d")
    query = urlencode({"Action": action, "Version": VERSION})
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body_hash = hashlib.sha256(body).hexdigest()
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_headers = ("content-type:application/json\n" + f"host:{HOST}\n" +
                         f"x-content-sha256:{body_hash}\n" + f"x-date:{x_date}\n")
    canonical_request = "POST\n/\n" + query + "\n" + canonical_headers + "\n" + signed_headers + "\n" + body_hash
    scope = f"{short_date}/{REGION}/{SERVICE}/request"
    string_to_sign = "HMAC-SHA256\n" + x_date + "\n" + scope + "\n" + hashlib.sha256(canonical_request.encode()).hexdigest()
    k_date = sign(sk.encode("utf-8"), short_date)
    k_region = sign(k_date, REGION)
    k_service = sign(k_region, SERVICE)
    k_signing = sign(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = f"HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    headers = {"Content-Type": "application/json", "Host": HOST, "X-Date": x_date,
               "X-Content-Sha256": body_hash, "Authorization": auth}
    req = Request(f"{ENDPOINT}/?{query}", data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=request_timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            fail(f"HTTP {e.code}: {raw[:300]}", f"HTTP_{e.code}")
    except URLError as e:
        fail(f"network error: {e.reason}", "NETWORK_ERROR")


def response_error(obj):
    meta = obj.get("ResponseMetadata") or obj.get("response_metadata") or {}
    err = meta.get("Error") or meta.get("error") or {}
    code = obj.get("code", err.get("Code", err.get("code", 0)))
    msg = obj.get("message", err.get("Message", err.get("message", "")))
    request_id = obj.get("request_id") or meta.get("RequestId") or meta.get("request_id")
    # Visual API business responses use 10000 for success, while the
    # ResponseMetadata-style envelope uses 0/no code for success.
    if str(code) not in ("0", "10000", "", "None") or err:
        return str(code), msg or "Volcengine API error", request_id
    return None


def extract_data(obj):
    return obj.get("data") or obj.get("Result") or obj.get("result") or {}


def request_id_of(result):
    meta = result.get("ResponseMetadata") or {}
    return result.get("request_id") or meta.get("RequestId")


def save_task_results(result, output_dir, task_number, start_index, limit):
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"result_task_{task_number:02d}.json"
    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    data = extract_data(result)
    urls = data.get("image_urls") or data.get("image_url") or []
    if isinstance(urls, str):
        urls = [urls]
    binaries = data.get("binary_data_base64") or []
    if isinstance(binaries, str):
        binaries = [binaries]
    available = min(max(len(urls), len(binaries)), limit)
    images = []
    for offset in range(available):
        index = start_index + offset
        item = {"image_index": index, "url": None, "local_path": None}
        if offset < len(urls):
            item["url"] = urls[offset]
        if offset < len(binaries):
            path = output_dir / f"image_{index}.png"
            try:
                path.write_bytes(base64.b64decode(binaries[offset], validate=True))
            except (ValueError, TypeError) as e:
                fail(f"invalid base64 image data: {e}", "INVALID_IMAGE_DATA", request_id_of(result))
            item["local_path"] = str(path.resolve())
        images.append(item)
    return images, str(raw_path.resolve())


def submit_task(a, ak, sk, batch_size):
    payload = {"req_key": REQ_KEY, "prompt": a.prompt, "negative_prompt": a.negative_prompt,
               "width": a.width, "height": a.height, "seed": a.seed,
               "use_pre_llm": a.use_pre_llm, "return_url": True,
               "logo_info": {"add_logo": a.add_logo}, "req_schedule_conf": "general_v20_9B_rephraser",
               "batch_size": batch_size}
    submitted = signed_request("CVSync2AsyncSubmitTask", payload, ak, sk)
    error = response_error(submitted)
    if error:
        fail(error[1], error[0], error[2])
    data = extract_data(submitted)
    task_id = data.get("task_id") or submitted.get("task_id")
    if not task_id:
        fail("submit response did not contain task_id", "MISSING_TASK_ID", request_id_of(submitted))
    return task_id


def wait_for_task(a, ak, sk, task_id):
    deadline = time.monotonic() + a.timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            fail("timed out waiting for generation result", "TIMEOUT")
        time.sleep(min(a.poll_interval, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            fail("timed out waiting for generation result", "TIMEOUT")
        result = signed_request("CVSync2AsyncGetResult", {"req_key": REQ_KEY, "task_id": task_id},
                                ak, sk, request_timeout=min(60, max(1, remaining)))
        error = response_error(result)
        if error:
            fail(error[1], error[0], error[2])
        status = str(extract_data(result).get("status", "")).lower()
        if status in ("done", "success", "completed"):
            return result
        if status in ("failed", "error", "cancelled"):
            fail(f"generation ended with status {status}", "GENERATION_FAILED", request_id_of(result))


def main():
    a = load_args()
    validate(a)
    submit_payload = {"req_key": REQ_KEY, "prompt": a.prompt, "negative_prompt": a.negative_prompt,
                      "width": a.width, "height": a.height, "seed": a.seed,
                      "use_pre_llm": a.use_pre_llm, "return_url": True,
                      "logo_info": {"add_logo": a.add_logo}, "req_schedule_conf": "general_v20_9B_rephraser",
                      "batch_size": a.count}
    if a.dry_run:
        print(json.dumps({"status": "dry_run", "endpoint": ENDPOINT,
                          "submit_action": "CVSync2AsyncSubmitTask", "payload": submit_payload}, ensure_ascii=False))
        return
    ak = os.getenv("VOLCENGINE_ACCESS_KEY_ID")
    sk = os.getenv("VOLCENGINE_SECRET_ACCESS_KEY")
    if not ak or not sk:
        fail("set VOLCENGINE_ACCESS_KEY_ID and VOLCENGINE_SECRET_ACCESS_KEY", "MISSING_CREDENTIALS")
    images = []
    tasks = []
    raw_result_paths = []
    while len(images) < a.count:
        if tasks:
            time.sleep(a.poll_interval)
        remaining = a.count - len(images)
        task_id = submit_task(a, ak, sk, remaining)
        result = wait_for_task(a, ak, sk, task_id)
        task_images, raw_path = save_task_results(
            result, a.output_dir, len(tasks) + 1, len(images), remaining)
        request_id = request_id_of(result)
        tasks.append({"task_id": task_id, "request_id": request_id,
                      "image_count": len(task_images), "raw_result_path": raw_path})
        raw_result_paths.append(raw_path)
        if not task_images:
            fail(f"task completed without images ({len(images)}/{a.count} saved)",
                 "EMPTY_RESULT", request_id)
        images.extend(task_images)

    manifest = {"status": "done", "requested_count": a.count, "generated_count": len(images),
                "tasks": tasks, "images": images}
    a.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = a.output_dir / "result.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "done", "task_id": tasks[0]["task_id"],
                      "task_ids": [task["task_id"] for task in tasks],
                      "request_id": tasks[-1]["request_id"],
                      "request_ids": [task["request_id"] for task in tasks],
                      "requested_count": a.count, "generated_count": len(images),
                      "images": images, "raw_result_path": str(manifest_path.resolve()),
                      "raw_result_paths": raw_result_paths}, ensure_ascii=False))


if __name__ == "__main__":
    main()
