#!/bin/bash

#
# Run unit tests and create a coverage report.
#
# - Uses pytest as test framework
# - Creates coverage report in terminal and HTML
#
# Usage:
#
#   $ ./run_tests.sh
# 

coverage run -m pytest
coverage html
coverage report

echo "HTML coverage report at: file://`pwd`/htmlcov/index.html"
