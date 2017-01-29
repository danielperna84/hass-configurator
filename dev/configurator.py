#!/usr/bin/python3
"""
Proof of concept configurator for Home Assistant.
https://github.com/danielperna84/hass-poc-configurator
"""
import os
import sys
import json
import ssl
import socketserver
import urllib.request
from string import Template
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

### Some options for you to change
LISTENIP = "0.0.0.0"
LISTENPORT = 3218
# Set BASEPATH to something like "/home/hass/.homeasssitant" if you're not running the configurator from that path
BASEPATH = None
# Set the paths to a certificate and the key if you're using SSL, e.g "/etc/ssl/certs/mycert.pem"
SSL_CERTIFICATE = None
SSL_KEY = None
# Set the destination where the HASS API is reachable
HASS_API = "http://127.0.0.1:8123/api/"
# If a password is required to access the API, set it in the form of "password"
HASS_API_PASSWORD = None
# To enable authentication, set the credentials in the form of "username:password"
CREDENTIALS = None
### End of options

RELEASEURL = "https://api.github.com/repos/danielperna84/hass-poc-configurator/releases/latest"
VERSION = "0.0.6"
BASEDIR = "."

class Node:
    def __init__(self, id, text, parent):
        self.id = id
        self.text = text
        self.parent = parent
        self.icon = 'jstree-folder'
        self.state = {'opened': self.id == '.'}
        if os.path.isfile(os.path.join(parent, text)):
            self.icon = "jstree-file"
 
    def is_equal(self, node):
        return self.id == node.id
 
    def as_json(self):
        return dict(
            id=self.id,
            parent=self.parent,
            text=self.text,
            icon=self.icon,
            state=self.state
        )
 
 
def get_nodes_from_path(path):
    nodes = []
    path_nodes = path.split(os.sep)
    for idx, node_name in enumerate(path_nodes):
        parent = None
        node_id = os.sep.join(path_nodes[0:idx+1])
        if idx != 0:
            parent = os.sep.join(path_nodes[0:idx])
            if os.path.isfile(os.path.join(parent, node_name)) and (not node_name.endswith('.yaml') and not node_name.endswith('.conf')):
                continue
        else:
            parent = "#"
        
        nodes.append(Node(node_id, node_name, parent))
    return nodes
 
 
def getdirs(searchpath):
    unique_nodes = []
    for root, dirs, files in os.walk(searchpath, topdown=True):
        if './deps' not in root and './.git' not in root and './www' not in root:
            for name in files:
                path = os.path.join(root, name)
                nodes = get_nodes_from_path(path)
                for node in nodes:
                    if not any(node.is_equal(unode) for unode in unique_nodes):
                        unique_nodes.append(node)
    return [node.as_json() for node in unique_nodes]

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        req = urlparse(self.path)
        query = parse_qs(req.query)
        self.send_response(200)
        if req.path == '/api/files':
            self.send_header('Content-type','text/json')
            self.end_headers()
            dirs = sorted(getdirs(BASEDIR), key=lambda x: x["text"])
            self.wfile.write(bytes(json.dumps(dirs), "utf8"))
            return
        elif req.path == '/api/file':
            content = ""
            self.send_header('Content-type','text/text')
            self.end_headers()
            filename = query.get('filename', None)
            if filename:
                if os.path.isfile(os.path.join(BASEDIR, filename[0])):
                    with open(os.path.join(BASEDIR, filename[0])) as fptr:
                        content += fptr.read()
            self.wfile.write(bytes(content, "utf8"))
            return

        self.send_header('Content-type','text/html')
        self.end_headers()
        html = ""
        with open("index.html") as fptr:
            html = Template(fptr.read())
        boot = "{}"
        try:
            headers = {
                "Content-Type": "application/json"
            }
            if HASS_API_PASSWORD:
                headers["x-ha-access"] = HASS_API_PASSWORD
            req = urllib.request.Request("%sbootstrap" % HASS_API, headers=headers, method='GET')
            with urllib.request.urlopen(req) as response:
                boot = response.read().decode('utf-8')
            
        except Exception as err:
            print(err)
        
        color = "green"
        try:
            response = urllib.request.urlopen(RELEASEURL)
            latest = json.loads(response.read().decode('utf-8'))['tag_name']
            if VERSION != latest:
                color = "red"
        except Exception as err:
            print(err)
        html = INDEX.safe_substitute(bootstrap=boot, current=VERSION, versionclass=color)
        self.wfile.write(bytes(html, "utf8"))
        return

    def do_POST(self):
        postvars = {}
        response = "Failure"
        try:
            length = int(self.headers['content-length'])
            postvars = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=1)
        except Exception as err:
            print(err)
            response = "%s" % (str(err))

        if 'filename' in postvars.keys() and 'text' in postvars.keys():
            if postvars['filename'] and postvars['text']:
                try:
                    filename = postvars['filename'][0]
                    with open(os.path.join(BASEDIR, filename), 'wb') as fptr:
                        fptr.write(bytes(postvars['text'][0], "utf-8"))
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(bytes("File saved successfully", "utf8"))
                    return
                except Exception as err:
                    response = "%s" % (str(err))
                    print(err)
        else:
            response = "Missing filename or text"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(bytes(response, "utf8"))
        return

class AuthHandler(RequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_AUTHHEAD(self):
        print("Requesting authorization")
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"HASS-PoC-Configurator\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        global CREDENTIALS
        authorization = self.headers.get('Authorization', None)
        if authorization == None:
            self.do_AUTHHEAD()
            self.wfile.write(bytes('no auth header received', 'utf-8'))
            pass
        elif authorization == 'Basic %s' % CREDENTIALS.decode('utf-8'):
            super().do_GET()
            pass
        else:
            self.do_AUTHHEAD()
            self.wfile.write(bytes('not authenticated', 'utf-8'))
            pass
    
    def do_POST(self):
        global CREDENTIALS
        authorization = self.headers.get('Authorization', None)
        if authorization == None:
            self.do_AUTHHEAD()
            self.wfile.write(bytes('no auth header received', 'utf-8'))
            pass
        elif authorization == 'Basic %s' % CREDENTIALS.decode('utf-8'):
            super().do_POST()
            pass
        else:
            self.do_AUTHHEAD()
            self.wfile.write(bytes('not authenticated', 'utf-8'))
            pass

def run():
    global CREDENTIALS
    print('Starting server')
    server_address = (LISTENIP, LISTENPORT)
    if CREDENTIALS:
        CREDENTIALS = base64.b64encode(bytes(CREDENTIALS, "utf-8"))
        Handler = AuthHandler
    else:
        Handler = RequestHandler
    if not SSL_CERTIFICATE:
        httpd = HTTPServer(server_address, Handler)
    else:
        httpd = socketserver.TCPServer(server_address, RequestHandler)
        httpd.socket = ssl.wrap_socket(httpd.socket, certfile=SSL_CERTIFICATE, keyfile=SSL_KEY, server_side=True)
    print('Listening on: %s://%s:%i' % ('https' if SSL_CERTIFICATE else 'http', LISTENIP, LISTENPORT))
    if BASEPATH:
        os.chroot(BASEPATH)
        os.chdir('/')
    httpd.serve_forever()

run()
