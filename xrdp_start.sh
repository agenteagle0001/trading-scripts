#!/bin/sh
# xrdp X session start script

export DESKTOP_SESSION=xfce
export XDG_CURRENT_DESKTOP=XFCE
export XDG_SESSION_TYPE=x11

# Start XFCE
exec startxfce4
