pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        bat(script: '\'C:\\Program Files\\Python36\\python.exe\' -m virtualenv env', returnStatus: true, returnStdout: true)
      }
    }
  }
}