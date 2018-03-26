"use strict";
process.stdin.setEncoding("utf8");
var incoming = "";
var firstInput = true;
var context = {};

process.stdin.on("data", function(chunk) {
  incoming += chunk;
  var i = incoming.indexOf("\n");
  while (i > -1) {
    try{
      var input = incoming.substr(0, i);
      incoming = incoming.substr(i+1);
      var fn = JSON.parse(input);
      if(firstInput){
        context = require("vm").runInNewContext(fn, {});
      }
      else{
        process.stdout.write(JSON.stringify(require("vm").runInNewContext(fn, context)) + "\n");
      }
    }
    catch(e){
      console.error(e);
    }
    if(firstInput){
      firstInput = false;
    }
    else{
      /*strings to indicate the process has finished*/
      console.log("r1cepzbhUTxtykz5XTC4");
      console.error("r1cepzbhUTxtykz5XTC4");
    }

    i = incoming.indexOf("\n");
  }
});
process.stdin.on("end", process.exit);
