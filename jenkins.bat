set BOOT2DOCKER_VM=default
set PATH=%PATH%;"C:\\Program Files\\Docker Toolbox\\"
docker-machine start %BOOT2DOCKER_VM%
REM Set the environment variables to use docker-machine and docker commands
@FOR /f "tokens=*" %i IN ('docker-machine env --shell cmd %BOOT2DOCKER_VM%') DO @%i

python setup.py test --addopts --junit-xml=tests.xml
