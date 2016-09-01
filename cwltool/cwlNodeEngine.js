"use strict";
process.stdin.setEncoding('utf8');
var incoming = "";
process.stdin.on('data', function(chunk) {
  incoming += chunk;
  var i = incoming.indexOf("\n");
  if (i > -1) {
    var fn = JSON.parse(incoming.substr(0, i));
    incoming = incoming.substr(i+1);
    process.stdout.write(JSON.stringify(require("vm").runInNewContext(fn, {})) + "\n");
  }
});
process.stdin.on('end', process.exit);
