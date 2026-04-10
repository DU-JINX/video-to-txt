#!/usr/bin/env python3
"""视频转写 HTTP 微服务入口."""
from __future__ import annotations

import os

import uvicorn

from api.routes import app

_PORT = int(os.getenv('TRANSCRIBE_PORT', '8765'))

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=_PORT, timeout_keep_alive=600)
