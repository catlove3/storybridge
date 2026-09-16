"""Install an official cloudflared release into the project runtime directory."""

from __future__ import annotations

import hashlib
import io
import platform
import tarfile
from pathlib import Path

import httpx


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    target = root / ".storybridge/runtime/cloudflared"
    if target.is_file():
        return
    system = platform.system().lower()
    machine = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
    if system not in {"linux", "darwin"} or not machine:
        raise SystemExit("请先安装 cloudflared 并将它加入 PATH。")
    asset_name = f"cloudflared-{system}-{machine}" + (".tgz" if system == "darwin" else "")

    def download(trust_env: bool):
        with httpx.Client(follow_redirects=True, timeout=120, trust_env=trust_env) as client:
            response = client.get(
                "https://api.github.com/repos/cloudflare/cloudflared/releases/latest"
            )
            response.raise_for_status()
            asset = next(a for a in response.json()["assets"] if a["name"] == asset_name)
            response = client.get(asset["browser_download_url"])
            response.raise_for_status()
            return asset, response.content

    try:
        asset, archive = download(True)
    except httpx.TransportError:
        # Only public release downloads: a stale shell proxy need not prevent
        # direct HTTPS access. Never change proxy settings for model requests.
        asset, archive = download(False)
    digest = asset.get("digest", "")
    if digest != "sha256:" + hashlib.sha256(archive).hexdigest():
        raise SystemExit("cloudflared 校验失败或发布方未提供摘要，请手动安装。")
    binary = archive
    if system == "darwin":
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            member = next(
                m for m in bundle.getmembers() if m.name in {"cloudflared", "./cloudflared"}
            )
            handle = bundle.extractfile(member)
            if handle is None:
                raise SystemExit("cloudflared 压缩包中缺少程序。")
            binary = handle.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download")
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    temporary.replace(target)


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, OSError, StopIteration, KeyError):
        raise SystemExit(
            "无法下载官方 cloudflared，请检查网络或代理，或手动安装到 PATH。"
        ) from None
