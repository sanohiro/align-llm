#!/usr/bin/env python3
import os

from request6_adoption import main

try:
    os.close(11)
except OSError:
    pass

raise SystemExit(main())
