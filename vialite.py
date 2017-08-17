import requests
import traceback
import pyramid
import logging
import re
import time
from urlparse import urlparse, urljoin, parse_qs
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='vialite.log',level=logging.DEBUG
                    )
logger = logging.getLogger('')
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logger.addHandler(console)

#server_scheme = 'http'
#server_host = '10.0.0.9'  # for local testing
#server_port = 8000

server_scheme = 'http'
server_host = 'localhost'  
server_port = 8000

if server_port is None:
    server = '%s://%s' % (server_scheme, server_host)
else:
    server = '%s://%s:%s' % (server_scheme, server_host, server_port)

logger.info( 'server: %s' % server )

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

def passthrough(headers):
    EXCLUDE_HEADERS = [
        'content-length',  # per https://github.com/nickstenning/injecture/blob/master/proxy.go#L39
                           # // Remove the Content-Length header -- we've changed the length and Go's
	                       # // HTTP server will happily serve this as T-E: chunked.

        'connection',      # unsure about this

        'content-encoding' # because if we decoded gzipped content it isn't gzipped anymore
                           # unsure of full ramifications
    ]         

    for key in headers.keys():
        lowered_key = key.lower()
        if lowered_key in EXCLUDE_HEADERS:
            del headers[lowered_key]
    return headers

def join_fn(tag, url, match):
    joined_url = urljoin(url, match)
    return '%s="%s"' % (tag, joined_url)

def rewrite(content, url):
    pattern = '\\s*=\\s*["\']*(\.*/*[^#"\'\s]+)["\'\s]'
    content = re.sub('href' + pattern, lambda x: join_fn('href', url, x.group(1)), content, count=0, flags=re.IGNORECASE)
    content = re.sub('src' + pattern, lambda x: join_fn('src', url, x.group(1)), content, count=0, flags=re.IGNORECASE)
    return content

# The simplest possible replacement for via
@view_config( route_name='via' )
def via(request):
    qs = parse_qs(request.query_string)
    url = qs['url'][0]
    headers = request.headers
    r1 = requests.get(url)
    content = rewrite(r1.content, url)
    script = """<script async defer type="text/javascript" src="https://hypothes.is/embed.js"></script>""" 
    content = content.replace('</head>', script + '</head>')
    headers = passthrough(r1.headers)
    r2 = Response(body=content, headers=headers)
    return r2

# This variant includes the inlining seen in http://jonudell.net/h/via-lite-3.mp4
# I'd like it to connect to the H service but haven't worked that out yet, so this 
# connects to hyp.jonudell.info instead.
@view_config( route_name='via2' )
def via2(request):
    qs = parse_qs(request.query_string)
    url = qs['url'][0] 
    r1 = requests.get(url)
    content = rewrite(r1.content, url)
    script = """<script async defer type="text/javascript" src="https://hyp.jonudell.info/embed.js"></script>
<script class="js-hypothesis-config" type="application/json">
  { "assetRoot":"http://h.jonudell.info:3001/hypothesis/1.35.0/", 
    "sidebarAppUrl":"https://hyp.jonudell.info/app.html",
    "url_for_tags":"https://docs.google.com/document/d/1XZZEtmMSgSWDL6y5086SoYs0bkLvoO0qumLf-qVxrZU"
    }
</script> 
""" 
    content = content.replace('</head>', script + '</head>')
    headers = passthrough(r1.headers)
    r2 = Response(body=content, headers=headers)
    return r2

config = Configurator()

config.scan()

config.add_route('proxy', '/proxy')
config.add_route('via', '/via')
config.add_route('via2', '/via2')

app = config.make_wsgi_app()

if __name__ == '__main__': 

    server = make_server(server_host, server_port, app)
    server.serve_forever()
    
