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
import base64
import ipaddress
import signal
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
# Limit access to the configurator by adding allowed IP addresses / networks to the list,
# e.g ALLOWED_NETWORKS = ["192.168.0.0/24", "172.16.47.23"]
ALLOWED_NETWORKS = []
# List of statically banned IP addresses, e.g. ["1.1.1.1", "2.2.2.2"]
BANNED_IPS = []
# Ban IPs after n failed login attempts. Restart service to reset banning. The default of `0` disables this feature.
BANLIMIT = 0
# File extensions the file browser should include
EXTENSIONS = ['yaml', 'conf']
# Directories to exclude from the file browser
EXCLUDE_DIRS = ['/deps', '/.git']
### End of options

RELEASEURL = "https://api.github.com/repos/danielperna84/hass-poc-configurator/releases/latest"
VERSION = "0.0.8"
BASEDIR = "."
DEV = False
HTTPD = None
FAIL2BAN_IPS = {}
INDEX = Template("""<!DOCTYPE html>
<html>

<head>
    <!--  Android Chrome Color-->
    <meta name="theme-color" content="#EE6E73">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1.0" />
    <title>Configurator</title>
    <!-- CSS  -->
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.98.0/css/materialize.min.css" type="text/css" rel="stylesheet" media="screen,projection" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/1.12.1/jquery.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/jstree/3.3.3/themes/default/style.min.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jstree/3.3.3/jstree.min.js"></script>
    <style type="text/css" media="screen">
        body {
            margin: 0;
            padding: 0;
        }
        
        #editor {
            position: fixed;
            top: 68px;
            right: 0;
            bottom: 0;
        }
        
        .green {
            color: #0f0;
        }
        
        .red {
            color: #f00;
        }
        
        .dropdown-content {
            min-width: 200px;
        }
    </style>
</head>

<body>
    <div class="navbar-fixed">
        <nav class="light-blue hoverable">
            <div class="nav-wrapper">
                <ul class="left">
                    <li><a href="#" data-activates="slide-out" class="waves-effect waves-light button-collapse show-on-large"><i class="material-icons">folder</i></a></li>
                </ul>
                <ul class="right">
                    <li><a class="waves-effect waves-light" href="#modal_save"><i class="material-icons">save</i></a></li>
                    <li><a class="waves-effect waves-light dropdown-button" href="#!" data-activates="dropdown_tools" data-beloworigin="true"><i class="material-icons right">more_vert</i></a></li>
                </ul>
            </div>
        </nav>
    </div>
    <ul id="dropdown_tools" class="dropdown-content z-depth-4">
        <li><a onclick="toggle_whitespace()">Whitespace</a></li>
        <li><a onclick="toggle_fold()">Fold</a></li>
        <li><a onclick="toggle_highlightSelectedWord()">Highlight</a></li>
        <li><a target="_blank" href="https://github.com/ajaxorg/ace/wiki/Default-Keyboard-Shortcuts">Ace Keyboard Shortcuts</a></li>
        <li><a target="_blank" href="https://home-assistant.io/help/">Need HASS Help?</a></li>
        <li><a target="_blank" href="https://home-assistant.io/components/">HASS Components</a></li>
        <li><a href="#modal_about">About</a></li>
        <li class="divider"></li>
        <li><a href="#" data-activates="ace_settings" class="ace_settings-collapse">Settings</a></li>
        <li><a href="#modal_restart">Restart HASS</a></li>
    </ul>
    <div id="modal_save" class="modal">
        <div class="modal-content">
            <h4>Save</h4>
            <p>Do you really want to save?</p>
        </div>
        <div class="modal-footer"> <a href="#!" class=" modal-action modal-close waves-effect waves-red btn-flat">No</a> <a onclick="save()" class=" modal-action modal-close waves-effect waves-green btn-flat">Yes</a> </div>
    </div>
    <div id="modal_restart" class="modal">
        <div class="modal-content">
            <h4>Restart</h4>
            <p>Do you really want to restart HASS?</p>
        </div>
        <div class="modal-footer"> <a href="#!" class=" modal-action modal-close waves-effect waves-red btn-flat">No</a> <a onclick="restart()" class=" modal-action modal-close waves-effect waves-green btn-flat">Yes</a> </div>
    </div>
    <div id="modal_about" class="modal">
        <div class="modal-content">
            <h4>About</h4>
            <p>Version: <a class="$versionclass" href="https://github.com/danielperna84/hass-poc-configurator/releases/latest" target="_blank">$current</a></p>
        </div>
        <div class="modal-footer"> <a class=" modal-action modal-close waves-effect btn-flat">OK</a> </div>
    </div>
    <div class="row">
        <div class="col m4 l3 hide-on-small-only">
            </br>
            <div class="input-field col s12">
                <select onchange="insert(this.value)">
                    <option value="" disabled selected>Choose your option</option>
                    <option value="event">Event</option>
                    <option value="mqtt">MQTT</option>
                    <option value="numberic_state">Numeric State</option>
                    <option value="state">State</option>
                    <option value="sun">Sun</option>
                    <option value="template">Template</option>
                    <option value="time">Time</option>
                    <option value="zone">Zone</option>
                </select>
                <label>Trigger Platform</label>
            </div>
            <div class="input-field col s12">
                <select id="events" onchange="insert(this.value)"> </select>
                <label>Events</label>
            </div>
            <div class="input-field col s12">
                <select id="entities" onchange="insert(this.value)"> </select>
                <label>Entities</label>
            </div>
            <div class="input-field col s12">
                <select onchange="insert(this.value)">
                    <option value="" disabled selected>Choose your option</option>
                    <option value="numeric_state">Numeric state</option>
                    <option value="state">State</option>
                    <option value="sun">Sun</option>
                    <option value="template">Template</option>
                    <option value="time">Time</option>
                    <option value="zone">Zone</option>
                </select>
                <label>Conditions</label>
            </div>
            <div class="input-field col s12">
                <select id="services" onchange="insert(this.value)"> </select>
                <label>Services</label>
            </div>
        </div>
        <div class="col s12 m8 l9 z-depth-3 hoverable" id="editor"></div>
    </div>
    <div>
        <ul id="slide-out" class="side-nav">
            <li> <a class="subheader">Home Assistant Directory</a> </li>
            <li>
                <div id="tree"></div>
            </li>
            <li>
                <a class="subheader"></a>
            </li>
            <div class="row">
                <div class="hide-on-med-and-up">
                    <div class="input-field col s12">
                        <select onchange="insert(this.value)">
                            <option value="" disabled selected>Choose your option</option>
                            <option value="event">Event</option>
                            <option value="mqtt">MQTT</option>
                            <option value="numberic_state">Numeric State</option>
                            <option value="state">State</option>
                            <option value="sun">Sun</option>
                            <option value="template">Template</option>
                            <option value="time">Time</option>
                            <option value="zone">Zone</option>
                        </select>
                        <label>Trigger Platform</label>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="hide-on-med-and-up">
                    <div class="input-field col s12">
                        <select id="events_side" onchange="insert(this.value)"> </select>
                        <label>Events</label>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="hide-on-med-and-up">
                    <div class="input-field col s12">
                        <select id="entities_side" onchange="insert(this.value)"> </select>
                        <label>Entities</label>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="hide-on-med-and-up">
                    <div class="input-field col s12">
                        <select onchange="insert(this.value)">
                            <option value="" disabled selected>Choose your option</option>
                            <option value="numeric_state">Numeric state</option>
                            <option value="state">State</option>
                            <option value="sun">Sun</option>
                            <option value="template">Template</option>
                            <option value="time">Time</option>
                            <option value="zone">Zone</option>
                        </select>
                        <label>Conditions</label>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="hide-on-med-and-up">
                    <div class="input-field col s12">
                        <select id="services_side" onchange="insert(this.value)"> </select>
                        <label>Services</label>
                    </div>
                </div>
            </div>
            </br>
            </br>
            </br>
        </ul>
    </div>
    <div class="row center">
        <ul id="ace_settings" class="side-nav">
            <li><a onclick="Materialize.toast('¯\\_(ツ)_/¯', 2000)">Coming Soon . . .</a></li>
            <form class="row center col s12" action="#">
                <p>
                    <input type="checkbox" id="test1" />
                    <label for="test1">Animated Scroll</label>
                </p>
                <p>
                    <input type="checkbox" id="test2" />
                    <label for="test2">Behaviours Enabled</label>
                </p>
                <p>
                    <input type="checkbox" id="test3" />
                    <label for="test3">Display Indent Guides</label>
                </p>
            </form>
            <div class="row">
                <div class="input-field col s6">
                    <input value="150" id="drag_delay" type="text" class="validate">
                    <label class="active" for="drag_delay">Drag Delay</label>
                </div>
            </div>
            <form class="col s12" action="#">
                <p>
                    <input type="checkbox" id="test4" />
                    <label for="test4">Fade Fold Widgets</label>
                </p>
            </form>
        </ul>
    </div>
</body>
<!--  Scripts-->
<script src="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.98.0/js/materialize.min.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
        $('select').material_select();
        $('.modal').modal();
        $('.dropdown-button').dropdown({
            inDuration: 300,
            outDuration: 225,
            constrainWidth: true,
            hover: false,
            gutter: 0,
            belowOrigin: true,
            alignment: 'right',
            stopPropagation: false
        });
        $('.button-collapse').sideNav({
            menuWidth: 350,
            edge: 'left',
            closeOnClick: true,
            draggable: true
        });
        $('.ace_settings-collapse').sideNav({
            menuWidth: 400, // Default is 300
            edge: 'right', // Choose the horizontal origin
            closeOnClick: true, // Closes side-nav on <a> clicks, useful for Angular/Meteor
            draggable: true // Choose whether you can drag to open on touch screens
        });
    });
</script>
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
        var events = document.getElementById("events_side");
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
        var entities = document.getElementById("entities_side");
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
        var services = document.getElementById("services_side");
        for (var i = 0; i < bootstrap.services.length; i++) {
            for (var k in bootstrap.services[i].services) {
                var option = document.createElement("option");
                option.value = bootstrap.services[i].domain + '.' + k;
                option.text = bootstrap.services[i].domain + '.' + k;
                services.add(option);
            }
        }
        var options = $('#events option');
        var arr = options.map(function(_, o) {
            return {
                t: $(o).text(),
                v: o.value
            };
        }).get();
        arr.sort(function(o1, o2) {
            var t1 = o1.t.toLowerCase(),
                t2 = o2.t.toLowerCase();
            return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
        });
        options.each(function(i, o) {
            o.value = arr[i].v;
            $(o).text(arr[i].t);
        });
        var options = $('#entities option');
        var arr = options.map(function(_, o) {
            return {
                t: $(o).text(),
                v: o.value
            };
        }).get();
        arr.sort(function(o1, o2) {
            var t1 = o1.t.toLowerCase(),
                t2 = o2.t.toLowerCase();
            return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
        });
        options.each(function(i, o) {
            o.value = arr[i].v;
            $(o).text(arr[i].t);
        });
        var options = $('#services option');
        var arr = options.map(function(_, o) {
            return {
                t: $(o).text(),
                v: o.value
            };
        }).get();
        arr.sort(function(o1, o2) {
            var t1 = o1.t.toLowerCase(),
                t2 = o2.t.toLowerCase();
            return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
        });
        options.each(function(i, o) {
            o.value = arr[i].v;
            $(o).text(arr[i].t);
        });
    }
    $('#tree').jstree({
        'core': {
            'data': {
                'url': '/api/files'
            }
        }
    });
    $('#tree').on("select_node.jstree", function(e, data) {
        load();
    });
    var whitespacestatus = false;
    var foldstatus = true;
    var highlightwords = true;

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
        } else {
            editor.getSession().unfold();
        }
        foldstatus = !foldstatus;
    }

    function load() {
        var n = $("#tree").jstree("get_selected");
        if (n) {
            $.get("api/file?filename=" + n[0], function(data) {
                editor.setValue(data);
                editor.selection.selectFileStart();
                editor.focus();
            });
        }
    }

    function restart() {
        $.get("api/restart", function(resp) {
            if (resp.length == 0) {
                var $toastContent = $("<div><pre>Restarting HASS</pre></div>");
                Materialize.toast($toastContent, 2000);
            } else {
                var $toastContent = $("<div><pre>" + resp + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
        });
    }

    function save() {
        var n = $("#tree").jstree("get_selected");
        if (n) {
            data = new Object();
            data.filename = n[0];
            data.text = editor.getValue()
            $.post("api/save", data).done(function(resp) {
                var $toastContent = $("<div><pre>" + resp + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            });
        }
    }
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ace.js" type="text/javascript" charset="utf-8"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ext-modelist.js" type="text/javascript" charset="utf-8"></script>
<script>
    var editor = ace.edit("editor");
    if (localStorage.hasOwnProperty("pochass")) {
        editor.setOptions(JSON.parse(localStorage.pochass));
    } else {
        editor.getSession().setMode("ace/mode/yaml");
        editor.setOption("showInvisibles", whitespacestatus);
        editor.setOption("useSoftTabs", true);
        editor.setOption("displayIndentGuides", true);
        editor.setOption("highlightSelectedWord", highlightwords);
        editor.$blockScrolling = Infinity;
    }

    function insert(text) {
        var pos = editor.selection.getCursor();
        var end = editor.session.insert(pos, text);
        editor.selection.setRange({
            start: pos,
            end: end
        });
        editor.focus();
    }
</script>

</html>
""")

