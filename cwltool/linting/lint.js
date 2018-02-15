"use strict";
var assert = require("assert");
var jshint = require("./jshint.js")

function validateJS(input) {
  var jshint_globals_obj = {}
  input.globals.forEach(function(global){
    jshint_globals_obj[global] = true;
  })

  jshint.JSHINT(
    input.code,
    {
      strict: "implied",
      esversion: 5
    },
    jshint_globals_obj
  )

  var errors = jshint.JSHINT.data().errors;

  return jshint.JSHINT.data();
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
