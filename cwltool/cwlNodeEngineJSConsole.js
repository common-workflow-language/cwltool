"use strict";
function js_console_log(){
    console.error("[log] "+require("util").format.apply(this, arguments).split("\n").join("\n[log] "));
}
function js_console_err(){
    console.error("[err] "+require("util").format.apply(this, arguments).split("\n").join("\n[err] "));
}
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
	    log: js_console_log, 
	    error: js_console_err
	}
    })) + "\n");
  }
});
process.stdin.on("end", process.exit);
