CALL %~dp0\setup.bat
pip install pytest pytest-cov
python setup.py test --addopts "--junit-xml=tests.xml --cov=cwltool"
pip install codecov
echo %PATH%
codecov -X gcov
