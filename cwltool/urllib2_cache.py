import urllib2
import hashlib
import urlparse, urllib
import os

cache_folder = None

def path2url(path):
    return urlparse.urljoin(
      'file:', urllib.pathname2url(path))

def set_cache(new_cache_folder):
    global cache_folder
    cached_handler = CachedHTTPHandler()
    opener = urllib2.build_opener(cached_handler)
    urllib2.install_opener(opener)
    cache_folder = new_cache_folder
    if not(os.path.exists(cache_folder)):
        os.mkdir(cache_folder)


class CachedHTTPHandler(urllib2.AbstractHTTPHandler):

    handler_order = 100

    def http_open(self, req):
        cache_path = self._get_local_cachefile_path(req.get_full_url())
        cache_url = self._get_local_cachefile_url(req.get_full_url())
        if os.path.exists(cache_path+'_redirect'):
            redirected_url = open(cache_path+'_redirect','r').read()
            cache_path = self._get_local_cachefile_path(redirected_url)
            cache_url = self._get_local_cachefile_url(redirected_url)
        if not(os.path.exists(cache_path)):
            response = urllib2.HTTPHandler().http_open(req)
            code = response.code
            headers = response.headers
            if code==200:
                open(cache_path, 'w').write(response.read())
            else:
                if (code in (301, 302, 303, 307)):
                    if 'location' in headers:
                        newurl = headers.getheaders('location')[0]
                    elif 'uri' in headers:
                        newurl = headers.getheaders('uri')[0]
                    open(cache_path+'_redirect', 'w').write(newurl)
                    print newurl
                    #os.link(cache_path, self._get_local_cachefile_path(newurl))
                return response
        response = urllib2.FileHandler().file_open(urllib2.Request(cache_url))
        response.code = 200
        response.msg = "everything is ok"
        return response

    http_request = urllib2.AbstractHTTPHandler.do_request_

    def _get_local_cachefile_name(self, url):
        return hashlib.md5(url).hexdigest()

    def _get_local_cachefile_path(self, url):
        return os.path.abspath(os.path.join(cache_folder, self._get_local_cachefile_name(url)))

    def _get_local_cachefile_url(self, url):
        return path2url(self._get_local_cachefile_path(url))