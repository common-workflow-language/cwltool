pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        bat(script: 'python -m virtualenv env', returnStatus: true, returnStdout: true)
      }
    }
  }
}