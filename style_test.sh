#!/bin/bash

# Checks the sources for some basic style guidelines and complexity.
#
# To let docformatter have a first pass at fixing the comment style, just run:
#
# docformatter --in-place --pre-summary-newline --blank --make-summary-multi-line --wrap-summaries 80 --wrap-descriptions 80 ......
#
# To test that docformatter didn't have to do anything, run without the --in-place
# option and check that no output was created. By default, we just test.


exit_check () {
    if [ "$1" == "0" ]; then
        echo "Passed check: $2"
    else
        echo "FAILED CHECK: $2"
        exit 1
    fi
}

check_flake8 () {
    echo "Checking sources with flake8..."
    flake8 --config=flake8.conf src
    exit_check $? "flake8"
}

check_pylint () {
    echo "Checking sources with pylint..."
    pylint src -j 0   # -j 0: Use all available processors to parallelize
    exit_check $? "pylint"
}

check_docformatter () {
    # At first, just capture the output, so we can test if any output was created at all
    echo "Checking docstrings with docformatter..."
    found_lines=$(find . \( -name '*.py' \) -exec docformatter --pre-summary-newline --blank --make-summary-multi-line --wrap-summaries 80 --wrap-descriptions 80  {} \;|wc -l)
    if [ "$found_lines" == "0" ]; then
        echo "Passed check: docformatter"
    else
        # Run the command again to display all the reported errors
        echo "FAILED CHECK: docformatter"
        find . \( -name '*.py' \) -exec docformatter --pre-summary-newline --blank --make-summary-multi-line --wrap-summaries 80 --wrap-descriptions 80  {} \;
        echo "@@@ Docformatter tests failed!"
        exit 1
    fi
}

check_docstrings () {
    echo "Checking docstrings with pydocstyle..."
    pydocstyle --add-select=D213 --ignore=D105,D106,D200,D203,D212,D405,D406,D409,D416 \
        src \
    exit_check $? "docstrings"
}

check_docstrings_tests () {
    echo "Checking docstrings in tests with pydocstyle..."
    # Ignore the big 'cache.py' file, which was generated from data.
    pydocstyle --add-select=D213 \
               --match='(?!cache).*\.py' \
               --ignore=D100,D101,D102,D103,D104,D105,D106,D107,D200,D203,D212,D405,D406,D409,D416 \
               src
    exit_check $? "docstring_tests"
}

# Starting the sub processes
pids=""

# Start the most CPU intensive one first. Note that pylint itself will also use multiple CPUs.
check_pylint &
pids+=" $!"

check_docformatter &
pids+=" $!"

check_docstrings &
pids+=" $!"

check_docstrings_tests &
pids+=" $!"

check_flake8 &
pids+=" $!"

# Waiting for completion of sub processes
# This was taken from: https://stackoverflow.com/a/29535256
any_failed="no"
for p in $pids; do
    if ! wait $p; then
        any_failed="yes"
    fi
done

if [ "$any_failed" == "yes" ]; then
    echo "*** style test failed! ***"
    exit 1
fi

echo "*** style test ok ***"