def signal_handler(signal, frame):
    global HTTPD
    print("Shutting down server")
    HTTPD.server_close()
    sys.exit(0)

def load_settings(settingsfile):
    global LISTENIP, LISTENPORT, BASEPATH, SSL_CERTIFICATE, SSL_KEY, HASS_API, \
    HASS_API_PASSWORD, CREDENTIALS, ALLOWED_NETWORKS, BANNED_IPS, BANLIMIT, \
    EXTENSIONS, EXCLUDE_DIRS
    try:
        if os.path.isfile(settingsfile):
            with open(settingsfile) as fptr:
                settings = json.loads(fptr.read())
                LISTENIP = settings.get("LISTENIP", LISTENIP)
                LISTENPORT = settings.get("LISTENPORT", LISTENPORT)
                BASEPATH = settings.get("BASEPATH", BASEPATH)
                SSL_CERTIFICATE = settings.get("SSL_CERTIFICATE", SSL_CERTIFICATE)
                SSL_KEY = settings.get("SSL_KEY", SSL_KEY)
                HASS_API = settings.get("HASS_API", HASS_API)
                HASS_API_PASSWORD = settings.get("HASS_API_PASSWORD", HASS_API_PASSWORD)
                CREDENTIALS = settings.get("CREDENTIALS", CREDENTIALS)
                ALLOWED_NETWORKS = settings.get("ALLOWED_NETWORKS", ALLOWED_NETWORKS)
                BANNED_IPS = settings.get("BANNED_IPS", BANNED_IPS)
                BANLIMIT = settings.get("BANLIMIT", BANLIMIT)
                EXTENSIONS = settings.get("EXTENSIONS", EXTENSIONS)
                EXCLUDE_DIRS = settings.get("EXCLUDE_DIRS", EXCLUDE_DIRS)
    except Exception as err:
        print(err)
        print("Not loading static settings")
    return False

