#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""
Configurator for Home Assistant.
https://github.com/danielperna84/hass-configurator
"""
import os
import sys
import argparse
import json
import ssl
import socket
import socketserver
import base64
import ipaddress
import signal
import cgi
import shlex
import subprocess
import logging
import fnmatch
import hashlib
import mimetypes
from string import Template
from http.server import BaseHTTPRequestHandler
import urllib.request
from urllib.parse import urlparse, parse_qs, unquote

### Some options for you to change
LISTENIP = "0.0.0.0"
PORT = 3218
# Set BASEPATH to something like "/home/hass/.homeassistant/" if you're not
# running the configurator from that path
BASEPATH = None
# Set ENFORCE_BASEPATH to True to lock the configurator into the basepath and
# thereby prevent it from opening files outside of the BASEPATH
ENFORCE_BASEPATH = False
# Set the paths to a certificate and the key if you're using SSL,
# e.g "/etc/ssl/certs/mycert.pem"
SSL_CERTIFICATE = None
SSL_KEY = None
# Set the destination where the HASS API is reachable
HASS_API = "http://127.0.0.1:8123/api/"
# Set the destination where the websocket API is reachable (if different
# from HASS_API, e.g. wss://hass.example.com/api/websocket)
HASS_WS_API = None
# If a password is required to access the API, set it in the form of "password"
# if you have HA ignoring SSL locally this is not needed if on same machine.
HASS_API_PASSWORD = None
# Using the CREDENTIALS variable is deprecated.
# It will still work though if USERNAME and PASSWORD are not set.
CREDENTIALS = None
# Set the username used for basic authentication.
USERNAME = None
# Set the password used for basic authentication.
PASSWORD = None
# Limit access to the configurator by adding allowed IP addresses / networks to
# the list, e.g ALLOWED_NETWORKS = ["192.168.0.0/24", "172.16.47.23"]
ALLOWED_NETWORKS = []
# Allow access to the configurator to client IP addesses which match the result
# of DNS lookups for the specified domains.
ALLOWED_DOMAINS = []
# List of statically banned IP addresses, e.g. ["1.1.1.1", "2.2.2.2"]
BANNED_IPS = []
# Ban IPs after n failed login attempts. Restart service to reset banning.
# The default of `0` disables this feature.
BANLIMIT = 0
# Enable git integration.
# GitPython (https://gitpython.readthedocs.io/en/stable/) has to be installed.
GIT = False
# Files to ignore in the UI.  A good example list that cleans up the UI is
# [".*", "*.log", "deps", "icloud", "*.conf", "*.json", "certs", "__pycache__"]
IGNORE_PATTERN = []
# if DIRSFIRST is set to `true`, directories will be displayed at the top
DIRSFIRST = False
# Sesame token. Browse to the configurator URL + /secrettoken to unban your
# client IP and add it to the list of allowed IPs.
HIDEHIDDEN = False
# Don't display hidden files (starting with .)
SESAME = None
# Instead of a static SESAME token you may also use a TOTP based token that
# changes every 30 seconds. The value needs to be a base 32 encoded string.
SESAME_TOTP_SECRET = None
# Verify the hostname used in the request. Block access if it doesn't match
# this value
VERIFY_HOSTNAME = None
# Prefix for environment variables
ENV_PREFIX = "HC_"
# Ignore SSL errors when connecting to the HASS API
IGNORE_SSL = False
# Notification service like `notify.mytelegram`. Default is `persistent_notification.create`
NOTIFY_SERVICE_DEFAULT = "persistent_notification.create"
NOTIFY_SERVICE = NOTIFY_SERVICE_DEFAULT
### End of options

LOGLEVEL_MAPPING = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG
}
DEFAULT_LOGLEVEL = "info"
LOGLEVEL = LOGLEVEL_MAPPING.get(os.environ.get("HC_LOGLEVEL", DEFAULT_LOGLEVEL))
LOG = logging.getLogger(__name__)
LOG.setLevel(LOGLEVEL)
SO = logging.StreamHandler(sys.stdout)
SO.setLevel(LOGLEVEL)
SO.setFormatter(
    logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s'))
LOG.addHandler(SO)
RELEASEURL = "https://api.github.com/repos/danielperna84/hass-configurator/releases/latest"
VERSION = "0.3.7"
BASEDIR = "."
DEV = False
LISTENPORT = None
TOTP = None
HTTPD = None
FAIL2BAN_IPS = {}
REPO = None

ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1.0" />
    <title>HASS Configurator - Error</title>
</head>
<body>
<h1>Error loading html. Please check the logs.</h1>
</body>
</html>"""

# pylint: disable=unused-argument
def signal_handler(sig, frame):
    """Handle signal to shut down server."""
    global HTTPD
    LOG.info("Got signal: %s. Shutting down server", str(sig))
    HTTPD.server_close()
    sys.exit(0)

