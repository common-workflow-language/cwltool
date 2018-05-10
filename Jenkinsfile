pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        bat(script: '\'C:\\Program Files\\Python36\\python.exe\' -m virtualenv env', returnStdout: true)
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          pybat(script: 'setup.py test', returnStdout: true)
        }

      }
    }
  }
}