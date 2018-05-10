pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'python') {
          pybat(script: 'python setup.py test', returnStatus: true, returnStdout: true)
        }

      }
    }
  }
}