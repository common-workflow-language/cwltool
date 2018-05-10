pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'C:\\Users\\Dan\\AppData\\Local\\Programs\\Python\\Python36\\python.exe') {
          pybat(script: 'python setup.py test', returnStatus: true, returnStdout: true)
        }

      }
    }
  }
}