def load_settings(args):
    """Load settings from file and environment."""
    global LISTENIP, LISTENPORT, BASEPATH, SSL_CERTIFICATE, SSL_KEY, HASS_API, \
    HASS_API_PASSWORD, CREDENTIALS, ALLOWED_NETWORKS, BANNED_IPS, BANLIMIT, \
    DEV, IGNORE_PATTERN, DIRSFIRST, SESAME, VERIFY_HOSTNAME, ENFORCE_BASEPATH, \
    ENV_PREFIX, NOTIFY_SERVICE, USERNAME, PASSWORD, SESAME_TOTP_SECRET, TOTP, \
    GIT, REPO, PORT, IGNORE_SSL, HASS_WS_API, ALLOWED_DOMAINS, HIDEHIDDEN
    settings = {}
    settingsfile = args.settings
    if settingsfile:
        try:
            if os.path.isfile(settingsfile):
                settings = json.loads(load_file(settingsfile).decode("utf-8"))
                LOG.debug("Settings from file:")
                LOG.debug(settings)
            else:
                LOG.warning("File not found: %s", settingsfile)
        except Exception as err:
            LOG.warning(err)
            LOG.warning("Not loading settings from file")
    ENV_PREFIX = settings.get('ENV_PREFIX', ENV_PREFIX)
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            # Convert booleans
            if value in ['true', 'false', 'True', 'False']:
                value = value in ['true', 'True']
            # Convert None / null
            elif value in ['none', 'None', 'null']:
                value = None
            # Convert plain numbers
            elif value.isnumeric():
                value = int(value)
            # Make lists out of comma separated values for list-settings
            elif key[len(ENV_PREFIX):] in ["ALLOWED_NETWORKS", "BANNED_IPS", "IGNORE_PATTERN"]:
                value = value.split(',')
            settings[key[len(ENV_PREFIX):]] = value
    LOG.debug("Settings after looking at environment:")
    LOG.debug(settings)
    if args.git:
        GIT = args.git
    else:
        GIT = settings.get("GIT", GIT)
    if GIT:
        try:
            # pylint: disable=redefined-outer-name,import-outside-toplevel
            from git import Repo as REPO
        except ImportError:
            LOG.warning("Unable to import Git module")
    if args.listen:
        LISTENIP = args.listen
    else:
        LISTENIP = settings.get("LISTENIP", LISTENIP)
    if args.port is not None:
        PORT = args.port
    else:
        LISTENPORT = settings.get("LISTENPORT", None)
    PORT = settings.get("PORT", PORT)
    if LISTENPORT is not None:
        PORT = LISTENPORT
    if args.basepath:
        BASEPATH = args.basepath
    else:
        BASEPATH = settings.get("BASEPATH", BASEPATH)
    if args.enforce:
        ENFORCE_BASEPATH = True
    else:
        ENFORCE_BASEPATH = settings.get("ENFORCE_BASEPATH", ENFORCE_BASEPATH)
    SSL_CERTIFICATE = settings.get("SSL_CERTIFICATE", SSL_CERTIFICATE)
    SSL_KEY = settings.get("SSL_KEY", SSL_KEY)
    if args.standalone:
        HASS_API = None
    else:
        HASS_API = settings.get("HASS_API", HASS_API)
    HASS_WS_API = settings.get("HASS_WS_API", HASS_WS_API)
    HASS_API_PASSWORD = settings.get("HASS_API_PASSWORD", HASS_API_PASSWORD)
    CREDENTIALS = settings.get("CREDENTIALS", CREDENTIALS)
    ALLOWED_NETWORKS = settings.get("ALLOWED_NETWORKS", ALLOWED_NETWORKS)
    if ALLOWED_NETWORKS and not all(ALLOWED_NETWORKS):
        LOG.warning("Invalid value for ALLOWED_NETWORKS. Using empty list.")
        ALLOWED_NETWORKS = []
    for net in ALLOWED_NETWORKS:
        try:
            ipaddress.ip_network(net)
        except Exception:
            LOG.warning("Invalid network in ALLOWED_NETWORKS: %s", net)
            ALLOWED_NETWORKS.remove(net)
    ALLOWED_DOMAINS = settings.get("ALLOWED_DOMAINS", ALLOWED_DOMAINS)
    if ALLOWED_DOMAINS and not all(ALLOWED_DOMAINS):
        LOG.warning("Invalid value for ALLOWED_DOMAINS. Using empty list.")
        ALLOWED_DOMAINS = []
    BANNED_IPS = settings.get("BANNED_IPS", BANNED_IPS)
    if BANNED_IPS and not all(BANNED_IPS):
        LOG.warning("Invalid value for BANNED_IPS. Using empty list.")
        BANNED_IPS = []
    for banned_ip in BANNED_IPS:
        try:
            ipaddress.ip_address(banned_ip)
        except Exception:
            LOG.warning("Invalid IP address in BANNED_IPS: %s", banned_ip)
            BANNED_IPS.remove(banned_ip)
    BANLIMIT = settings.get("BANLIMIT", BANLIMIT)
    if args.dev:
        DEV = True
    else:
        DEV = settings.get("DEV", DEV)
    IGNORE_PATTERN = settings.get("IGNORE_PATTERN", IGNORE_PATTERN)
    if IGNORE_PATTERN and not all(IGNORE_PATTERN):
        LOG.warning("Invalid value for IGNORE_PATTERN. Using empty list.")
        IGNORE_PATTERN = []
    if args.dirsfirst:
        DIRSFIRST = args.dirsfirst
    else:
        DIRSFIRST = settings.get("DIRSFIRST", DIRSFIRST)
    if args.hidehidden:
        HIDEHIDDEN = args.hidehidden
    else:
        HIDEHIDDEN = settings.get("HIDEHIDDEN", HIDEHIDDEN)
    SESAME = settings.get("SESAME", SESAME)
    SESAME_TOTP_SECRET = settings.get("SESAME_TOTP_SECRET", SESAME_TOTP_SECRET)
    VERIFY_HOSTNAME = settings.get("VERIFY_HOSTNAME", VERIFY_HOSTNAME)
    NOTIFY_SERVICE = settings.get("NOTIFY_SERVICE", NOTIFY_SERVICE_DEFAULT)
    IGNORE_SSL = settings.get("IGNORE_SSL", IGNORE_SSL)
    if IGNORE_SSL:
        # pylint: disable=protected-access
        ssl._create_default_https_context = ssl._create_unverified_context
    if args.username and args.password:
        USERNAME = args.username
        PASSWORD = args.password
    else:
        USERNAME = settings.get("USERNAME", USERNAME)
        PASSWORD = settings.get("PASSWORD", PASSWORD)
        PASSWORD = str(PASSWORD) if PASSWORD else None
    if CREDENTIALS and (USERNAME is None or PASSWORD is None):
        USERNAME = CREDENTIALS.split(":")[0]
        PASSWORD = ":".join(CREDENTIALS.split(":")[1:])
    if PASSWORD and PASSWORD.startswith("{sha256}"):
        PASSWORD = PASSWORD.lower()
    if SESAME_TOTP_SECRET:
        try:
            #pylint: disable=import-outside-toplevel
            import pyotp
            TOTP = pyotp.TOTP(SESAME_TOTP_SECRET)
        except ImportError:
            LOG.warning("Unable to import pyotp module")
        except Exception as err:
            LOG.warning("Unable to create TOTP object: %s", err)

def is_jwt(token):
    """Perform basic check if token is a JWT token."""
    return len(token.split('.')) == 3

def is_safe_path(basedir, path, follow_symlinks=True):
    """Check path for malicious traversal."""
    if basedir is None:
        return True
    if follow_symlinks:
        return os.path.realpath(path).startswith(basedir.encode('utf-8'))
    return os.path.abspath(path).startswith(basedir.encode('utf-8'))

