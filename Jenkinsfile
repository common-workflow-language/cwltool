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
          pybat(script: 'setup.py test', returnStdout: true)
        }

      }
    }
  }
}