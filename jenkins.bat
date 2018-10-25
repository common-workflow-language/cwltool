set PATH=%PATH%;"C:\\Program Files\\Docker Toolbox\\"
docker-machine start default
REM Set the environment variables to use docker-machine and docker commands
FOR /f "tokens=*" %%i IN ('docker-machine env --shell cmd default') DO %%i
FOR /f "tokens=*" %%i IN ('docker-machine env --shell cmd default') DO %%i
docker version
pip install -U codecov pytest-xdist pytest-cov galaxy-lib -rtest-requirements.txt
python -m coverage run --parallel-mode -m pytest --strict -p no:cacheprovider --junit-xml=tests.xml
python -m coverage combine
python -m coverage report
python -m coverage xml
pip install codecov
python -m codecov --file coverage.xml 
