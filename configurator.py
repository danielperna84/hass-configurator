#!/usr/bin/python3
import os
import sys
import json
import urllib.request
from string import Template
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

VERSION = "0.0.4"
BASEDIR = "."
LISTENIP = "0.0.0.0"
LISTENPORT = 3218
BOOTSTRAPAPI = "http://127.0.0.1:8123/api/bootstrap"
INDEX = Template("""<!DOCTYPE html>
<html>
    <head>
        <title>HASS-PoC-Configurator</title>
        <meta charset="UTF-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/1.12.1/jquery.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/simplemodal/1.4.4/jquery.simplemodal.min.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/jstree/3.2.1/themes/default/style.min.css" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jstree/3.2.1/jstree.min.js"></script>
        <style type="text/css" media="screen">
            body {
                margin: 0;
                padding: 0;
                font-family: monospace;
            }
            
            #menu {
                position:relative;
                width: 20%;
                float: left;
                font-size: 9pt;
                
            }
            
            #buttons {
                position: absolute;
                top: 0;
                right: 0;
            }
            
            #toolbar {
                position: relative;
                height: 20px;
            }

            #editor { 
                position: absolute;
                top: 20px;
                right: 0;
                bottom: 0;
                left: 20%;
            }
            
            #triggers {
                max-width: 100%;
            }
            
            #events {
                max-width: 100%;
            }
            
            #entities {
                max-width: 100%;
            }
            
            #conditions {
                max-width: 100%;
            }
            
            #services {
                max-width: 100%;
            }
        </style>
    </head>
    <body>
        <div id="menu">
            <div id="tree"></div><br />
            <label for="triggers">Trigger platforms:</label><br />
            <select id="triggers" onchange="editor.session.insert(editor.getCursorPosition(), this.value)">
                <option value="" disabled selected>...</option>
                <option value="event">Event</option>
                <option value="mqtt">MQTT</option>
                <option value="numeric_state">Numeric state</option>
                <option value="state">State</option>
                <option value="sun">Sun</option>
                <option value="template">Template</option>
                <option value="time">Time</option>
                <option value="zone">Zone</option>
            </select><br /><br />
            <label for="events">Events:</label><br />
            <select id="events" onchange="editor.session.insert(editor.getCursorPosition(), this.value)"></select><br /><br />
            <label for="entities">Entities:</label><br />
            <select id="entities" onchange="editor.session.insert(editor.getCursorPosition(), this.value)"></select><br /><br />
            <label for="conditions">Conditions:</label><br />
            <select id="conditions" onchange="editor.session.insert(editor.getCursorPosition(), this.value)">
                <option value="" disabled selected>...</option>
                <option value="numeric_state">Numeric state</option>
                <option value="state">State</option>
                <option value="sun">Sun</option>
                <option value="template">Template</option>
                <option value="time">Time</option>
                <option value="zone">Zone</option>
            </select><br /><br />
            <label for="services">Services:</label><br />
            <select id="services" onchange="editor.session.insert(editor.getCursorPosition(), this.value)"></select>
        </div>
        <div id="toolbar">
            <button id="savebutton" type="button" onclick="save()">Save</button>
            <button id="whitespace" type="button" onclick="toggle_whitespace()">Whitespace</button>
            <button id="fold" type="button" onclick="toggle_fold()">Fold</button>
            <button id="highlight" type="button" onclick="toggle_highlightSelectedWord()">Highlight selected words</button>
            <button id="help" type="button" onclick="window.open('https://home-assistant.io/getting-started/','_blank');">Help</button>
            <button id="components" type="button" onclick="window.open('https://home-assistant.io/components/','_blank');">Components</button>
        </div>
        <div id="editor"></div>
    </body>
    <script>
        var bootstrap = $bootstrap;
        if (bootstrap.hasOwnProperty("events")) {
            var events = document.getElementById("events");
            for (var i = 0; i < bootstrap.events.length; i++) {
                var option = document.createElement("option");
                option.value = bootstrap.events[i].event;
                option.text = bootstrap.events[i].event;
                events.add(option);
            }
            
            var entities = document.getElementById("entities");
            for (var i = 0; i < bootstrap.states.length; i++) {
                var option = document.createElement("option");
                option.value = bootstrap.states[i].entity_id;
                option.text = bootstrap.states[i].attributes.friendly_name + ' (' + bootstrap.states[i].entity_id + ')';
                entities.add(option);
            }
            
            var services = document.getElementById("services");
            for (var i = 0; i < bootstrap.services.length; i++) {
                for (var k in bootstrap.services[i].services) {
                    var option = document.createElement("option");
                    option.value = bootstrap.services[i].domain + '.' + k;
                    option.text = bootstrap.services[i].domain + '.' + k;
                    services.add(option);
                }
            }
            
            var options = $('#events option');
            var arr = options.map(function(_, o) { return { t: $(o).text(), v: o.value }; }).get();
            arr.sort(function(o1, o2) {
              var t1 = o1.t.toLowerCase(), t2 = o2.t.toLowerCase();
            
              return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
            });
            options.each(function(i, o) {
              o.value = arr[i].v;
              $(o).text(arr[i].t);
            });
            
            var options = $('#entities option');
            var arr = options.map(function(_, o) { return { t: $(o).text(), v: o.value }; }).get();
            arr.sort(function(o1, o2) {
              var t1 = o1.t.toLowerCase(), t2 = o2.t.toLowerCase();
            
              return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
            });
            options.each(function(i, o) {
              o.value = arr[i].v;
              $(o).text(arr[i].t);
            });
            
            var options = $('#services option');
            var arr = options.map(function(_, o) { return { t: $(o).text(), v: o.value }; }).get();
            arr.sort(function(o1, o2) {
              var t1 = o1.t.toLowerCase(), t2 = o2.t.toLowerCase();
            
              return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
            });
            options.each(function(i, o) {
              o.value = arr[i].v;
              $(o).text(arr[i].t);
            });
        }
        
        $('#tree').jstree(
        {
          'core' : {
            'data' : {
              'url' : '/api/files'
            }
          }
        });
        $('#tree').on("select_node.jstree", function (e, data) { load(); });
        
        var whitespacestatus = false;
        var foldstatus = true;
        var highlightwords = true;
        var modaloptions = {close: true, overlayClose: true, containerCss: {border: "1px solid #000", padding: "5px", background: "#fff"}};
        
        function toggle_highlightSelectedWord() {
            highlightwords = !highlightwords;
            editor.setOption("highlightSelectedWord", highlightwords);
        }
        
        function toggle_whitespace() {
            whitespacestatus = !whitespacestatus;
            editor.setOption("showInvisibles", whitespacestatus);
        }
        
        function toggle_fold() {
            if (foldstatus) {
                editor.getSession().foldAll();
            }
            else {
                editor.getSession().unfold();
            }
            foldstatus = !foldstatus;
        }
        
        function load() {
            var n = $("#tree").jstree("get_selected");
            if (n) {
                $.get("api/file?filename=" + n[0], function( data ) {
                  editor.setValue(data);
                });
            }
        }
        
        function save() {
            var n = $("#tree").jstree("get_selected");
            if (n) {
                data = new Object();
                data.filename = n[0];
                data.text = editor.getValue()
                $.post("api/save", data).done(
                    function( resp ) {
                    $.modal("<div><pre>" + resp + "</pre></div>", modaloptions);
                  }
                );
            }
        }
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ace.js" type="text/javascript" charset="utf-8"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ext-modelist.js" type="text/javascript" charset="utf-8"></script>
    <script>
        var editor = ace.edit("editor");
        editor.getSession().setMode("ace/mode/yaml");
        editor.setOption("showInvisibles", whitespacestatus);
        editor.setOption("useSoftTabs", true);
        editor.setOption("displayIndentGuides", true);
        editor.setOption("highlightSelectedWord", highlightwords);
        editor.$blockScrolling = Infinity;
    </script>
</html>
""")

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
        
        boot = "{}"
        try:
            response = urllib.request.urlopen(BOOTSTRAPAPI)
            boot = response.read().decode('utf-8')
        except Exception as err:
            print(err)
        
        html = INDEX.safe_substitute(bootstrap=boot)
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
    httpd.serve_forever()

run()
