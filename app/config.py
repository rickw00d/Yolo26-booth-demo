"""設定檔載入:先讀 config.yaml,再疊加平台設定檔(例如 config.gb10.yaml)。

指定平台設定檔的方式(擇一):
  python run.py --profile config.gb10.yaml
  DEMO_PROFILE=config.gb10.yaml python run.py
平台設定檔只需要寫和 config.yaml 不同的欄位,巢狀欄位會逐層合併。
"""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
_profile: str | None = None


def set_profile(path: str | None):
    global _profile
    _profile = path


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _read(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def profile_path() -> Path | None:
    p = _profile or os.environ.get("DEMO_PROFILE")
    if not p:
        return None
    path = Path(p)
    return path if path.is_absolute() else ROOT / path


def load_config(path: str | Path | None = None) -> dict:
    cfg = _read(Path(path) if path else ROOT / "config.yaml")
    prof = profile_path()
    if prof is not None:
        if not prof.exists():
            raise FileNotFoundError(f"找不到平台設定檔:{prof}")
        cfg = _merge(cfg, _read(prof))
        cfg["_profile"] = prof.name
    return cfg
