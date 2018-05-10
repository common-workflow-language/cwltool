pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'C:\\Program Files\\Python36\\python.exe') {
          pybat(script: 'python setup.py test', returnStatus: true, returnStdout: true)
        }

      }
    }
  }
}