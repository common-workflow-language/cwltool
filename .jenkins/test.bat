CALL %~dp0\setup.bat
pip install -rrequirements.txt
pip install -e .
pip install -U codecov pytest-xdist pytest-cov -rtest-requirements.txt
python -m coverage run --parallel-mode -m pytest --strict -p no:cacheprovider --junit-xml=tests.xml
python -m coverage combine
python -m coverage report
python -m coverage xml
pip install codecov
python -m codecov --file coverage.xml -X gcov
