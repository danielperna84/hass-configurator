#!/usr/bin/python3
"""
Proof of concept configurator for Home Assistant.
https://github.com/danielperna84/hass-poc-configurator
"""
import os
import sys
import json
import urllib.request
from string import Template
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

VERSION = "0.0.5"
BASEDIR = "."
# Set BASEPATH to something like "/home/hass/.homeasssitant" if you're not running the configurator from that path
BASEPATH = "."
LISTENIP = "0.0.0.0"
LISTENPORT = 3218
BOOTSTRAPAPI = "http://127.0.0.1:8123/api/bootstrap"

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
            response = urllib.request.urlopen(BOOTSTRAPAPI)
            boot = response.read().decode('utf-8')
        except Exception as err:
            print(err)
        
        html = html.safe_substitute(bootstrap=boot)
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
            #print(postvars)
            response = "Missing filename or text"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(bytes(response, "utf8"))
        return

def run():
    print('starting server...')
    server_address = (LISTENIP, LISTENPORT)
    httpd = HTTPServer(server_address, RequestHandler)
    print('running server...')
    if BASEPATH:
        os.chroot(BASEPATH)
        os.chdir('/')
    httpd.serve_forever()

run()
