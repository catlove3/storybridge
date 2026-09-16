"""Local authenticated encryption. Never print credentials, even on failure."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def master_key_path() -> Path:
    return Path(
        os.environ.get("STORYBRIDGE_MASTER_KEY_FILE", ROOT / ".storybridge/secrets/master.key")
    )


def _fernet(path: Path) -> Fernet:
    try:
        if path.stat().st_mode & 0o077:
            raise ValueError("主密钥权限必须是 0600。")
        return Fernet(path.read_bytes().strip())
    except (OSError, ValueError) as exc:
        raise ValueError("主密钥缺失、损坏或权限不是 0600。") from exc


def decrypt_api_key(encrypted: str, key_path: Path | None = None) -> str:
    try:
        value = _fernet(key_path or master_key_path()).decrypt(encrypted.encode()).decode()
        if not value:
            raise ValueError("empty credential")
        return value
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise ValueError("模型密钥无法解密，请恢复匹配的主密钥。") from exc


def migrate(env_path: Path, key_path: Path | None = None) -> bool:
    key_path = key_path or master_key_path()
    values = dotenv_values(env_path)
    encrypted = values.get("LLM_API_KEY_ENCRYPTED")
    plain = values.get("LLM_API_KEY")
    if encrypted:
        decrypted = decrypt_api_key(encrypted, key_path)
        if plain and decrypted != plain:
            raise ValueError("加密项与明文项不一致；配置未修改。")
        if not plain and not re.search(
            r"(?m)^\s*(?:export\s+)?LLM_API_KEY\s*=", env_path.read_text()
        ):
            return False
    else:
        if not plain:
            raise ValueError("请先在 backend/.env 配置 LLM_API_KEY、地址和模型。")
        if not key_path.exists():
            key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(Fernet.generate_key())
                handle.flush()
                os.fsync(handle.fileno())
        encrypted = _fernet(key_path).encrypt(plain.encode()).decode()
        if decrypt_api_key(encrypted, key_path) != plain:
            raise ValueError("密钥迁移验证失败；配置未修改。")
    # dotenv values can span multiple lines: remove whole parsed assignments,
    # preserving all unrelated settings and comments byte-for-byte.
    from dotenv.parser import parse_stream

    with env_path.open(encoding="utf-8") as handle:
        content = "".join(
            binding.original.string
            for binding in parse_stream(handle)
            if binding.key not in {"LLM_API_KEY", "LLM_API_KEY_ENCRYPTED"}
        )
    content = content.rstrip("\n") + f"\nLLM_API_KEY_ENCRYPTED={encrypted}\n"
    descriptor, temporary = tempfile.mkstemp(dir=env_path.parent, prefix=".env-migrate-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, env_path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


if __name__ == "__main__":
    try:
        changed = migrate(ROOT / "backend/.env")
        print("模型密钥已加密。" if changed else "加密配置验证通过，无需迁移。")
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from None