def get_dircontent(path, repo=None):
    """Get content of directory."""
    dircontent = []
    if repo:
        untracked = [
            "%s%s%s"%(repo.working_dir, os.sep, e) for e in \
            ["%s"%os.sep.join(f.split('/')) for f in repo.untracked_files]
        ]
        staged = {}
        unstaged = {}
        try:
            for element in repo.index.diff("HEAD"):
                staged["%s%s%s" % (repo.working_dir,
                                   os.sep,
                                   "%s"%os.sep.join(
                                       element.b_path.split('/')))] = element.change_type
        except Exception as err:
            LOG.warning("Exception: %s", str(err))
        for element in repo.index.diff(None):
            unstaged["%s%s%s" % (repo.working_dir,
                                 os.sep,
                                 "%s"%os.sep.join(
                                     element.b_path.split('/')))] = element.change_type
    else:
        untracked = []
        staged = {}
        unstaged = {}

    def sorted_file_list():
        """Sort list of files / directories."""
        dirlist = [x for x in os.listdir(path) if os.path.isdir(os.path.join(path, x))]
        filelist = [x for x in os.listdir(path) if not os.path.isdir(os.path.join(path, x))]
        if HIDEHIDDEN:
            dirlist = [x for x in dirlist if not x.startswith('.')]
            filelist = [x for x in filelist if not x.startswith('.')]
        if DIRSFIRST:
            return sorted(dirlist, key=lambda x: x.lower()) + \
                sorted(filelist, key=lambda x: x.lower())
        return sorted(dirlist + filelist, key=lambda x: x.lower())

    for elem in sorted_file_list():
        edata = {}
        edata['name'] = elem
        edata['dir'] = path
        edata['fullpath'] = os.path.abspath(os.path.join(path, elem))
        edata['type'] = 'dir' if os.path.isdir(edata['fullpath']) else 'file'
        try:
            stats = os.stat(os.path.join(path, elem))
            edata['size'] = stats.st_size
            edata['modified'] = stats.st_mtime
            edata['created'] = stats.st_ctime
        except Exception:
            edata['size'] = 0
            edata['modified'] = 0
            edata['created'] = 0
        edata['changetype'] = None
        edata['gitstatus'] = bool(repo)
        edata['gittracked'] = 'untracked' if edata['fullpath'] in untracked else 'tracked'
        if edata['fullpath'] in unstaged:
            edata['gitstatus'] = 'unstaged'
            edata['changetype'] = unstaged.get(edata['name'], None)
        elif edata['fullpath'] in staged:
            edata['gitstatus'] = 'staged'
            edata['changetype'] = staged.get(edata['name'], None)

        hidden = False
        if IGNORE_PATTERN is not None:
            for file_pattern in IGNORE_PATTERN:
                if fnmatch.fnmatch(edata['name'], file_pattern):
                    hidden = True

        if not hidden:
            dircontent.append(edata)

    return dircontent

def load_file(filename, static=False):
    """Load files. If static is True, set to path of configurator."""
    if static:
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), filename)
    try:
        with open(filename, 'rb') as fptr:
            content = fptr.read()
            return content
    except Exception as err:
        LOG.critical(err)
        return None

def password_problems(password, name="UNKNOWN"):
    """Rudimentary checks for password strength."""
    problems = 0
    password = str(password)
    if password is None:
        return problems
    if len(password) < 8:
        LOG.warning("Password %s is too short", name)
        problems += 1
    if password.isalpha():
        LOG.warning("Password %s does not contain digits", name)
        problems += 2
    if password.isdigit():
        LOG.warning("Password %s does not contain alphabetic characters", name)
        problems += 4
    quota = len(set(password)) / len(password)
    exp = len(password) ** len(set(password))
    score = exp / quota / 8
    if score < 65536:
        LOG.warning("Password %s does not contain enough unique characters (%i)",
                    name, len(set(password)))
        problems += 8
    return problems

def check_access(clientip):
    """Check if IP is allowed to access the configurator / API."""
    global BANNED_IPS
    if clientip in BANNED_IPS:
        LOG.warning("Client IP banned.")
        return False
    if not ALLOWED_NETWORKS:
        return True
    for net in ALLOWED_NETWORKS:
        ipobject = ipaddress.ip_address(clientip)
        if ipobject in ipaddress.ip_network(net):
            return True
    LOG.warning("Client IP not within allowed networks.")
    if ALLOWED_DOMAINS:
        for domain in ALLOWED_DOMAINS:
            try:
                domain_data = socket.getaddrinfo(domain, None)
            except Exception as err:
                LOG.warning("Unable to lookup domain data: %s", err)
                continue
            for res in domain_data:
                if res[0] in [socket.AF_INET, socket.AF_INET6]:
                    if res[4][0] == clientip:
                        return True
        LOG.warning("Client IP not within allowed domains.")
    BANNED_IPS.append(clientip)
    return False

def verify_hostname(request_hostname):
    """Verify the provided host header is correct."""
    if VERIFY_HOSTNAME:
        if VERIFY_HOSTNAME not in request_hostname:
            return False
    return True

