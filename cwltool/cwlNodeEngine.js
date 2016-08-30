#!/usr/bin/env nodejs

"use strict";

process.stdin.setEncoding('utf8');

var incoming = "";

process.stdin.on('readable', function() {
  var chunk = process.stdin.read();
    if (chunk !== null) {
        incoming += chunk;
        var i = incoming.indexOf("\n");
        if (i > -1) {
            var fn = JSON.parse(incoming.substr(0, i));
            incoming = incoming.substr(i+1);
            process.stdout.write(JSON.stringify(require("vm").runInNewContext(fn, {})) + "\n");
        }
    }
});
