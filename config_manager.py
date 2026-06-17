import configparser
from pathlib import Path

_DEFAULTS = {
    "appearance": {"bgcolor": "#FFFFFF"},
    "window": {
        "width_main":   "460",
        "height_main":  "720",
        "width_numpad": "280",
        "height_numpad":"460",
    },
    "sip": {
        "domain":    "",
        "port":      "5060",
        "username":  "",
        "password":  "",
        "auth_user": "",      # 空白の場合はusernameと同じ
        "transport": "udp",
        "park_ext":  "",      # パーク転送先内線番号
    },
    "admin": {"password": ""},
}


class ConfigManager:
    def __init__(self, config_dir: Path = None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / "Documents" / "sipteller"
        self.path = self.config_dir / "config.ini"
        self._cp = configparser.ConfigParser()
        self._init()

    def _init(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._cp.read(self.path, encoding="utf-8")
        for section, values in _DEFAULTS.items():
            if not self._cp.has_section(section):
                self._cp.add_section(section)
            for key, val in values.items():
                if not self._cp.has_option(section, key):
                    self._cp.set(section, key, val)
        self._write()

    def _write(self):
        with open(self.path, "w", encoding="utf-8") as f:
            self._cp.write(f)

    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self._cp.get(section, key, fallback=fallback)

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        return self._cp.getint(section, key, fallback=fallback)

    def set(self, section: str, key: str, value) -> None:
        if not self._cp.has_section(section):
            self._cp.add_section(section)
        self._cp.set(section, key, str(value))

    def save(self):
        self._write()

    def is_sip_configured(self) -> bool:
        d = self.get("sip", "domain")
        u = self.get("sip", "username")
        return bool(d and d not in ("0.0.0.0", "") and u)

    def write_baresip_accounts(self) -> bool:
        if not self.is_sip_configured():
            return False
        u         = self.get("sip", "username")
        d         = self.get("sip", "domain")
        pw        = self.get("sip", "password")
        port      = self.get("sip", "port", "5060")
        auth_user = self.get("sip", "auth_user") or u
        transport = self.get("sip", "transport") or "udp"
        dom = f"{d}:{port}" if port and port != "5060" else d
        params = f"auth_user={auth_user};auth_pass={pw};transport={transport}"
        # パラメータを <> の外に書くことでRequest-URIに含まれなくなる
        # → HA2 = MD5("REGISTER:sip:domain") が正しく計算される
        (self.config_dir / "accounts").write_text(
            f"<sip:{u}@{dom}>;{params}\n", encoding="utf-8"
        )
        self.write_baresip_config()
        return True

    def write_baresip_config(self) -> None:
        module_path = self._find_baresip_module_path()
        config = self.config_dir / "config"
        content = config.read_text(encoding="utf-8") if config.exists() else ""
        import re
        new_line = f"module_path\t\t{module_path}"
        if re.search(r"^module_path\s", content, re.MULTILINE):
            content = re.sub(r"^module_path\s.*$", new_line, content, flags=re.MULTILINE)
        else:
            content = new_line + "\n" + content
        config.write_text(content, encoding="utf-8")

    @staticmethod
    def _find_baresip_module_path() -> str:
        from sys import platform
        candidates = []
        if platform.startswith("darwin"):
            candidates = [
                "/opt/homebrew/opt/baresip/lib/baresip/modules",
                "/opt/homebrew/lib/baresip/modules",
                "/usr/local/opt/baresip/lib/baresip/modules",
                "/usr/local/lib/baresip/modules",
            ]
        else:
            candidates = [
                "/usr/lib/baresip/modules",
                "/usr/local/lib/baresip/modules",
            ]
        for p in candidates:
            if Path(p).is_dir():
                return p
        # fallback: ask brew
        try:
            import subprocess
            r = subprocess.run(["brew", "--prefix", "baresip"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return str(Path(r.stdout.strip()) / "lib" / "baresip" / "modules")
        except Exception:
            pass
        return candidates[0] if candidates else "/usr/lib/baresip/modules"