def get_html():
    if DEV:
        try:
            with open("dev.html") as fptr:
                html = Template(fptr.read())
                return html
        except Exception as err:
            print(err)
            print("Delivering embedded HTML")
    return INDEX

def check_access(clientip):
    global BANNED_IPS
    if clientip in BANNED_IPS:
        return False
    if not ALLOWED_NETWORKS:
        return True
    for net in ALLOWED_NETWORKS:
        ipobject = ipaddress.ip_address(clientip)
        if ipobject in ipaddress.ip_network(net):
            return True
    BANNED_IPS.append(clientip)
    return False

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
            if os.path.isfile(os.path.join(parent, node_name)) and node_name.split('.')[-1] not in EXTENSIONS:
                continue
        else:
            parent = "#"
        
        nodes.append(Node(node_id, node_name, parent))
    return nodes

def getdirs(searchpath):
    unique_nodes = []
    for root, dirs, files in os.walk(searchpath, topdown=True):
        if [d for d in EXCLUDE_DIRS if d in root]:
            continue
        for name in files:
            path = os.path.join(root, name)
            nodes = get_nodes_from_path(path)
            for node in nodes:
                if not any(node.is_equal(unode) for unode in unique_nodes):
                    unique_nodes.append(node)
    return [node.as_json() for node in unique_nodes]

