#!/usr/bin/env python3
import os

from adoption_namespace import main

try:
    os.close(11)
except OSError:
    pass

raise SystemExit(main())
