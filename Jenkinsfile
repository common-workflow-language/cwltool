pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          pybat(script: 'pip install .', returnStdout: true)
          pybat '''
		set BOOT2DOCKER_VM=default
		set PATH=%PATH%;"C:\\Program Files\\Docker Toolbox\\"
		docker-machine start %BOOT2DOCKER_VM%
		REM Set the environment variables to use docker-machine and docker commands
		@FOR /f "tokens=*" %i IN ('docker-machine env --shell cmd %BOOT2DOCKER_VM%') DO @%i
		setup.py test --addopts --junit-xml=tests.xml
          '''
        }

      }
    }
  }
  post {
    always {
      junit 'tests.xml'

    }

  }
}
