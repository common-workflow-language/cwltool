setup.bat
python setup.py test --addopts "--junit-xml=tests.xml --cov-report xml --cov cwltool"
pip install codecov
codecov
