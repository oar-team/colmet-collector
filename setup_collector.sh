#! /bin/bash

cd colmet-collector
git pull

python -m venv .venv
source .venv/bin/activate
pip install -e .

./launch_collector.sh
