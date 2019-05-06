import sys
f = open(sys.argv[1], "r+")
val = int(f.read())
f.seek(0)
f.write(str(val+1))
f.close()
