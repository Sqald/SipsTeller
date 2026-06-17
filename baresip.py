import os
import stat
import subprocess
import threading
from pathlib import Path
from sys import platform


class BaresipManager:
    def __init__(self, config_dir: str, on_output=None):
        self.config_dir = config_dir
        self.on_output = on_output
        self._process = None
        self._lock = threading.Lock()

    def _executable(self) -> str:
        base = Path(__file__).parent / "bin"
        if platform.startswith("win"):
            return str(base / "baresip.exe")
        if platform.startswith("darwin"):
            import shutil
            sys_exe = shutil.which("baresip")
            if sys_exe:
                return sys_exe
            return str(base / "baresip_mac")
        return "baresip"

    def _chmod(self, path: str):
        p = Path(path)
        if p.exists() and not platform.startswith("win"):
            try:
                p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass

    def start(self) -> bool:
        env = os.environ.copy()
        env["BARESIP_HOME"] = self.config_dir
        exe = self._executable()
        self._chmod(exe)
        try:
            self._process = subprocess.Popen(
                [exe, "-f", self.config_dir],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
            threading.Thread(target=self._reader, daemon=True).start()
            return True
        except (FileNotFoundError, PermissionError, OSError) as e:
            if self.on_output:
                self.on_output(f"[ERROR] baresip起動失敗: {e}")
            return False

    def _reader(self):
        for line in self._process.stdout:
            s = line.rstrip()
            if s and self.on_output:
                self.on_output(s)

    def send(self, command: str):
        with self._lock:
            if self._process and self._process.stdin:
                try:
                    self._process.stdin.write(command + "\n")
                    self._process.stdin.flush()
                except BrokenPipeError:
                    pass

    def dial(self, uri: str):       self.send(f"/dial {uri}")
    def answer(self):               self.send("/accept")
    def hangup(self):               self.send("/hangup")
    def hold(self):                 self.send("/hold")
    def resume(self):               self.send("/resume")
    def transfer(self, uri: str):   self.send(f"/transfer {uri}")
    def mute(self):                 self.send("/mute")
    def dtmf(self, digit: str):     self.send(f"/dtmf {digit}")

    def stop(self):
        self.send("/quit")
        if self._process:
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def restart(self) -> bool:
        self.stop()
        return self.start()

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None
