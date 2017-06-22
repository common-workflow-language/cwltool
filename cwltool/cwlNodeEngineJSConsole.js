"use strict";
process.stdin.setEncoding("utf8");
var incoming = "";
process.stdin.on("data", function(chunk) {
  incoming += chunk;
  var i = incoming.indexOf("\n");
  if (i > -1) {
    var fn = JSON.parse(incoming.substr(0, i));
    incoming = incoming.substr(i+1);
    process.stdout.write(JSON.stringify(require("vm").runInNewContext(fn, {
	console: {
	    log: function(){
		console.error("[log] "+util.format.apply(this, arguments).split("\n").join("\n[log] "));
	    }, 
	    error: function(){
		console.error("[err] "+util.format.apply(this, arguments).split("\n").join("\n[err] "));
	    }
	}
    })) + "\n");
  }
});
process.stdin.on("end", process.exit);
