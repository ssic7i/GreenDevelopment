# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Serhii Sheiko
"""Keep a process-group leader alive until the controller cleans its workers."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading


def controller_gone():
    sys.stdin.buffer.read()
    # This process created the session/group; EOF means its controller is gone.
    os.killpg(os.getpgrp(), signal.SIGTERM)


def main():
    status=Path(sys.argv[1])
    threading.Thread(target=controller_gone,daemon=True).start()
    try:
        child=subprocess.Popen(sys.argv[2:],stdin=subprocess.DEVNULL)
        code=child.wait()
        code=128-code if code<0 else code
    except OSError as exc:
        print(str(exc),file=sys.stderr)
        code=127
    temp=status.with_suffix('.pending')
    with temp.open('x') as handle:
        json.dump({'exit_code':code},handle)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temp,status)
    # The leader remains alive even if the payload has left background workers.
    threading.Event().wait()


if __name__=='__main__': main()
