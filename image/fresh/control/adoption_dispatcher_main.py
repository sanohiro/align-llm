#!/usr/bin/env python3
import os

def debug_message(message: str) -> None:
    try:
        with open("/tmp/fresh-debug", "a", encoding="ascii") as stream:
            stream.write(message + "\n")
    except (OSError, UnicodeError):
        pass

debug_message("python: main start")
from request6_adoption import main
debug_message("python: import passed")

try:
    os.fstat(11)
except OSError:
    debug_message("python: bundle fd missing")

debug_message("python: calling dispatch")
raise SystemExit(main())
