#!/bin/bash
# This script runs the python script embyRemote.py and redirects output to emby.txt
export PYTHONPATH=~/Manyana:$PYTHONPATH
python ./embyRemote.py >> ./emby.txt 2>&1
