"use strict";
var jshint = require("./jshint.js");

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

  jshint.JSHINT(
    input.code,
    input.options,
    jshintGlobalsObj
  )

  var jshintData = jshint.JSHINT.data();
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


process.stdin.setEncoding("utf8");
var incoming = "";
process.stdin.on("data", function (chunk) {
  incoming += chunk;
  var i = incoming.indexOf("\n");
  if (i > -1) {
    try {
      var input = incoming.substr(0, i);
      console.log(JSON.stringify(validateJS(JSON.parse(input))));

      incoming = incoming.substr(i + 1);
    }
    catch (e) {
      console.error(e)
    }
    /*strings to indicate the process has finished*/
    console.log("r1cepzbhUTxtykz5XTC4");
    console.error("r1cepzbhUTxtykz5XTC4");
  }
});
process.stdin.on("end", process.exit);
