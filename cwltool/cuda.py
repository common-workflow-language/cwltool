import subprocess
import xml.dom.minidom

def cuda_version_and_device_count():
    try:
        res = subprocess.run(["nvidia-smi", "-q", "-x"], capture_output=True)
    except:
        return ('', 0)
    out = res.stdout
    dm = xml.dom.minidom.parseString(out)
    ag = dm.getElementsByTagName("attached_gpus")[0].firstChild
    cv = dm.getElementsByTagName("cuda_version")[0].firstChild
    return (cv.data, int(ag.data))

def cuda_check(cuda_req):
    vmin = cuda_req["cudaVersionMin"]
    version, devices = cuda_version_and_device_count()
    if float(version) < float(vmin):
        return 0
    dmin = cuda_req.get("deviceCountMin", 1)
    dmax = cuda_req.get("deviceCountMax", dmin)
    if devices < dmin:
        return 0
    return min(dmax, devices)
