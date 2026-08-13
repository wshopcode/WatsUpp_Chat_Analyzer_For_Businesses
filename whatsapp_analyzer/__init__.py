"""WhatsApp chat analyzer — parse an export, anonymise it, visualise it.

Standard library only. Nothing is uploaded anywhere.
"""

from .parser import parse_file, parse_lines, Chat, Message
from .anonymize import anonymize
from .analytics import analyse, Report
from .report import build_html

__version__ = "1.0.0"
__all__ = ["parse_file", "parse_lines", "Chat", "Message",
           "anonymize", "analyse", "Report", "build_html"]
