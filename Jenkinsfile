pipeline {
  agent {
    node {
      label 'windows'
    }
  environment {
    CODECOV_TOKEN = credentials('jenkins-codecov-tokeN')
  }

  }
  options {
    timeout(30)
  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          bat(script: 'pip install .', returnStdout: true)
          bat 'jenkins.bat'
          git 'https://github.com/common-workflow-language/common-workflow-language.git'
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
