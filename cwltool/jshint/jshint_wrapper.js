"use strict";
// set a global object, in order for jshint to work
var global = this;

function validateJS(input) {
  var jshintGlobalsObj = {};
  input.globals.forEach(function (global) {
    jshintGlobalsObj[global] = true;
  })
  var includewarnings;

  if (input.options.includewarnings !== undefined) {
    includewarnings = input.options.includewarnings;
    delete input.options.includewarnings;
  }

  JSHINT(
    input.code,
    input.options,
    jshintGlobalsObj
  )

  var jshintData = JSHINT.data();
  if (jshintData.errors !== undefined) {
    if (includewarnings !== undefined) {
      jshintData.errors = jshintData.errors.filter(function (error) {
        return includewarnings.indexOf(error.code) !== -1 || error.code[0] == "E";
      })
    }

    jshintData.errors.forEach(function (error) {
      if (error.code == "W104" || error.code == "W119") {
        if (error.code == "W104"){
          var jslint_suffix = " (use 'esversion: 6') or Mozilla JS extensions (use moz)."
        }
        else{
          var jslint_suffix = " (use 'esversion: 6')"
        }

        error.reason = error.reason.slice(0, -jslint_suffix.length - 1) +
          ". CWL only supports ES5.1";
      }
    })
  }

  return jshintData;
}
