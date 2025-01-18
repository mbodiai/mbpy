"""Copied and modified to work with asyncio and windows from pexpect."""
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from queue import Empty, Queue
from typing import TypeVar

from mbpy.expect.exceptions import EOF
from mbpy.expect.spawnbase import SpawnBase

string_types = (str, bytes)
AnyStrT = TypeVar("AnyStrT", str, bytes)
AnyStrT_co = TypeVar("AnyStrT_co", str, bytes, covariant=True)
PY3: bool
text_type: type
AnyStr  = str  | bytes



class PopenSpawn(SpawnBase):
    def __init__(
        self,
        cmd,
        args=[],
        timeout=30,
        maxread=2000,
        searchwindowsize=None,
        logfile=None,
        cwd=None,
        env=None,
        encoding=None,
        codec_errors="strict",
        preexec_fn=None,
    ):
        super().__init__(
            timeout=timeout,
            maxread=maxread,
            searchwindowsize=searchwindowsize,
            logfile=logfile,
            encoding=encoding,
            codec_errors=codec_errors,
        )

        if encoding is None:
            self.crlf = os.linesep.encode("ascii")
        else:
            self.crlf = self.string_type(os.linesep)

        kwargs = {
            "bufsize": 0,
            "stdin": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdout": subprocess.PIPE,
            "cwd": cwd,
            "preexec_fn": preexec_fn,
            "env": env,
        }

        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        # Fix command handling
        if isinstance(cmd, (str, bytes)) and not cmd:
            cmd = "echo"  # Default command if empty
        elif isinstance(cmd, (list, tuple)) and not cmd:
            cmd = ["echo"]
            
        if isinstance(cmd, (str, bytes)):
            if args:
                cmd = [str(cmd)] + [str(a) for a in args]
            elif sys.platform != "win32":
                cmd = shlex.split(str(cmd))
            else:
                cmd = str(cmd)  # Keep as string for Windows
        
        self.proc = subprocess.Popen(cmd, **kwargs)
        self.pid = self.proc.pid
        self.closed = False
        self._buf = self.string_type()

        self._read_queue = Queue()
        self._read_thread = threading.Thread(target=self._read_incoming)
        self._read_thread.daemon = True
        self._read_thread.start()

    _read_reached_eof = False

    def read_nonblocking(self, size, timeout):
        buf = self._buf
        if self._read_reached_eof:
            if buf:
                self._buf = buf[size:]
                return buf[:size]
            self.flag_eof = True
            raise EOF("End Of File (EOF).")

        if timeout == -1:
            timeout = self.timeout
        elif timeout is None:
            timeout = 1e6

        t0 = time.time()
        while (time.time() - t0) < timeout and size and len(buf) < size:
            try:
                incoming = self._read_queue.get_nowait()
            except Empty:
                break
            else:
                if incoming is None:
                    self._read_reached_eof = True
                    break

                buf += self._decoder.decode(incoming, final=False)

        r, self._buf = buf[:size], buf[size:]

        self._log(r, "read")
        return r

    def _read_incoming(self):
        fileno = self.proc.stdout.fileno()
        while 1:
            buf = b""
            try:
                buf = os.read(fileno, 1024)
            except OSError as e:
                self._log(e, "read")

            if not buf:
                self._read_queue.put(None)
                return

            self._read_queue.put(buf)

    def write(self, s) -> None:
        self.send(s)

    def writelines(self, sequence) -> None:
        for s in sequence:
            self.send(s)

    def send(self, s):
        s = self._coerce_send_string(s)
        self._log(s, "send")

        b = self._encoder.encode(s, final=False)

        return self.proc.stdin.write(b)


    def sendline(self, s=""):
        n = self.send(s)
        return n + self.send(self.linesep)

    def wait(self):
        status = self.proc.wait()
        if status >= 0:
            self.exitstatus = status
            self.signalstatus = None
        else:
            self.exitstatus = None
            self.signalstatus = -status
        self.terminated = True
        return status

    def kill(self, sig) -> None:
        if sys.platform == "win32":
            if sig in [signal.SIGINT, signal.CTRL_C_EVENT]:
                sig = signal.CTRL_C_EVENT
            elif sig in [signal.SIGBREAK, signal.CTRL_BREAK_EVENT]:
                sig = signal.CTRL_BREAK_EVENT
            else:
                sig = signal.SIGTERM

        os.kill(self.proc.pid, sig)

    def close(self) -> None:
        self.proc.send_signal(signal.SIGINT)

    def sendeof(self) -> None:
        self.proc.stdin.close()
