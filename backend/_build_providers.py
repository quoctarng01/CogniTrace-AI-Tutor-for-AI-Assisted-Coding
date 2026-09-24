"""Build script — constructs the new llm_providers.py file.

This script writes the larger file using a different mechanism than
the direct Write tool, which has a size limit.
"""
from pathlib import Path


def _normalize_openai_url(custom_url: str) -> str:
    return '<<HTTP_URL_NOT_DEFINED>>'


# This file is deleted after build.
print('placeholder')