class RequestHandler(BaseHTTPRequestHandler):
    """Request handler."""
    # pylint: disable=redefined-builtin
    def log_message(self, format, *args):
        LOG.info("%s - %s", self.client_address[0], format % args)

    # pylint: disable=invalid-name
    def do_BLOCK(self, status=420, reason="Policy not fulfilled"):
        """Customized do_BLOCK method."""
        self.send_response(status)
        self.end_headers()
        self.wfile.write(bytes(reason, "utf8"))

    # pylint: disable=invalid-name
    def do_GET(self):
        """Customized do_GET method."""
        if not verify_hostname(self.headers.get('Host', '')):
            self.do_BLOCK(403, "Forbidden")
            return
        req = urlparse(self.path)
        if SESAME or TOTP:
            chunk = req.path.split("/")[-1]
            if SESAME and chunk == SESAME:
                if self.client_address[0] not in ALLOWED_NETWORKS:
                    ALLOWED_NETWORKS.append(self.client_address[0])
                if self.client_address[0] in BANNED_IPS:
                    BANNED_IPS.remove(self.client_address[0])
                url = req.path[:req.path.rfind(chunk)]
                self.send_response(302)
                self.send_header('Location', url)
                self.end_headers()
                data = {
                    "title": "HASS Configurator - SESAME access",
                    "message": "Your SESAME token has been used to whitelist " \
                    "the IP address %s." % self.client_address[0]
                }
                notify(**data)
                return
            if TOTP and TOTP.verify(chunk):
                if self.client_address[0] not in ALLOWED_NETWORKS:
                    ALLOWED_NETWORKS.append(self.client_address[0])
                if self.client_address[0] in BANNED_IPS:
                    BANNED_IPS.remove(self.client_address[0])
                url = req.path[:req.path.rfind(chunk)]
                self.send_response(302)
                self.send_header('Location', url)
                self.end_headers()
                data = {
                    "title": "HASS Configurator - SESAME access",
                    "message": "Your SESAME token has been used to whitelist " \
                    "the IP address %s." % self.client_address[0]
                }
                notify(**data)
                return
        if not check_access(self.client_address[0]):
            self.do_BLOCK()
            return
        query = parse_qs(req.query)
        self.send_response(200)
        # pylint: disable=no-else-return
        if req.path.endswith('/api/file'):
            content = ""
            filename = query.get('filename', None)
            try:
                if filename:
                    is_raw = False
                    filename = unquote(filename[0]).encode('utf-8')
                    if ENFORCE_BASEPATH and not is_safe_path(BASEPATH, filename):
                        raise OSError('Access denied.')
                    filepath = os.path.join(BASEDIR.encode('utf-8'), filename)
                    if os.path.isfile(filepath):
                        mimetype = mimetypes.guess_type(filepath.decode('utf-8'))
                        if mimetype[0] is not None:
                            if mimetype[0].split('/')[0] == 'image':
                                is_raw = True
                        if is_raw:
                            content = load_file(filepath)
                            self.send_header('Content-type', mimetype[0])
                        else:
                            content = load_file(filepath).decode("utf-8")
                            self.send_header('Content-type', 'text/text')
                    else:
                        self.send_header('Content-type', 'text/text')
                        content = "File not found"
            except Exception as err:
                LOG.warning(err)
                self.send_header('Content-type', 'text/text')
                content = str(err)
            self.end_headers()
            if is_raw:
                self.wfile.write(content)
            else:
                self.wfile.write(bytes(content, "utf8"))
            return
        elif req.path.endswith('/api/download'):
            content = ""
            filename = query.get('filename', None)
            try:
                if filename:
                    filename = unquote(filename[0]).encode('utf-8')
                    if ENFORCE_BASEPATH and not is_safe_path(BASEPATH, filename):
                        raise OSError('Access denied.')
                    LOG.info(filename)
                    filepath = os.path.join(BASEDIR.encode('utf-8'), filename)
                    if os.path.isfile(filepath):
                        filecontent = load_file(filepath)
                        self.send_header(
                            'Content-Disposition',
                            'attachment; filename=%s' % filename.decode('utf-8').split(os.sep)[-1])
                        self.end_headers()
                        self.wfile.write(filecontent)
                        return
                    content = "File not found"
            except Exception as err:
                LOG.warning(err)
                content = str(err)
            self.send_header('Content-type', 'text/text')
            self.wfile.write(bytes(content, "utf8"))
            return
        elif req.path.endswith('/api/listdir'):
            content = {'error': None}
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            dirpath = query.get('path', None)
            try:
                if dirpath:
                    dirpath = unquote(dirpath[0]).encode('utf-8')
                    if os.path.isdir(dirpath):
                        if ENFORCE_BASEPATH and not is_safe_path(BASEPATH,
                                                                 dirpath):
                            raise OSError('Access denied.')
                        repo = None
                        activebranch = None
                        dirty = False
                        branches = []
                        if REPO:
                            try:
                                # pylint: disable=not-callable
                                repo = REPO(dirpath.decode('utf-8'),
                                            search_parent_directories=True)
                                activebranch = repo.active_branch.name
                                dirty = repo.is_dirty()
                                for branch in repo.branches:
                                    branches.append(branch.name)
                            except Exception as err:
                                LOG.debug("Exception (no repo): %s", str(err))
                        dircontent = get_dircontent(dirpath.decode('utf-8'), repo)
                        filedata = {
                            'content': dircontent,
                            'abspath': os.path.abspath(dirpath).decode('utf-8'),
                            'parent': os.path.dirname(os.path.abspath(dirpath)).decode('utf-8'),
                            'branches': branches,
                            'activebranch': activebranch,
                            'dirty': dirty,
                            'error': None
                        }
                        self.wfile.write(bytes(json.dumps(filedata), "utf8"))
            except Exception as err:
                LOG.warning(err)
                content['error'] = str(err)
                self.wfile.write(bytes(json.dumps(content), "utf8"))
            return
        elif req.path.endswith('/api/abspath'):
            content = ""
            self.send_header('Content-type', 'text/text')
            self.end_headers()
            dirpath = query.get('path', None)
            if dirpath:
                dirpath = unquote(dirpath[0]).encode('utf-8')
                LOG.debug(dirpath)
                absp = os.path.abspath(dirpath)
                LOG.debug(absp)
                if os.path.isdir(dirpath):
                    self.wfile.write(os.path.abspath(dirpath))
            return
        elif req.path.endswith('/api/parent'):
            content = ""
            self.send_header('Content-type', 'text/text')
            self.end_headers()
            dirpath = query.get('path', None)
            if dirpath:
                dirpath = unquote(dirpath[0]).encode('utf-8')
                LOG.debug(dirpath)
                absp = os.path.abspath(dirpath)
                LOG.debug(absp)
                if os.path.isdir(dirpath):
                    self.wfile.write(os.path.abspath(os.path.dirname(dirpath)))
            return
        elif req.path.endswith('/api/netstat'):
            content = ""
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            res = {
                "allowed_networks": ALLOWED_NETWORKS,
                "banned_ips": BANNED_IPS
            }
            self.wfile.write(bytes(json.dumps(res), "utf8"))
            return
        elif req.path.endswith('/api/restart'):
            LOG.info("/api/restart")
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            res = {"restart": False}
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                if HASS_API_PASSWORD:
                    if is_jwt(HASS_API_PASSWORD):
                        headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
                    else:
                        headers["x-ha-access"] = HASS_API_PASSWORD
                req = urllib.request.Request(
                    "%sservices/homeassistant/restart" % HASS_API,
                    headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    res = json.loads(response.read().decode('utf-8'))
                    LOG.debug(res)
            except Exception as err:
                LOG.warning(err)
                res['restart'] = str(err)
            self.wfile.write(bytes(json.dumps(res), "utf8"))
            return
        elif req.path.endswith('/api/check_config'):
            LOG.info("/api/check_config")
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            res = {"check_config": False}
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                if HASS_API_PASSWORD:
                    if is_jwt(HASS_API_PASSWORD):
                        headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
                    else:
                        headers["x-ha-access"] = HASS_API_PASSWORD
                req = urllib.request.Request(
                    "%sservices/homeassistant/check_config" % HASS_API,
                    headers=headers, method='POST')
            except Exception as err:
                LOG.warning(err)
                res['restart'] = str(err)
            self.wfile.write(bytes(json.dumps(res), "utf8"))
            return
        elif req.path.endswith('/api/reload_automations'):
            LOG.info("/api/reload_automations")
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            res = {"reload_automations": False}
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                if HASS_API_PASSWORD:
                    if is_jwt(HASS_API_PASSWORD):
                        headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
                    else:
                        headers["x-ha-access"] = HASS_API_PASSWORD
                req = urllib.request.Request(
                    "%sservices/automation/reload" % HASS_API,
                    headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    LOG.debug(json.loads(response.read().decode('utf-8')))
                    res['service'] = "called successfully"
            except Exception as err:
                LOG.warning(err)
                res['restart'] = str(err)
            self.wfile.write(bytes(json.dumps(res), "utf8"))
            return
        elif req.path.endswith('/api/reload_scripts'):
            LOG.info("/api/reload_scripts")
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            res = {"reload_scripts": False}
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                if HASS_API_PASSWORD:
                    if is_jwt(HASS_API_PASSWORD):
                        headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
                    else:
                        headers["x-ha-access"] = HASS_API_PASSWORD
                req = urllib.request.Request(
                    "%sservices/script/reload" % HASS_API,
                    headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    LOG.debug(json.loads(response.read().decode('utf-8')))
                    res['service'] = "called successfully"
            except Exception as err:
                LOG.warning(err)
                res['restart'] = str(err)
            self.wfile.write(bytes(json.dumps(res), "utf8"))
            return
        elif req.path.endswith('/api/reload_groups'):
            LOG.info("/api/reload_groups")
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            res = {"reload_groups": False}
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                if HASS_API_PASSWORD:
                    if is_jwt(HASS_API_PASSWORD):
                        headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
                    else:
                        headers["x-ha-access"] = HASS_API_PASSWORD
                req = urllib.request.Request(
                    "%sservices/group/reload" % HASS_API,
                    headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    LOG.debug(json.loads(response.read().decode('utf-8')))
                    res['service'] = "called successfully"
            except Exception as err:
                LOG.warning(err)
                res['restart'] = str(err)
            self.wfile.write(bytes(json.dumps(res), "utf8"))
            return
        elif req.path.endswith('/api/reload_core'):
            LOG.info("/api/reload_core")
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            res = {"reload_core": False}
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                if HASS_API_PASSWORD:
                    if is_jwt(HASS_API_PASSWORD):
                        headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
                    else:
                        headers["x-ha-access"] = HASS_API_PASSWORD
                req = urllib.request.Request(
                    "%sservices/homeassistant/reload_core_config" % HASS_API,
                    headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    LOG.debug(json.loads(response.read().decode('utf-8')))
                    res['service'] = "called successfully"
            except Exception as err:
                LOG.warning(err)
                res['restart'] = str(err)
            self.wfile.write(bytes(json.dumps(res), "utf8"))
            return
        elif req.path.endswith('/'):
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            loadfile = query.get('loadfile', [None])[0]
            if loadfile is None:
                loadfile = 'null'
            else:
                loadfile = "'%s'" % loadfile
            services = "[]"
            events = "[]"
            states = "[]"
            try:
                if HASS_API:
                    headers = {
                        "Content-Type": "application/json"
                    }
                    if HASS_API_PASSWORD:
                        if is_jwt(HASS_API_PASSWORD):
                            headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
                        else:
                            headers["x-ha-access"] = HASS_API_PASSWORD

                    req = urllib.request.Request("%sservices" % HASS_API,
                                                 headers=headers, method='GET')
                    with urllib.request.urlopen(req) as response:
                        services = response.read().decode('utf-8')

                    req = urllib.request.Request("%sevents" % HASS_API,
                                                 headers=headers, method='GET')
                    with urllib.request.urlopen(req) as response:
                        events = response.read().decode('utf-8')

                    req = urllib.request.Request("%sstates" % HASS_API,
                                                 headers=headers, method='GET')
                    with urllib.request.urlopen(req) as response:
                        states = response.read().decode('utf-8')

            except Exception as err:
                LOG.warning("Exception getting bootstrap")
                LOG.warning(err)

            color = ""
            try:
                response = urllib.request.urlopen(RELEASEURL)
                latest = json.loads(response.read().decode('utf-8'))['tag_name']
                if VERSION != latest:
                    color = "red-text"
            except Exception as err:
                LOG.warning("Exception getting release")
                LOG.warning(err)
            ws_api = ""
            if HASS_API:
                protocol, uri = HASS_API.split("//")
                ws_api = "%s://%swebsocket" % (
                    "wss" if protocol == 'https' else 'ws', uri
                )
            if HASS_WS_API:
                ws_api = HASS_WS_API
            standalone = ""
            if not HASS_API:
                standalone = "toggle_hass_panels();"
            try:
                html = Template(load_file("dev.html", static=True).decode('utf-8'))
                html = html.safe_substitute(
                    services=services,
                    events=events,
                    states=states,
                    loadfile=loadfile,
                    current=VERSION,
                    versionclass=color,
                    githidden="" if GIT else "hiddendiv",
                    # pylint: disable=anomalous-backslash-in-string
                    separator="\%s" % os.sep if os.sep == "\\" else os.sep,
                    your_address=self.client_address[0],
                    listening_address="%s://%s:%i" % (
                        'https' if SSL_CERTIFICATE else 'http', LISTENIP, PORT),
                    hass_api_address="%s" % (HASS_API, ),
                    hass_ws_address=ws_api,
                    api_password=HASS_API_PASSWORD if HASS_API_PASSWORD else "",
                    standalone=standalone)
            except Exception as err:
                LOG.warning("Error getting html: %s", err)
                html = ERROR_HTML
            self.wfile.write(bytes(html, "utf8"))
            return
        elif req.path.endswith('/jquery-3.4.1.min.js'):
            try:
                data = load_file("jquery-3.4.1.min.js", static=True)
            except Exception as err:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(bytes("File not found", "utf8"))
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            self.wfile.write(data)
        elif req.path.endswith('/flUhRq6tzZclQEJ-Vdg-IuiaDsNc.woff2'):
            try:
                data = load_file("flUhRq6tzZclQEJ-Vdg-IuiaDsNc.woff2", static=True)
            except Exception as err:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(bytes("File not found", "utf8"))
            self.send_header('Content-type', 'font/woff')
            self.end_headers()
            self.wfile.write(data)
        elif req.path.endswith('/js-yaml.min.js'):
            try:
                data = load_file("js-yaml.min.js", static=True)
            except Exception as err:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(bytes("File not found", "utf8"))
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            self.wfile.write(data)
        elif req.path.endswith('/materialize.min.js'):
            try:
                data = load_file("materialize.min.js", static=True)
            except Exception as err:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(bytes("File not found", "utf8"))
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            self.wfile.write(data)
        elif req.path.endswith('/material-icons.fallback.css'):
            try:
                data = load_file("material-icons.fallback.css", static=True)
            except Exception as err:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(bytes("File not found", "utf8"))
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            self.wfile.write(data)
        elif req.path.endswith('/style.css'):
            try:
                data = load_file("style.css", static=True)
            except Exception as err:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(bytes("File not found", "utf8"))
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(bytes("File not found", "utf8"))

    # pylint: disable=invalid-name
    def do_POST(self):
        """Customized do_POST method."""
        global ALLOWED_NETWORKS, BANNED_IPS
        if not verify_hostname(self.headers.get('Host', '')):
            self.do_BLOCK(403, "Forbidden")
            return
        if not check_access(self.client_address[0]):
            self.do_BLOCK()
            return
        req = urlparse(self.path)

        response = {
            "error": True,
            "message": "Generic failure"
        }

        length = int(self.headers['content-length'])
        if req.path.endswith('/api/save'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'filename' in postvars.keys() and 'text' in postvars.keys():
                if postvars['filename'] and postvars['text']:
                    try:
                        filename = unquote(postvars['filename'][0])
                        response['file'] = filename
                        with open(filename, 'wb') as fptr:
                            fptr.write(bytes(postvars['text'][0], "utf-8"))
                        self.send_response(200)
                        self.send_header('Content-type', 'text/json')
                        self.end_headers()
                        response['error'] = False
                        response['message'] = "File saved successfully"
                        self.wfile.write(bytes(json.dumps(response), "utf8"))
                        return
                    except Exception as err:
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing filename or text"
        elif req.path.endswith('/api/upload'):
            if length > 104857600: #100 MB for now
                read = 0
                while read < length:
                    read += len(self.rfile.read(min(66556, length - read)))
                self.send_response(200)
                self.send_header('Content-type', 'text/json')
                self.end_headers()
                response['error'] = True
                response['message'] = "File too big: %i" % read
                self.wfile.write(bytes(json.dumps(response), "utf8"))
                return
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': self.headers['Content-Type'],
                })
            filename = form['file'].filename
            filepath = form['path'].file.read()
            data = form['file'].file.read()
            open("%s%s%s" % (filepath, os.sep, filename), "wb").write(data)
            self.send_response(200)
            self.send_header('Content-type', 'text/json')
            self.end_headers()
            response['error'] = False
            response['message'] = "Upload successful"
            self.wfile.write(bytes(json.dumps(response), "utf8"))
            return
        elif req.path.endswith('/api/delete'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys():
                if postvars['path']:
                    try:
                        delpath = unquote(postvars['path'][0])
                        response['path'] = delpath
                        try:
                            if os.path.isdir(delpath):
                                os.rmdir(delpath)
                            else:
                                os.unlink(delpath)
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            response['error'] = False
                            response['message'] = "Deletion successful"
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            LOG.warning(err)
                            response['error'] = True
                            response['message'] = str(err)

                    except Exception as err:
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing filename or text"
        elif req.path.endswith('/api/exec_command'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'command' in postvars.keys():
                if postvars['command']:
                    try:
                        command = shlex.split(postvars['command'][0])
                        timeout = 15
                        if 'timeout' in postvars.keys():
                            if postvars['timeout']:
                                timeout = int(postvars['timeout'][0])
                        try:
                            proc = subprocess.Popen(
                                command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
                            stdout, stderr = proc.communicate(timeout=timeout)
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            response['error'] = False
                            response['message'] = "Command executed: %s" % postvars['command'][0]
                            response['returncode'] = proc.returncode
                            try:
                                response['stdout'] = stdout.decode(sys.getdefaultencoding())
                            except Exception as err:
                                LOG.warning(err)
                                response['stdout'] = stdout.decode("utf-8", errors="replace")
                            try:
                                response['stderr'] = stderr.decode(sys.getdefaultencoding())
                            except Exception as err:
                                LOG.warning(err)
                                response['stderr'] = stderr.decode("utf-8", errors="replace")
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            LOG.warning(err)
                            response['error'] = True
                            response['message'] = str(err)

                    except Exception as err:
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing command"
        elif req.path.endswith('/api/gitadd'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys():
                if postvars['path']:
                    try:
                        addpath = unquote(postvars['path'][0])
                        # pylint: disable=not-callable
                        repo = REPO(addpath,
                                    search_parent_directories=True)
                        filepath = "/".join(
                            addpath.split(os.sep)[len(repo.working_dir.split(os.sep)):])
                        response['path'] = filepath
                        try:
                            repo.index.add([filepath])
                            response['error'] = False
                            response['message'] = "Added file to index"
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            LOG.warning(err)
                            response['error'] = True
                            response['message'] = str(err)

                    except Exception as err:
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing filename"
        elif req.path.endswith('/api/gitdiff'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys():
                if postvars['path']:
                    try:
                        diffpath = unquote(postvars['path'][0])
                        # pylint: disable=not-callable
                        repo = REPO(diffpath,
                                    search_parent_directories=True)
                        filepath = "/".join(
                            diffpath.split(os.sep)[len(repo.working_dir.split(os.sep)):])
                        response['path'] = filepath
                        try:
                            diff = repo.index.diff(None,
                                                   create_patch=True,
                                                   paths=filepath)[0].diff.decode("utf-8")
                            response['error'] = False
                            response['message'] = diff
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            LOG.warning(err)
                            response['error'] = True
                            response['message'] = "Unable to load diff: %s" % str(err)

                    except Exception as err:
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing filename"
        elif req.path.endswith('/api/commit'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys() and 'message' in postvars.keys():
                if postvars['path'] and postvars['message']:
                    try:
                        commitpath = unquote(postvars['path'][0])
                        response['path'] = commitpath
                        message = unquote(postvars['message'][0])
                        # pylint: disable=not-callable
                        repo = REPO(commitpath,
                                    search_parent_directories=True)
                        try:
                            repo.index.commit(message)
                            response['error'] = False
                            response['message'] = "Changes commited"
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            response['error'] = True
                            response['message'] = str(err)
                            LOG.debug(response)

                    except Exception as err:
                        response['message'] = "Not a git repository: %s" % (str(err))
                        LOG.warning("Exception (no repo): %s", str(err))
            else:
                response['message'] = "Missing path"
        elif req.path.endswith('/api/checkout'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys() and 'branch' in postvars.keys():
                if postvars['path'] and postvars['branch']:
                    try:
                        branchpath = unquote(postvars['path'][0])
                        response['path'] = branchpath
                        branch = unquote(postvars['branch'][0])
                        # pylint: disable=not-callable
                        repo = REPO(branchpath,
                                    search_parent_directories=True)
                        try:
                            head = [h for h in repo.heads if h.name == branch][0]
                            head.checkout()
                            response['error'] = False
                            response['message'] = "Checked out %s" % branch
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            response['error'] = True
                            response['message'] = str(err)
                            LOG.warning(response)

                    except Exception as err:
                        response['message'] = "Not a git repository: %s" % (str(err))
                        LOG.warning("Exception (no repo): %s", str(err))
            else:
                response['message'] = "Missing path or branch"
        elif req.path.endswith('/api/newbranch'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys() and 'branch' in postvars.keys():
                if postvars['path'] and postvars['branch']:
                    try:
                        branchpath = unquote(postvars['path'][0])
                        response['path'] = branchpath
                        branch = unquote(postvars['branch'][0])
                        # pylint: disable=not-callable
                        repo = REPO(branchpath,
                                    search_parent_directories=True)
                        try:
                            repo.git.checkout("HEAD", b=branch)
                            response['error'] = False
                            response['message'] = "Created and checked out %s" % branch
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            response['error'] = True
                            response['message'] = str(err)
                            LOG.warning(response)

                    except Exception as err:
                        response['message'] = "Not a git repository: %s" % (str(err))
                        LOG.warning("Exception (no repo): %s", str(err))
            else:
                response['message'] = "Missing path or branch"
        elif req.path.endswith('/api/init'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys():
                if postvars['path']:
                    try:
                        repopath = unquote(postvars['path'][0])
                        response['path'] = repopath
                        try:
                            repo = REPO.init(repopath)
                            response['error'] = False
                            response['message'] = "Initialized repository in %s" % repopath
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            response['error'] = True
                            response['message'] = str(err)
                            LOG.warning(response)

                    except Exception as err:
                        response['message'] = "Not a git repository: %s" % (str(err))
                        LOG.warning("Exception (no repo): %s", str(err))
            else:
                response['message'] = "Missing path or branch"
        elif req.path.endswith('/api/push'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys():
                if postvars['path']:
                    try:
                        repopath = unquote(postvars['path'][0])
                        response['path'] = repopath
                        try:
                            # pylint: disable=not-callable
                            repo = REPO(repopath)
                            urls = []
                            if repo.remotes:
                                for url in repo.remotes.origin.urls:
                                    urls.append(url)
                            if not urls:
                                response['error'] = True
                                response['message'] = "No remotes configured for %s" % repopath
                            else:
                                repo.remotes.origin.push()
                                response['error'] = False
                                response['message'] = "Pushed to %s" % urls[0]
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            response['error'] = True
                            response['message'] = str(err)
                            LOG.warning(response)

                    except Exception as err:
                        response['message'] = "Not a git repository: %s" % (str(err))
                        LOG.warning("Exception (no repo): %s", str(err))
            else:
                response['message'] = "Missing path or branch"
        elif req.path.endswith('/api/stash'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys():
                if postvars['path']:
                    try:
                        repopath = unquote(postvars['path'][0])
                        response['path'] = repopath
                        try:
                            # pylint: disable=not-callable
                            repo = REPO(repopath)
                            returnvalue = repo.git.stash()
                            response['error'] = False
                            response['message'] = "%s\n%s" % (returnvalue, repopath)
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            response['error'] = True
                            response['message'] = str(err)
                            LOG.warning(response)

                    except Exception as err:
                        response['message'] = "Not a git repository: %s" % (str(err))
                        LOG.warning("Exception (no repo): %s", str(err))
            else:
                response['message'] = "Missing path or branch"
        elif req.path.endswith('/api/newfolder'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys() and 'name' in postvars.keys():
                if postvars['path'] and postvars['name']:
                    try:
                        basepath = unquote(postvars['path'][0])
                        name = unquote(postvars['name'][0])
                        response['path'] = os.path.join(basepath, name)
                        try:
                            os.makedirs(response['path'])
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            response['error'] = False
                            response['message'] = "Folder created"
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            LOG.warning(err)
                            response['error'] = True
                            response['message'] = str(err)
                    except Exception as err:
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
        elif req.path.endswith('/api/newfile'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'path' in postvars.keys() and 'name' in postvars.keys():
                if postvars['path'] and postvars['name']:
                    try:
                        basepath = unquote(postvars['path'][0])
                        name = unquote(postvars['name'][0])
                        response['path'] = os.path.join(basepath, name)
                        try:
                            with open(response['path'], 'w') as fptr:
                                fptr.write("")
                            self.send_response(200)
                            self.send_header('Content-type', 'text/json')
                            self.end_headers()
                            response['error'] = False
                            response['message'] = "File created"
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            LOG.warning(err)
                            response['error'] = True
                            response['message'] = str(err)
                    except Exception as err:
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing filename or text"
        elif req.path.endswith('/api/allowed_networks'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'network' in postvars.keys() and 'method' in postvars.keys():
                if postvars['network'] and postvars['method']:
                    try:
                        network = unquote(postvars['network'][0])
                        method = unquote(postvars['method'][0])
                        if method == 'remove':
                            if network in ALLOWED_NETWORKS:
                                ALLOWED_NETWORKS.remove(network)
                                if not ALLOWED_NETWORKS:
                                    ALLOWED_NETWORKS.append("0.0.0.0/0")
                            response['error'] = False
                        elif method == 'add':
                            ipaddress.ip_network(network)
                            ALLOWED_NETWORKS.append(network)
                            response['error'] = False
                        else:
                            response['error'] = True
                        self.send_response(200)
                        self.send_header('Content-type', 'text/json')
                        self.end_headers()
                        response['error'] = False
                        response['message'] = "ALLOWED_NETWORKS (%s): %s" % (method, network)
                        self.wfile.write(bytes(json.dumps(response), "utf8"))
                        return
                    except Exception as err:
                        response['error'] = True
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing network"
        elif req.path.endswith('/api/banned_ips'):
            try:
                postvars = parse_qs(self.rfile.read(length).decode('utf-8'),
                                    keep_blank_values=1)
            except Exception as err:
                LOG.warning(err)
                response['message'] = "%s" % (str(err))
                postvars = {}
            if 'ip' in postvars.keys() and 'method' in postvars.keys():
                if postvars['ip'] and postvars['method']:
                    try:
                        ip_address = unquote(postvars['ip'][0])
                        method = unquote(postvars['method'][0])
                        if method == 'unban':
                            if ip_address in BANNED_IPS:
                                BANNED_IPS.remove(ip_address)
                            response['error'] = False
                        elif method == 'ban':
                            ipaddress.ip_network(ip_address)
                            BANNED_IPS.append(ip_address)
                        else:
                            response['error'] = True
                        self.send_response(200)
                        self.send_header('Content-type', 'text/json')
                        self.end_headers()
                        response['message'] = "BANNED_IPS (%s): %s" % (method, ip_address)
                        self.wfile.write(bytes(json.dumps(response), "utf8"))
                        return
                    except Exception as err:
                        response['error'] = True
                        response['message'] = "%s" % (str(err))
                        LOG.warning(err)
            else:
                response['message'] = "Missing IP"
        else:
            response['message'] = "Invalid method"
        self.send_response(200)
        self.send_header('Content-type', 'text/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(response), "utf8"))
        return

class AuthHandler(RequestHandler):
    """Handler to verify auth header."""
    def do_BLOCK(self, status=420, reason="Policy not fulfilled"):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(bytes(reason, "utf8"))

    # pylint: disable=invalid-name
    def do_AUTHHEAD(self):
        """Request authorization."""
        LOG.info("Requesting authorization")
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"HASS-Configurator\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        if not verify_hostname(self.headers.get('Host', '')):
            self.do_BLOCK(403, "Forbidden")
            return
        header = self.headers.get('Authorization', None)
        if header is None:
            self.do_AUTHHEAD()
            self.wfile.write(bytes('no auth header received', 'utf-8'))
        else:
            authorization = header.split()
            if len(authorization) == 2 and authorization[0] == "Basic":
                plain = base64.b64decode(authorization[1]).decode("utf-8")
                parts = plain.split(':')
                username = parts[0]
                password = ":".join(parts[1:])
                if PASSWORD.startswith("{sha256}"):
                    password = "{sha256}%s" % hashlib.sha256(password.encode("utf-8")).hexdigest()
                if username == USERNAME and password == PASSWORD:
                    if BANLIMIT:
                        FAIL2BAN_IPS.pop(self.client_address[0], None)
                    super().do_GET()
                    return
            if BANLIMIT:
                bancounter = FAIL2BAN_IPS.get(self.client_address[0], 1)
                if bancounter >= BANLIMIT:
                    LOG.warning("Blocking access from %s", self.client_address[0])
                    self.do_BLOCK()
                    return
                FAIL2BAN_IPS[self.client_address[0]] = bancounter + 1
            self.do_AUTHHEAD()
            self.wfile.write(bytes('Authentication required', 'utf-8'))

    def do_POST(self):
        if not verify_hostname(self.headers.get('Host', '')):
            self.do_BLOCK(403, "Forbidden")
            return
        header = self.headers.get('Authorization', None)
        if header is None:
            self.do_AUTHHEAD()
            self.wfile.write(bytes('no auth header received', 'utf-8'))
        else:
            authorization = header.split()
            if len(authorization) == 2 and authorization[0] == "Basic":
                plain = base64.b64decode(authorization[1]).decode("utf-8")
                parts = plain.split(':')
                username = parts[0]
                password = ":".join(parts[1:])
                if PASSWORD.startswith("{sha256}"):
                    password = "{sha256}%s" % hashlib.sha256(password.encode("utf-8")).hexdigest()
                if username == USERNAME and password == PASSWORD:
                    if BANLIMIT:
                        FAIL2BAN_IPS.pop(self.client_address[0], None)
                    super().do_POST()
                    return
            if BANLIMIT:
                bancounter = FAIL2BAN_IPS.get(self.client_address[0], 1)
                if bancounter >= BANLIMIT:
                    LOG.warning("Blocking access from %s", self.client_address[0])
                    self.do_BLOCK()
                    return
                FAIL2BAN_IPS[self.client_address[0]] = bancounter + 1
            self.do_AUTHHEAD()
            self.wfile.write(bytes('Authentication required', 'utf-8'))

class SimpleServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Server class."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass)

def notify(title="HASS Configurator",
           message="Notification by HASS Configurator",
           notification_id=None):
    """Helper function to send notifications via HASS."""
    if not HASS_API or not NOTIFY_SERVICE:
        return
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "title": title,
        "message": message
    }
    if notification_id and NOTIFY_SERVICE == NOTIFY_SERVICE_DEFAULT:
        data["notification_id"] = notification_id
    if HASS_API_PASSWORD:
        if is_jwt(HASS_API_PASSWORD):
            headers["Authorization"] = "Bearer %s" % HASS_API_PASSWORD
        else:
            headers["x-ha-access"] = HASS_API_PASSWORD
    req = urllib.request.Request(
        "%sservices/%s" % (HASS_API, NOTIFY_SERVICE.replace('.', '/')),
        data=bytes(json.dumps(data).encode('utf-8')),
        headers=headers, method='POST')
    LOG.info("%s", data)
    try:
        with urllib.request.urlopen(req) as response:
            message = response.read().decode('utf-8')
            LOG.debug(message)
    except Exception as err:
        LOG.warning("Exception while creating notification: %s", err)

def main():
    """Main function, duh!"""
    global HTTPD
    signal.signal(signal.SIGINT, signal_handler)
    parser = argparse.ArgumentParser(description="Visit " \
    "https://github.com/danielperna84/hass-configurator for more details " \
    "about the availble options.")
    parser.add_argument(
        'settings', nargs='?',
        help="Path to file with persistent settings.")
    parser.add_argument(
        '--listen', '-l', nargs='?',
        help="The IP address the service is listening on. Default: 0.0.0.0")
    parser.add_argument(
        '--port', '-p', nargs='?', type=int,
        help="The port the service is listening on. " \
        "0 allocates a dynamic port. Default: 3218")
    parser.add_argument(
        '--allowed_networks', '-a', nargs='?',
        help="Comma-separated list of allowed networks / IP addresses " \
        "from which access is allowed. Eg. 127.0.0.1,192.168.0.0/16. " \
        "By default access is allowed from anywhere.")
    parser.add_argument(
        '--username', '-U', nargs='?',
        help="Username required for access.")
    parser.add_argument(
        '--password', '-P', nargs='?',
        help="Password required for access.")
    parser.add_argument(
        '--sesame', '-S', nargs='?',
        help="SESAME token for whitelisting client IPs by accessing " \
        "a scret URL: http://1.2.3.4:3218/secret_sesame_token")
    parser.add_argument(
        '--basepath', '-b', nargs='?',
        help="Path to initially serve files from")
    parser.add_argument(
        '--enforce', '-e', action='store_true',
        help="Lock the configurator into the basepath.")
    parser.add_argument(
        '--standalone', '-s', action='store_true',
        help="Don't fetch data from HASS_API.")
    parser.add_argument(
        '--dirsfirst', '-d', action='store_true',
        help="Display directories first.")
    parser.add_argument(
        '--hidehidden', '-H', action='store_true',
        help="Don't display hidden files.")
    parser.add_argument(
        '--git', '-g', action='store_true',
        help="Enable GIT support.")
    parser.add_argument(
        '--dev', '-D', action='store_true',
        help="Enable Dev-Mode (serve dev.html instead of embedded HTML).")
    args = parser.parse_args()
    load_settings(args)
    LOG.info("Starting server")

    try:
        problems = None
        if HASS_API_PASSWORD:
            problems = password_problems(HASS_API_PASSWORD, "HASS_API_PASSWORD")
        if problems:
            data = {
                "title": "HASS Configurator - Password warning",
                "message": "Your HASS API password seems insecure (%i). " \
                "Refer to the HASS configurator logs for further information." % problems,
                "notification_id": "HC_HASS_API_PASSWORD"
            }
            notify(**data)

        problems = None
        if SESAME:
            problems = password_problems(SESAME, "SESAME")
        if problems:
            data = {
                "title": "HASS Configurator - Password warning",
                "message": "Your SESAME seems insecure (%i). " \
                "Refer to the HASS configurator logs for further information." % problems,
                "notification_id": "HC_SESAME"
            }
            notify(**data)

        problems = None
        if PASSWORD:
            problems = password_problems(PASSWORD, "PASSWORD")
        if problems:
            data = {
                "title": "HASS Configurator - Password warning",
                "message": "Your PASSWORD seems insecure (%i). " \
                "Refer to the HASS configurator logs for further information." % problems,
                "notification_id": "HC_PASSWORD"
            }
            notify(**data)
    except Exception as err:
        LOG.warning("Exception while checking passwords: %s", err)

    custom_server = SimpleServer
    if ':' in LISTENIP:
        custom_server.address_family = socket.AF_INET6
    server_address = (LISTENIP, PORT)
    if USERNAME and PASSWORD:
        handler = AuthHandler
    else:
        handler = RequestHandler
    HTTPD = custom_server(server_address, handler)
    if SSL_CERTIFICATE:
        HTTPD.socket = ssl.wrap_socket(HTTPD.socket,
                                       certfile=SSL_CERTIFICATE,
                                       keyfile=SSL_KEY,
                                       server_side=True)
    LOG.info('Listening on: %s://%s:%i',
             'https' if SSL_CERTIFICATE else 'http',
             HTTPD.server_address[0], HTTPD.server_address[1])
    if BASEPATH:
        os.chdir(BASEPATH)
    HTTPD.serve_forever()

if __name__ == "__main__":
    main()
