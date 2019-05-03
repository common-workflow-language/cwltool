set PATH=%PATH%;"C:\\Program Files\\Docker Toolbox\\"
docker-machine start default
REM Set the environment variables to use docker-machine and docker commands
FOR /f "tokens=*" %%i IN ('docker-machine env --shell cmd default') DO %%i
docker version
python setup.py test --addopts "--junit-xml=tests.xml --cov-report xml --cov cwltool"
pip install codecov
codecov
