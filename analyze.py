#!/usr/bin/env python3
"""WhatsApp chat analyzer.

    python analyze.py sample_chat.txt --open

Standard library only — no pip install needed.
"""

import sys

from whatsapp_analyzer.cli import main

if __name__ == "__main__":
    sys.exit(main())
