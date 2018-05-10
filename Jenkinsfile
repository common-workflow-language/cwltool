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
          pybat(script: 'setup.py test --addopts --junit-xml=tests.xml', returnStatus: true)
        }

        junit 'tests.xml'
      }
    }
  }
}