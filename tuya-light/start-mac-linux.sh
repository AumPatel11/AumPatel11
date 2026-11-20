#!/bin/sh
cd "$(dirname "$0")"
python3 -m pip install --user -r requirements.txt
( sleep 2; open http://localhost:8787 2>/dev/null || xdg-open http://localhost:8787 2>/dev/null ) &
python3 server.py
