#!/bin/sh
# Maintainers: upload instance packages. Usage: tools/upload_s3.sh OUT_DIR s3://<bucket>/v1/public/
set -eu
aws s3 cp "$1" "$2" --recursive --exclude '*' --include '*.tar'
