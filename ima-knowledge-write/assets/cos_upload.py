#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯云 COS 单文件上传（使用临时密钥）—— ima 知识库本地文件入库的第二步。

用法：全部参数走环境变量，脚本本身不含任何密钥，可安全复用。
  COS_SECRET_ID / COS_SECRET_KEY / COS_TOKEN / COS_BUCKET / COS_REGION
  COS_KEY / COS_CONTENT_TYPE / LOCAL_FILE

依赖：仅标准库。
"""
import hashlib
import hmac
import os
import ssl
import sys
import urllib.parse
import urllib.request


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"[FATAL] 缺少环境变量 {name}")
    return v


def hmac_sha1_hex(key: str, msg: str) -> str:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha1).hexdigest()


def url_encode(s: str, keep_slash: bool = False) -> str:
    safe = "/" if keep_slash else ""
    return urllib.parse.quote(s, safe=safe)


def main() -> int:
    secret_id = env("COS_SECRET_ID")
    secret_key = env("COS_SECRET_KEY")
    token = env("COS_TOKEN")
    bucket = env("COS_BUCKET")
    region = env("COS_REGION")
    cos_key = env("COS_KEY")
    content_type = env("COS_CONTENT_TYPE")
    local_file = env("LOCAL_FILE")

    if not os.path.isfile(local_file):
        sys.exit(f"[FATAL] 本地文件不存在: {local_file}")
    with open(local_file, "rb") as fh:
        body = fh.read()

    host = f"{bucket}.cos.{region}.myqcloud.com"
    url_path = "/" + url_encode(cos_key, keep_slash=True)
    url = f"https://{host}{url_path}"

    now = int(__import__("time").time())
    sign_time = f"{now};{now + 3600}"
    key_time = sign_time

    sign_key = hmac_sha1_hex(secret_key, key_time)

    headers = {
        "host": host,
        "content-type": content_type,
        "x-cos-security-token": token,
    }
    header_list = ";".join(sorted(headers.keys()))
    http_headers = "&".join(
        f"{url_encode(k).lower()}={url_encode(v)}" for k, v in sorted(headers.items())
    )

    http_string = f"put\n{url_path}\n\n{http_headers}\n"
    string_to_sign = f"sha1\n{sign_time}\n{hashlib.sha1(http_string.encode('utf-8')).hexdigest()}\n"
    signature = hmac_sha1_hex(sign_key, string_to_sign)

    authorization = (
        "q-sign-algorithm=sha1"
        f"&q-ak={secret_id}"
        f"&q-sign-time={sign_time}"
        f"&q-key-time={key_time}"
        f"&q-header-list={header_list}"
        "&q-url-param-list="
        f"&q-signature={signature}"
    )

    print(f"[info] 本地上传字节 = {len(body)}")
    print(f"[info] 目标 = {url}")

    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Host", host)
    req.add_header("Content-Type", content_type)
    req.add_header("x-cos-security-token", token)
    req.add_header("Authorization", authorization)
    req.add_header("Content-Length", str(len(body)))

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            print(f"[result] HTTP {resp.status}")
            for k, v in resp.headers.items():
                if k.lower() in ("etag", "x-cos-request-id", "content-length"):
                    print(f"[result] {k}: {v}")
        return 0
    except urllib.error.HTTPError as e:
        print(f"[FATAL] HTTP {e.code}")
        print(e.read().decode("utf-8", "replace")[:2000])
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[FATAL] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
