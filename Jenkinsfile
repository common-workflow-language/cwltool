pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        bat 'python setup.py '
      }
    }
  }
}