class RequestHandler(BaseHTTPRequestHandler):
    def do_BLOCK(self):
        self.send_response(420)
        self.end_headers()
        self.wfile.write(bytes("Policy not fulfilled", "utf8"))

    def do_GET(self):
        if not check_access(self.client_address[0]):
            self.do_BLOCK()
            return
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
        elif req.path == '/api/restart':
            print("/api/restart")
            self.send_header('Content-type','text/json')
            self.end_headers()
            r = {"restart": False}
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                if HASS_API_PASSWORD:
                    headers["x-ha-access"] = HASS_API_PASSWORD
                req = urllib.request.Request("%sservices/homeassistant/restart" % HASS_API, headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    r = json.loads(response.read().decode('utf-8'))
                    print(r)
            except Exception as err:
                print(err)
                r['restart'] = str(err)
            self.wfile.write(bytes(json.dumps(r), "utf8"))
            return
        elif req.path == '/':
            self.send_header('Content-type','text/html')
            self.end_headers()
            
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
                print("Exception getting bootstrap")
                print(err)
    
            color = "green"
            try:
                response = urllib.request.urlopen(RELEASEURL)
                latest = json.loads(response.read().decode('utf-8'))['tag_name']
                if VERSION != latest:
                    color = "red"
            except Exception as err:
                print("Exception getting release")
                print(err)
            html = get_html().safe_substitute(bootstrap=boot, current=VERSION, versionclass=color)
            self.wfile.write(bytes(html, "utf8"))
            return
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(bytes("File not found", "utf8"))

    def do_POST(self):
        if not check_access(self.client_address[0]):
            self.do_BLOCK()
            return
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
            if BANLIMIT:
                FAIL2BAN_IPS.pop(self.client_address[0], None)
            super().do_GET()
            pass
        else:
            if BANLIMIT:
                bancounter = FAIL2BAN_IPS.get(self.client_address[0], 1)
                if bancounter >= BANLIMIT:
                    print("Blocking access from %s" % self.client_address[0])
                    self.do_BLOCK()
                    return
                else:
                    FAIL2BAN_IPS[self.client_address[0]] = bancounter + 1
            self.do_AUTHHEAD()
            self.wfile.write(bytes('Authentication required', 'utf-8'))
            pass

    def do_POST(self):
        global CREDENTIALS
        authorization = self.headers.get('Authorization', None)
        if authorization == None:
            self.do_AUTHHEAD()
            self.wfile.write(bytes('no auth header received', 'utf-8'))
            pass
        elif authorization == 'Basic %s' % CREDENTIALS.decode('utf-8'):
            if BANLIMIT:
                FAIL2BAN_IPS.pop(self.client_address[0], None)
            super().do_POST()
            pass
        else:
            if BANLIMIT:
                bancounter = FAIL2BAN_IPS.get(self.client_address[0], 1)
                if bancounter >= BANLIMIT:
                    print("Blocking access from %s" % self.client_address[0])
                    self.do_BLOCK()
                    return
                else:
                    FAIL2BAN_IPS[self.client_address[0]] = bancounter + 1
            self.do_AUTHHEAD()
            self.wfile.write(bytes('Authentication required', 'utf-8'))
            pass

def main(args):
    global HTTPD, CREDENTIALS
    if args:
        load_settings(args[0])
    print("Starting server")
    server_address = (LISTENIP, LISTENPORT)
    if CREDENTIALS:
        CREDENTIALS = base64.b64encode(bytes(CREDENTIALS, "utf-8"))
        Handler = AuthHandler
    else:
        Handler = RequestHandler
    if not SSL_CERTIFICATE:
        HTTPD = HTTPServer(server_address, Handler)
    else:
        HTTPD = socketserver.TCPServer(server_address, Handler)
        HTTPD.socket = ssl.wrap_socket(HTTPD.socket, certfile=SSL_CERTIFICATE, keyfile=SSL_KEY, server_side=True)
    print('Listening on: %s://%s:%i' % ('https' if SSL_CERTIFICATE else 'http', LISTENIP, LISTENPORT))
    if BASEPATH:
        os.chdir(BASEPATH)
    HTTPD.serve_forever()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main(sys.argv[1:])
