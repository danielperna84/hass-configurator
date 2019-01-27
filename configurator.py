#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""
Configurator for Home Assistant.
https://github.com/danielperna84/hass-configurator
"""
import os
import sys
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
VERSION = "0.3.4"
BASEDIR = "."
DEV = False
LISTENPORT = None
TOTP = None
HTTPD = None
FAIL2BAN_IPS = {}
REPO = None

INDEX = Template(r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1.0" />
    <title>HASS Configurator</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/MaterialDesign-Webfont/3.3.92/css/materialdesignicons.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.100.2/css/materialize.min.css">
    <style type="text/css" media="screen">
        body {
            margin: 0;
            padding: 0;
            background-color: #fafafa;
            display: flex;
            min-height: 100vh;
            flex-direction: column;
        }

        main {
            flex: 1 0 auto;
        }

        #editor {
            position: fixed;
            top: 135px;
            right: 0;
            bottom: 0;
        }

        @media only screen and (max-width: 600px) {
          #editor {
              top: 125px;
          }
          .toolbar_mobile {
              margin-bottom: 0;
          }
        }

        .leftellipsis {
            overflow: hidden;
            direction: rtl;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .select-wrapper input.select-dropdown {
            width: 96%;
            overflow: hidden;
            direction: ltr;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        #edit_float {
              z-index: 10;
        }

        #filebrowser {
            background-color: #fff;
        }

        #fbheader {
            display: block;
            cursor: initial;
            pointer-events: none;
            color: #424242 !important;
            font-weight: 400;
            font-size: .9em;
            min-height: 64px;
            padding-top: 8px;
            margin-left: -5px;
            max-width: 250px;
        }

        #fbheaderbranch {
            padding: 5px 10px !important;
            display: none;
            color: #757575 !important;
        }

        #branchselector {
            font-weight: 400;
        }

        a.branch_select.active {
            color: white !important;
        }

        #fbelements {
            margin: 0;
            position: relative;
        }

        a.collection-item {
            color: #616161 !important;
        }

        .fbtoolbarbutton {
            color: #757575 !important;
            min-height: 64px !important;
        }

        .fbmenubutton {
            color: #616161 !important;
            display: inline-block;
            float: right;
            min-height: 64px;
            padding-top: 8px !important;
            padding-left: 20px !important;
        }

        .filename {
            color: #616161 !important;
            font-weight: 400;
            display: inline-block;
            width: 182px;
            white-space: nowrap;
            text-overflow: ellipsis;
            cursor: pointer;
        }

        .nowrap {
            white-space: nowrap;
        }

        .text_darkgreen {
            color: #1b5e20 !important;
        }

        .text_darkred {
            color: #b71c1c !important;
        }

        span.stats {
            margin: -10px 0 0 0;
            padding: 0;
            font-size: 0.5em;
            color: #616161 !important;
            line-height: 16px;
            display: inherit;
        }

        .collection-item #uplink {
            background-color: #f5f5f5;
            width: 323px !important;
            margin-left: -3px !important;
        }

        input.currentfile_input {
            margin-bottom: 0;
            margin-top: 0;
            padding-left: 5px;
            border-bottom: 0;
        }

        .side_tools {
            vertical-align: middle;
        }

        .fbtoolbarbutton_icon {
            margin-top: 20px;
        }

        .collection {
            margin: 0;
            background-color: #fff;
        }

        li.collection-item {
            border-bottom: 1px solid #eeeeee !important;
        }

        .side-nav {
            width: 337px !important;
            height: 100% !important;
        }

        .fb_side-nav li {
            line-height: 36px;
        }

        .fb_side-nav a {
          padding: 0 0 0 16px;
          display: inline-block !important;
        }

        .fb_side-nav li>a>i {
            margin-right: 16px !important;
            cursor: pointer;
        }

        .green {
            color: #fff;
        }

        .red {
            color: #fff;
        }

        #dropdown_menu, #dropdown_menu_mobile {
            min-width: 235px;
        }

        #dropdown_gitmenu {
            min-width: 140px !important;
        }

        .dropdown-content li>a,
        .dropdown-content li>span {
            color: #616161 !important;
        }

        .fb_dd {
            margin-left: -15px !important;
        }

        .blue_check:checked+label:before {
            border-right: 2px solid #03a9f4;
            border-bottom: 2px solid #03a9f4;
        }

        .input-field input:focus+label {
            color: #03a9f4 !important;
        }

        .input-field input[type=text].valid {
            border-bottom: 1px solid #03a9f4 !important;
            box-shadow: 0 1px 0 0 #03a9f4 !important;
        }

        .input-field input[type=text]:focus {
            border-bottom: 1px solid #03a9f4 !important;
            box-shadow: 0 1px 0 0 #03a9f4 !important;
        }

        .input-field input:focus+label {
            color: #03a9f4 !important;
        }

        .input-field input[type=password].valid {
            border-bottom: 1px solid #03a9f4 !important;
            box-shadow: 0 1px 0 0 #03a9f4 !important;
        }

        .input-field input[type=password]:focus {
            border-bottom: 1px solid #03a9f4 !important;
            box-shadow: 0 1px 0 0 #03a9f4 !important;
        }

        .input-field textarea:focus+label {
            color: #03a9f4 !important;
        }

        .input-field textarea:focus {
            border-bottom: 1px solid #03a9f4 !important;
            box-shadow: 0 1px 0 0 #03a9f4 !important;
        }

        #modal_acekeyboard {
            top: auto;
            width: 96%;
            min-height: 96%;
            border-radius: 0;
            margin: auto;
        }

        .modal .modal-content_nopad {
            padding: 0;
        }

        .waves-effect.waves-blue .waves-ripple {
            background-color: #03a9f4;
        }

        .preloader-background {
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #eee;
            position: fixed;
            z-index: 10000;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }

        .modal-content_nopad {
            position: relative;
        }

        .modal-content_nopad .modal_btn {
            position: absolute;
            top: 2px;
            right:0;
        }

        footer {
            z-index: 10;
        }

        .shadow {
            height: 25px;
            margin: -26px;
            min-width: 320px;
            background-color: transparent;
        }

        .ace_optionsMenuEntry input {
            position: relative !important;
            left: 0 !important;
            opacity: 1 !important;
        }

        .ace_optionsMenuEntry select {
            position: relative !important;
            left: 0 !important;
            opacity: 1 !important;
            display: block !important;
        }

        .ace_search {
            background-color: #eeeeee !important;
            border-radius: 0 !important;
            border: 0 !important;
            box-shadow: 0 6px 10px 0 rgba(0, 0, 0, 0.14), 0 1px 18px 0 rgba(0, 0, 0, 0.12), 0 3px 5px -1px rgba(0, 0, 0, 0.3);
        }

        .ace_search_form {
            background-color: #fafafa;
            width: 300px;
            border: 0 !important;
            border-radius: 0 !important;
            outline: none !important;
            box-shadow: 0 2px 2px 0 rgba(0, 0, 0, 0.14), 0 1px 5px 0 rgba(0, 0, 0, 0.12), 0 2px 1px -2px rgba(0, 0, 0, 0.2);
            margin-bottom: 15px !important;
            margin-left: 8px !important;
            color: #424242 !important;
        }

        .ace_search_field {
            padding-left: 4px !important;
            margin-left: 10px !important;
            max-width: 275px !important;
            font-family: 'Roboto', sans-serif !important;
            border-bottom: 1px solid #03a9f4 !important;
            color: #424242 !important;
        }

        .ace_replace_form {
            background-color: #fafafa;
            width: 300px;
            border: 0 !important;
            border-radius: 0 !important;
            outline: none !important;
            box-shadow: 0 2px 2px 0 rgba(0, 0, 0, 0.14), 0 1px 5px 0 rgba(0, 0, 0, 0.12), 0 2px 1px -2px rgba(0, 0, 0, 0.2);
            margin-bottom: 15px !important;
            margin-left: 8px !important;
        }

        .ace_search_options {
            background-color: #eeeeee;
            text-align: left !important;
            letter-spacing: .5px !important;
            transition: .2s ease-out;
            font-family: 'Roboto', sans-serif !important;
            font-size: 130%;
            top: 0 !important;
        }

        .ace_searchbtn {
            text-decoration: none !important;
            min-width: 40px !important;
            min-height: 30px !important;
            color: #424242 !important;
            text-align: center !important;
            letter-spacing: .5px !important;
            transition: .2s ease-out;
            cursor: pointer;
            font-family: 'Roboto', sans-serif !important;
        }

        .ace_searchbtn:hover {
            background-color: #03a9f4;
        }

        .ace_replacebtn {
            text-decoration: none !important;
            min-width: 40px !important;
            min-height: 30px !important;
            color: #424242 !important;
            text-align: center !important;
            letter-spacing: .5px !important;
            transition: .2s ease-out;
            cursor: pointer;
            font-family: 'Roboto', sans-serif !important;
        }

        .ace_replacebtn:hover {
            background-color: #03a9f4;
        }

        .ace_button {
            text-decoration: none !important;
            min-width: 40px !important;
            min-height: 30px !important;
            border-radius: 0 !important;
            outline: none !important;
            color: #424242 !important;
            background-color: #fafafa;
            text-align: center;
            letter-spacing: .5px;
            transition: .2s ease-out;
            cursor: pointer;
            font-family: 'Roboto', sans-serif !important;
        }

        .ace_button:hover {
            background-color: #03a9f4 !important;
        }

        .ace_invisible {
            color: rgba(191, 191, 191, 0.5) !important;
        }

        .fbicon_pad {
            min-height: 64px !important;
        }

        .fbmenuicon_pad {
            min-height: 64px;
            margin-top: 6px !important;
            margin-right: 18px !important;
            color: #616161 !important;
        }

        .no-padding {
            padding: 0 !important;
        }

        .branch_select {
            min-width: 300px !important;
            font-size: 14px !important;
            font-weight: 400 !important;
        }

        a.branch_hover:hover {
            background-color: #e0e0e0 !important;
        }

        .hidesave {
            opacity: 0;
            -webkit-transition: all 0.5s ease-in-out;
            -moz-transition: all 0.5s ease-in-out;
            -ms-transition: all 0.5s ease-in-out;
            -o-transition: all 0.5s ease-in-out;
            transition: all 0.5s ease-in-out;
        }

        .pathtip_color {
            -webkit-animation: fadeinout 1.75s linear 1 forwards;
            animation: fadeinout 1.75s linear 1 forwards;
        }

        @-webkit-keyframes fadeinout {
            0% { background-color: #f5f5f5; }
            50% { background-color: #ff8a80; }
            100% { background-color: #f5f5f5; }
        }
        @keyframes fadeinout {
            0% { background-color: #f5f5f5; }
            50% { background-color: #ff8a80; }
            100% { background-color: #f5f5f5; }
        }

        #lint-status {
            position: absolute;
            top: 0.75rem;
            right: 10px;
        }

        .cursor-pointer {
            cursor: pointer;
        }

        #modal_lint.modal {
            width: 80%;
        }

        #modal_lint textarea {
            resize: none;
            height: auto;
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.2/ace.js" type="text/javascript" charset="utf-8"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.2/ext-modelist.js" type="text/javascript" charset="utf-8"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.4.2/ext-language_tools.js" type="text/javascript" charset="utf-8"></script>
</head>
<body>
  <div class="preloader-background">
    <div class="preloader-wrapper big active">
      <div class="spinner-layer spinner-blue">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div>
        <div class="gap-patch">
          <div class="circle"></div>
        </div>
        <div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
      <div class="spinner-layer spinner-red">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div>
        <div class="gap-patch">
          <div class="circle"></div>
        </div>
        <div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
      <div class="spinner-layer spinner-yellow">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div>
        <div class="gap-patch">
          <div class="circle"></div>
        </div>
        <div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
      <div class="spinner-layer spinner-green">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div>
        <div class="gap-patch">
          <div class="circle"></div>
        </div>
        <div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
    </div>
  </div>
  <header>
    <div class="navbar-fixed">
        <nav class="light-blue">
            <div class="nav-wrapper">
                <ul class="left">
                    <li><a class="waves-effect waves-light tooltipped files-collapse hide-on-small-only" data-activates="slide-out" data-position="bottom" data-delay="500" data-tooltip="Browse Filesystem" style="padding-left: 25px; padding-right: 25px;"><i class="material-icons">folder</i></a></li>
                    <li><a class="waves-effect waves-light files-collapse hide-on-med-and-up" data-activates="slide-out" style="padding-left: 25px; padding-right: 25px;"><i class="material-icons">folder</i></a></li>
                </ul>
                <ul class="right">
                    <li><a class="waves-effect waves-light tooltipped hide-on-small-only markdirty hidesave" data-position="bottom" data-delay="500" data-tooltip="Save" onclick="save_check()"><i class="material-icons">save</i></a></li>
                    <li><a class="waves-effect waves-light tooltipped hide-on-small-only modal-trigger" data-position="bottom" data-delay="500" data-tooltip="Close" href="#modal_close"><i class="material-icons">close</i></a></li>
                    <li><a class="waves-effect waves-light tooltipped hide-on-small-only" data-position="bottom" data-delay="500" data-tooltip="Search" onclick="editor.execCommand('replace')"><i class="material-icons">search</i></a></li>
                    <li><a class="waves-effect waves-light dropdown-button hide-on-small-only $versionclass" data-activates="dropdown_menu" data-beloworigin="true"><i class="material-icons right">settings</i></a></li>
                    <li><a class="waves-effect waves-light hide-on-med-and-up markdirty hidesave" onclick="save_check()"><i class="material-icons">save</i></a></li>
                    <li><a class="waves-effect waves-light hide-on-med-and-up modal-trigger" href="#modal_close"><i class="material-icons">close</i></a></li>
                    <li><a class="waves-effect waves-light hide-on-med-and-up" onclick="editor.execCommand('replace')"><i class="material-icons">search</i></a></li>
                    <li><a class="waves-effect waves-light dropdown-button hide-on-med-and-up $versionclass" data-activates="dropdown_menu_mobile" data-beloworigin="true"><i class="material-icons right">settings</i></a></li>
                </ul>
            </div>
        </nav>
    </div>
  </header>
  <main>
    <ul id="dropdown_menu" class="dropdown-content z-depth-4">
        <li><a onclick="localStorage.setItem('new_tab', true);window.open(window.location.origin+window.location.pathname, '_blank');">New tab</a></li>
        <li class="divider"></li>
        <li><a target="_blank" href="https://home-assistant.io/components/">Components</a></li>
        <li><a target="_blank" href="https://materialdesignicons.com/">Material Icons</a></li>
        <li><a href="#" data-activates="ace_settings" class="ace_settings-collapse">Editor Settings</a></li>
        <li><a class="modal-trigger" href="#modal_netstat" onclick="get_netstat()">Network status</a></li>
        <li><a class="modal-trigger" href="#modal_about">About HASS-Configurator</a></li>
        <li class="divider"></li>
        <!--<li><a href="#modal_check_config">Check HASS Configuration</a></li>-->
        <li><a class="modal-trigger" href="#modal_events">Observe events</a></li>
        <li><a class="modal-trigger" href="#modal_reload_automations">Reload automations</a></li>
        <li><a class="modal-trigger" href="#modal_reload_scripts">Reload scripts</a></li>
        <li><a class="modal-trigger" href="#modal_reload_groups">Reload groups</a></li>
        <li><a class="modal-trigger" href="#modal_reload_core">Reload core</a></li>
        <li><a class="modal-trigger" href="#modal_restart">Restart HASS</a></li>
        <li class="divider"></li>
        <li><a class="modal-trigger" href="#modal_exec_command">Execute shell command</a></li>
    </ul>
    <ul id="dropdown_menu_mobile" class="dropdown-content z-depth-4">
        <li><a onclick="localStorage.setItem('new_tab', true);window.open(window.location.origin+window.location.pathname, '_blank');">New tab</a></li>
        <li class="divider"></li>
        <li><a target="_blank" href="https://home-assistant.io/help/">Help</a></li>
        <li><a target="_blank" href="https://home-assistant.io/components/">Components</a></li>
        <li><a target="_blank" href="https://materialdesignicons.com/">Material Icons</a></li>
        <li><a href="#" data-activates="ace_settings" class="ace_settings-collapse">Editor Settings</a></li>
        <li><a class="modal-trigger" href="#modal_netstat" onclick="get_netstat()">Network status</a></li>
        <li><a class="modal-trigger" href="#modal_about">About HASS-Configurator</a></li>
        <li class="divider"></li>
        <!--<li><a href="#modal_check_config">Check HASS Configuration</a></li>-->
        <li><a class="modal-trigger" href="#modal_events">Observe events</a></li>
        <li><a class="modal-trigger" href="#modal_reload_automations">Reload automations</a></li>
        <li><a class="modal-trigger" href="#modal_reload_scripts">Reload scripts</a></li>
        <li><a class="modal-trigger" href="#modal_reload_groups">Reload groups</a></li>
        <li><a class="modal-trigger" href="#modal_reload_core">Reload core</a></li>
        <li><a class="modal-trigger" href="#modal_restart">Restart HASS</a></li>
        <li class="divider"></li>
        <li><a class="modal-trigger" href="#modal_exec_command">Execute shell command</a></li>
    </ul>
    <ul id="dropdown_gitmenu" class="dropdown-content z-depth-4">
        <li><a class="modal-trigger" href="#modal_init" class="nowrap waves-effect">git init</a></li>
        <li><a class="modal-trigger" href="#modal_commit" class="nowrap waves-effect">git commit</a></li>
        <li><a class="modal-trigger" href="#modal_push" class="nowrap waves-effect">git push</a></li>
        <li><a class="modal-trigger" href="#modal_stash" class="nowrap waves-effect">git stash</a></li>
    </ul>
    <ul id="dropdown_gitmenu_mobile" class="dropdown-content z-depth-4">
        <li><a class="modal-trigger" href="#modal_init" class="nowrap waves-effect">git init</a></li>
        <li><a class="modal-trigger" href="#modal_commit" class="nowrap waves-effect">git commit</a></li>
        <li><a class="modal-trigger" href="#modal_push" class="nowrap waves-effect">git push</a></li>
        <li><a class="modal-trigger" href="#modal_stash" class="nowrap waves-effect">git stash</a></li>
    </ul>
    <div id="modal_acekeyboard" class="modal bottom-sheet modal-fixed-footer">
        <div class="modal-content centered">
        <h4 class="grey-text text-darken-3">Ace Keyboard Shortcuts<i class="mdi mdi-keyboard right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
        <br>
        <ul class="collapsible popout" data-collapsible="expandable">
          <li>
            <div class="collapsible-header"><i class="material-icons">view_headline</i>Line Operations</div>
            <div class="collapsible-body">
              <table class="bordered highlight centered">
                <thead>
                  <tr>
                    <th>Windows/Linux</th>
                    <th>Mac</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Ctrl-D</td>
                    <td>Command-D</td>
                    <td>Remove line</td>
                  </tr>
                  <tr>
                    <td>Alt-Shift-Down</td>
                    <td>Command-Option-Down</td>
                    <td>Copy lines down</td>
                  </tr>
                  <tr>
                    <td>Alt-Shift-Up</td>
                    <td>Command-Option-Up</td>
                    <td>Copy lines up</td>
                  </tr>
                  <tr>
                    <td>Alt-Down</td>
                    <td>Option-Down</td>
                    <td>Move lines down</td>
                  </tr>
                  <tr>
                    <td>Alt-Up</td>
                    <td>Option-Up</td>
                    <td>Move lines up</td>
                  </tr>
                  <tr>
                    <td>Alt-Delete</td>
                    <td>Ctrl-K</td>
                    <td>Remove to line end</td>
                  </tr>
                  <tr>
                    <td>Alt-Backspace</td>
                    <td>Command-Backspace</td>
                    <td>Remove to linestart</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Backspace</td>
                    <td>Option-Backspace, Ctrl-Option-Backspace</td>
                    <td>Remove word left</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Delete</td>
                    <td>Option-Delete</td>
                    <td>Remove word right</td>
                  </tr>
                  <tr>
                    <td>---</td>
                    <td>Ctrl-O</td>
                    <td>Split line</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </li>
          <li>
            <div class="collapsible-header"><i class="material-icons">photo_size_select_small</i>Selection</div>
            <div class="collapsible-body">
              <table class="bordered highlight centered">
                <thead>
                  <tr>
                    <th >Windows/Linux</th>
                    <th >Mac</th>
                    <th >Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td >Ctrl-A</td>
                    <td >Command-A</td>
                    <td >Select all</td>
                  </tr>
                  <tr>
                    <td >Shift-Left</td>
                    <td >Shift-Left</td>
                    <td >Select left</td>
                  </tr>
                  <tr>
                    <td >Shift-Right</td>
                    <td >Shift-Right</td>
                    <td >Select right</td>
                  </tr>
                  <tr>
                    <td >Ctrl-Shift-Left</td>
                    <td >Option-Shift-Left</td>
                    <td >Select word left</td>
                  </tr>
                  <tr>
                    <td >Ctrl-Shift-Right</td>
                    <td >Option-Shift-Right</td>
                    <td >Select word right</td>
                  </tr>
                  <tr>
                    <td >Shift-Home</td>
                    <td >Shift-Home</td>
                    <td >Select line start</td>
                  </tr>
                  <tr>
                    <td >Shift-End</td>
                    <td >Shift-End</td>
                    <td >Select line end</td>
                  </tr>
                  <tr>
                    <td >Alt-Shift-Right</td>
                    <td >Command-Shift-Right</td>
                    <td >Select to line end</td>
                  </tr>
                  <tr>
                    <td >Alt-Shift-Left</td>
                    <td >Command-Shift-Left</td>
                    <td >Select to line start</td>
                  </tr>
                  <tr>
                    <td >Shift-Up</td>
                    <td >Shift-Up</td>
                    <td >Select up</td>
                  </tr>
                  <tr>
                    <td >Shift-Down</td>
                    <td >Shift-Down</td>
                    <td >Select down</td>
                  </tr>
                  <tr>
                    <td >Shift-PageUp</td>
                    <td >Shift-PageUp</td>
                    <td >Select page up</td>
                  </tr>
                  <tr>
                    <td >Shift-PageDown</td>
                    <td >Shift-PageDown</td>
                    <td >Select page down</td>
                  </tr>
                  <tr>
                    <td >Ctrl-Shift-Home</td>
                    <td >Command-Shift-Up</td>
                    <td >Select to start</td>
                  </tr>
                  <tr>
                    <td >Ctrl-Shift-End</td>
                    <td >Command-Shift-Down</td>
                    <td >Select to end</td>
                  </tr>
                  <tr>
                    <td >Ctrl-Shift-D</td>
                    <td >Command-Shift-D</td>
                    <td >Duplicate selection</td>
                  </tr>
                  <tr>
                    <td >Ctrl-Shift-P</td>
                    <td >---</td>
                    <td >Select to matching bracket</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </li>
          <li>
            <div class="collapsible-header"><i class="material-icons">multiline_chart</i>Multicursor</div>
            <div class="collapsible-body">
              <table class="bordered highlight centered">
                <thead>
                  <tr>
                    <th>Windows/Linux</th>
                    <th>Mac</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Ctrl-Alt-Up</td>
                    <td>Ctrl-Option-Up</td>
                    <td>Add multi-cursor above</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-Down</td>
                    <td>Ctrl-Option-Down</td>
                    <td>Add multi-cursor below</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-Right</td>
                    <td>Ctrl-Option-Right</td>
                    <td>Add next occurrence to multi-selection</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-Left</td>
                    <td>Ctrl-Option-Left</td>
                    <td>Add previous occurrence to multi-selection</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-Shift-Up</td>
                    <td>Ctrl-Option-Shift-Up</td>
                    <td>Move multicursor from current line to the line above</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-Shift-Down</td>
                    <td>Ctrl-Option-Shift-Down</td>
                    <td>Move multicursor from current line to the line below</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-Shift-Right</td>
                    <td>Ctrl-Option-Shift-Right</td>
                    <td>Remove current occurrence from multi-selection and move to next</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-Shift-Left</td>
                    <td>Ctrl-Option-Shift-Left</td>
                    <td>Remove current occurrence from multi-selection and move to previous</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Shift-L</td>
                    <td>Ctrl-Shift-L</td>
                    <td>Select all from multi-selection</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </li>
          <li>
            <div class="collapsible-header"><i class="material-icons">call_missed_outgoing</i>Go To</div>
            <div class="collapsible-body">
              <table class="bordered highlight centered">
                <thead>
                  <tr>
                    <th>Windows/Linux</th>
                    <th>Mac</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Left</td>
                    <td>Left, Ctrl-B</td>
                    <td>Go to left</td>
                  </tr>
                  <tr>
                    <td>Right</td>
                    <td>Right, Ctrl-F</td>
                    <td>Go to right</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Left</td>
                    <td>Option-Left</td>
                    <td>Go to word left</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Right</td>
                    <td>Option-Right</td>
                    <td>Go to word right</td>
                  </tr>
                  <tr>
                    <td>Up</td>
                    <td>Up, Ctrl-P</td>
                    <td>Go line up</td>
                  </tr>
                  <tr>
                    <td>Down</td>
                    <td>Down, Ctrl-N</td>
                    <td>Go line down</td>
                  </tr>
                  <tr>
                    <td>Alt-Left, Home</td>
                    <td>Command-Left, Home, Ctrl-A</td>
                    <td>Go to line start</td>
                  </tr>
                  <tr>
                    <td>Alt-Right, End</td>
                    <td>Command-Right, End, Ctrl-E</td>
                    <td>Go to line end</td>
                  </tr>
                  <tr>
                    <td>PageUp</td>
                    <td>Option-PageUp</td>
                    <td>Go to page up</td>
                  </tr>
                  <tr>
                    <td>PageDown</td>
                    <td>Option-PageDown, Ctrl-V</td>
                    <td>Go to page down</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Home</td>
                    <td>Command-Home, Command-Up</td>
                    <td>Go to start</td>
                  </tr>
                  <tr>
                    <td>Ctrl-End</td>
                    <td>Command-End, Command-Down</td>
                    <td>Go to end</td>
                  </tr>
                  <tr>
                    <td>Ctrl-L</td>
                    <td>Command-L</td>
                    <td>Go to line</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Down</td>
                    <td>Command-Down</td>
                    <td>Scroll line down</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Up</td>
                    <td>---</td>
                    <td>Scroll line up</td>
                  </tr>
                  <tr>
                    <td>Ctrl-P</td>
                    <td>---</td>
                    <td>Go to matching bracket</td>
                  </tr>
                  <tr>
                    <td>---</td>
                    <td>Option-PageDown</td>
                    <td>Scroll page down</td>
                  </tr>
                  <tr>
                    <td>---</td>
                    <td>Option-PageUp</td>
                    <td>Scroll page up</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </li>
          <li>
            <div class="collapsible-header"><i class="material-icons">find_replace</i>Find/Replace</div>
            <div class="collapsible-body">
              <table class="bordered highlight centered">
                <thead>
                  <tr>
                    <th>Windows/Linux</th>
                    <th>Mac</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Ctrl-F</td>
                    <td>Command-F</td>
                    <td>Find</td>
                  </tr>
                  <tr>
                    <td>Ctrl-H</td>
                    <td>Command-Option-F</td>
                    <td>Replace</td>
                  </tr>
                  <tr>
                    <td>Ctrl-K</td>
                    <td>Command-G</td>
                    <td>Find next</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Shift-K</td>
                    <td>Command-Shift-G</td>
                    <td>Find previous</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </li>
          <li>
            <div class="collapsible-header"><i class="material-icons">all_out</i>Folding</div>
            <div class="collapsible-body">
              <table class="bordered highlight centered">
                <thead>
                  <tr>
                    <th>Windows/Linux</th>
                    <th>Mac</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Alt-L, Ctrl-F1</td>
                    <td>Command-Option-L, Command-F1</td>
                    <td>Fold selection</td>
                  </tr>
                  <tr>
                    <td>Alt-Shift-L, Ctrl-Shift-F1</td>
                    <td>Command-Option-Shift-L, Command-Shift-F1</td>
                    <td>Unfold</td>
                  </tr>
                  <tr>
                    <td>Alt-0</td>
                    <td>Command-Option-0</td>
                    <td>Fold all</td>
                  </tr>
                  <tr>
                    <td>Alt-Shift-0</td>
                    <td>Command-Option-Shift-0</td>
                    <td>Unfold all</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </li>
          <li>
            <div class="collapsible-header"><i class="material-icons">devices_other</i>Other</div>
            <div class="collapsible-body">
              <table class="bordered highlight centered">
                <thead>
                  <tr>
                    <th>Windows/Linux</th>
                    <th>Mac</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Tab</td>
                    <td>Tab</td>
                    <td>Indent</td>
                  </tr>
                  <tr>
                    <td>Shift-Tab</td>
                    <td>Shift-Tab</td>
                    <td>Outdent</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Z</td>
                    <td>Command-Z</td>
                    <td>Undo</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Shift-Z, Ctrl-Y</td>
                    <td>Command-Shift-Z, Command-Y</td>
                    <td>Redo</td>
                  </tr>
                  <tr>
                    <td>Ctrl-,</td>
                    <td>Command-,</td>
                    <td>Show the settings menu</td>
                  </tr>
                  <tr>
                    <td>Ctrl-/</td>
                    <td>Command-/</td>
                    <td>Toggle comment</td>
                  </tr>
                  <tr>
                    <td>Ctrl-T</td>
                    <td>Ctrl-T</td>
                    <td>Transpose letters</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Enter</td>
                    <td>Command-Enter</td>
                    <td>Enter full screen</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Shift-U</td>
                    <td>Ctrl-Shift-U</td>
                    <td>Change to lower case</td>
                  </tr>
                  <tr>
                    <td>Ctrl-U</td>
                    <td>Ctrl-U</td>
                    <td>Change to upper case</td>
                  </tr>
                  <tr>
                    <td>Insert</td>
                    <td>Insert</td>
                    <td>Overwrite</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Shift-E</td>
                    <td>Command-Shift-E</td>
                    <td>Macros replay</td>
                  </tr>
                  <tr>
                    <td>Ctrl-Alt-E</td>
                    <td>---</td>
                    <td>Macros recording</td>
                  </tr>
                  <tr>
                    <td>Delete</td>
                    <td>---</td>
                    <td>Delete</td>
                  </tr>
                  <tr>
                    <td>---</td>
                    <td>Ctrl-L</td>
                    <td>Center selection</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </li>
        </ul>
      </div>
      <div class="modal-footer">
        <a class="modal-action modal-close waves-effect btn-flat light-blue-text">Close</a>
      </div>
    </div>
    <div id="modal_events" class="modal modal-fixed-footer">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Event Observer<i class="grey-text text-darken-3 material-icons right" style="font-size: 2rem;">error_outline</i></h4>
            <br />
            <div class="row">
                <form class="col s12">
                    <div class="row">
                        <div class="input-field col s12">
                            <input type="text" id="ws_uri" placeholder="ws://127.0.0.1:8123/api/websocket" value="$hass_ws_address"/>
                            <label for="ws_uri">Websocket URI</label>
                        </div>
                    </div>
                    <div class="row">
                        <div class="input-field col s12">
                            <input type="password" id="ws_password" value="$api_password"/>
                            <label for="ws_password">API password</label>
                        </div>
                    </div>
                    <div class="row">
                        <div class="input-field col s12">
                            <textarea id="ws_events" class="materialize-textarea"></textarea>
                        </div>
                    </div>
                </form>
            </div>
        </div>
        <div class="modal-footer">
          <a onclick="ws_connect()" id="ws_b_c" class="modal-action waves-effect waves-green btn-flat light-blue-text">Connect</a>
          <a onclick="ws_disconnect()" id="ws_b_d" class="modal-action waves-effect waves-green btn-flat light-blue-text disabled">Disconnect</a>
          <a onclick="ws_disconnect()" class="modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Close</a>
        </div>
    </div>
    <div id="modal_save" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Save<i class="grey-text text-darken-3 material-icons right" style="font-size: 2rem;">save</i></h4>
            <p>Do you really want to save?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="save()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_upload" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Upload File<i class="grey-text text-darken-3 material-icons right" style="font-size: 2.28rem;">file_upload</i></h4>
            <p>Please choose a file to upload</p>
            <form action="#" id="uploadform">
              <div class="file-field input-field">
                <div class="btn light-blue waves-effect">
                  <span>File</span>
                  <input type="file" id="uploadfile" />
                </div>
                <div class="file-path-wrapper">
                  <input class="file-path validate" type="text">
                </div>
              </div>
            </form>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="upload()" class="modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_init" class="modal">
        <div class="modal-content">
          <h4 class="grey-text text-darken-3">git init<i class="mdi mdi-git right grey-text text-darken-3" style="font-size: 2.48rem;"></i></h4>
          <p>Are you sure you want to initialize a repository at the current path?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="gitinit()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_commit" class="modal">
        <div class="modal-content">
          <h4 class="grey-text text-darken-3">git commit<i class="mdi mdi-git right grey-text text-darken-3" style="font-size: 2.48rem;"></i></h4>
          <div class="row">
            <div class="input-field col s12">
              <input type="text" id="commitmessage">
              <label class="active" for="commitmessage">Commit message</label>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="commit(document.getElementById('commitmessage').value)" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_push" class="modal">
        <div class="modal-content">
          <h4 class="grey-text text-darken-3">git push<i class="mdi mdi-git right grey-text text-darken-3" style="font-size: 2.48rem;"></i></h4>
          <p>Are you sure you want to push your commited changes to the configured remote / origin?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="gitpush()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_stash" class="modal">
        <div class="modal-content">
          <h4 class="grey-text text-darken-3">git stash<i class="mdi mdi-git right grey-text text-darken-3" style="font-size: 2.48rem;"></i></h4>
          <p>Are you sure you want to stash your changes?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="gitstash()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_close" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Close File<i class="grey-text text-darken-3 material-icons right" style="font-size: 2.28rem;">close</i></h4>
            <p>Are you sure you want to close the current file? Unsaved changes will be lost.</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="closefile()" class="modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_delete" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Delete</h4>
            <p>Are you sure you want to delete <span class="fb_currentfile"></span>?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="delete_element()" class="modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_gitadd" class="modal">
        <div class="modal-content">
          <h4 class="grey-text text-darken-3">git add<i class="mdi mdi-git right grey-text text-darken-3" style="font-size: 2.48rem;"></i></h4>
          <p>Are you sure you want to add <span class="fb_currentfile"></span> to the index?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="gitadd()" class="modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_check_config" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Check configuration<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you want to check the configuration?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="check_config()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_reload_automations" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Reload automations<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you want to reload the automations?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="reload_automations()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_reload_scripts" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Reload scripts<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you want to reload the scripts?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="reload_scripts()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_reload_groups" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Reload groups<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you want to reload the groups?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="reload_groups()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_reload_core" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Reload core<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you want to reload the core?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="reload_core()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_restart" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Restart<i class="mdi mdi-restart right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you really want to restart Home Assistant?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="restart()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_a_net_remove" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Remove allowed network / IP<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you really want to remove the network / IP <b><span id="removenet"></span></b> from the list of allowed networks?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="a_net_remove()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_a_net_add" class="modal">
            <div class="modal-content">
                <h4 class="grey-text text-darken-3">Add allowed network / IP<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
                <p>Do you really want to Add the network / IP <b><span id="addnet"></span></b> to the list of allowed networks?</p>
            </div>
            <div class="modal-footer">
              <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
              <a onclick="a_net_add()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
            </div>
        </div>
    <div id="modal_unban" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Unban IP<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <p>Do you really want to unban the IP <b><span id="unbanip"></span></b>?</p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
          <a onclick="banned_unban()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
        </div>
    </div>
    <div id="modal_ban" class="modal">
            <div class="modal-content">
                <h4 class="grey-text text-darken-3">Ban IP<i class="mdi mdi-settings right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
                <p>Do you really want to ban the IP <b><span id="banip"></span></b>?</p>
            </div>
            <div class="modal-footer">
              <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">No</a>
              <a onclick="banned_ban()" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Yes</a>
            </div>
        </div>
    <div id="modal_exec_command" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Execute shell command<i class="mdi mdi-laptop right grey-text text-darken-3" style="font-size: 2rem;"></i></h4>
            <pre class="col s6" id="command_history"></pre>
            <br>
            <div class="row">
                <div class="input-field col s12">
                  <input placeholder="/bin/ls -l /var/log" id="commandline" type="text">
                  <label for="commandline">Command</label>
                </div>
          </div>
        </div>
        <div class="modal-footer">
            <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Close</a>
            <a onclick="document.getElementById('command_history').innerText='';" class=" modal-action waves-effect waves-green btn-flat light-blue-text">Clear</a>
            <a onclick="exec_command()" class=" modal-action waves-effect waves-green btn-flat light-blue-text">Execute</a>
        </div>
    </div>
    <div id="modal_markdirty" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Unsaved Changes<i class="grey-text text-darken-3 material-icons right" style="font-size: 2rem;">save</i></h4>
            <p>You have unsaved changes in the current file. Please save the changes or close the file before opening a new one.</p>
        </div>
        <div class="modal-footer">
          <a class="modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Abort</a>
          <a onclick="document.getElementById('currentfile').value='';editor.getSession().setValue('');$('.markdirty').each(function(i, o){o.classList.remove('red');});" class="modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Close file</a>
          <a onclick="save()" class="modal-action modal-close waves-effect waves-green btn-flat light-blue-text">Save changes</a>
        </div>
    </div>
    <div id="modal_newfolder" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">New Folder<i class="grey-text text-darken-3 material-icons right" style="font-size: 2rem;">create_new_folder</i></h4>
            <br>
            <div class="row">
                <div class="input-field col s12">
                    <input type="text" id="newfoldername">
                    <label class="active" for="newfoldername">New Folder Name</label>
                </div>
          </div>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="newfolder(document.getElementById('newfoldername').value)" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_newfile" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">New File<i class="grey-text text-darken-3 material-icons right" style="font-size: 2rem;">note_add</i></h4>
            <br>
            <div class="row">
                <div class="input-field col s12">
                    <input type="text" id="newfilename">
                    <label class="active" for="newfilename">New File Name</label>
                </div>
          </div>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="newfile(document.getElementById('newfilename').value)" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_newbranch" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">New Branch<i class="mdi mdi-git right grey-text text-darken-3" style="font-size: 2.48rem;"></i></h4>
            <div class="row">
                <div class="input-field col s12">
                    <input type="text" id="newbranch">
                    <label class="active" for="newbranch">New Branch Name</label>
                </div>
            </div>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
          <a onclick="newbranch(document.getElementById('newbranch').value)" class=" modal-action modal-close waves-effect waves-green btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_netstat" class="modal">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3">Network status<i class="mdi mdi-network right grey-text text-darken-3" style="font-size: 2.48rem;"></i></h4>
            <p><label for="your_address">Your address:&nbsp;</label><span id="your_address">$your_address</span></p>
            <p><label for="listening_address">Listening address:&nbsp;</label><span id="listening_address">$listening_address</span></p>
            <p><label for="hass_api_address">HASS API address:&nbsp;</label><span id="hass_api_address">$hass_api_address</span></p>
            <p>Modifying the following lists is not persistent. To statically control access please use the configuration file.</p>
            <p>
                <ul id="allowed_networks" class="collection with-header"></ul>
                <br />
                <div class="input-field">
                    <a href="#" class="prefix" onclick="helper_a_net_add()"><i class="mdi mdi-plus-circle prefix light-blue-text"></i></a></i>
                    <input placeholder="192.168.0.0/16" id="add_net_ip" type="text">
                    <label for="add_net_ip">Add network / IP</label>
                </div>
            </p>
            <p>
                <ul id="banned_ips" class="collection with-header"></ul>
                <br />
                <div class="input-field">
                    <a href="#" class="prefix" onclick="helper_banned_ban()"><i class="mdi mdi-plus-circle prefix light-blue-text"></i></a></i>
                    <input placeholder="1.2.3.4" id="add_banned_ip" type="text">
                    <label for="add_banned_ip">Ban IP</label>
                </div>
            </p>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect waves-red btn-flat light-blue-text">Cancel</a>
        </div>
    </div>
    <div id="modal_about" class="modal modal-fixed-footer">
        <div class="modal-content">
            <h4 class="grey-text text-darken-3"><a class="black-text" href="https://github.com/danielperna84/hass-configurator/" target="_blank">HASS Configurator</a></h4>
            <p>Version: <a class="$versionclass" href="https://github.com/danielperna84/hass-configurator/releases/" target="_blank">$current</a></p>
            <p>Web-based file editor designed to modify configuration files of <a class="light-blue-text" href="https://home-assistant.io/" target="_blank">Home Assistant</a> or other textual files. Use at your own risk.</p>
            <p>Published under the MIT license</p>
            <p>Developed by:</p>
            <ul>
                <li>
                    <div class="chip"> <img src="https://avatars3.githubusercontent.com/u/7396998?v=4&s=400" alt="Contact Person"> <a class="black-text" href="https://github.com/danielperna84" target="_blank">Daniel Perna</a> </div>
                </li>
                <li>
                    <div class="chip"> <img src="https://avatars2.githubusercontent.com/u/1509640?v=4&s=400" alt="Contact Person"> <a class="black-text" href="https://github.com/jmart518" target="_blank">JT Martinez</a> </div>
                </li>
                <li>
                    <div class="chip"> <img src="https://avatars0.githubusercontent.com/u/1525413?v=4&s=400" alt="Contact Person"> <a class="black-text" href="https://github.com/AtoxIO" target="_blank">AtoxIO</a> </div>
                </li>
                <li>
                    <div class="chip"> <img src="https://avatars0.githubusercontent.com/u/646513?s=400&v=4" alt="Contact Person"> <a class="black-text" href="https://github.com/Munsio" target="_blank">Martin Treml</a> </div>
                </li>
                <li>
                    <div class="chip"> <img src="https://avatars2.githubusercontent.com/u/1399443?s=460&v=4" alt="Contact Person"> <a class="black-text" href="https://github.com/sytone" target="_blank">Sytone</a> </div>
                </li>
                <li>
                    <div class="chip"> <img src="https://avatars3.githubusercontent.com/u/1561226?s=400&v=4" alt="Contact Person"> <a class="black-text" href="https://github.com/dimagoltsman" target="_blank">Dima Goltsman</a> </div>
                </li>
            </ul>
            <p>Libraries used:</p>
            <div class="row">
              <div class="col s6 m3 l3">
                <a href="https://ace.c9.io/" target="_blank">
                  <div class="card grey lighten-3 hoverable waves-effect">
                    <div class="card-image">
                      <img src="https://drive.google.com/uc?export=view&id=0B6wTGzSOtvNBeld4U09LQkV0c2M">
                    </div>
                    <div class="card-content">
                      <p class="grey-text text-darken-2">Ace Editor</p>
                    </div>
                  </div>
                </a>
              </div>
              <div class="col s6 m3 l3">
                <a class="light-blue-text" href="http://materializecss.com/" target="_blank">
                  <div class="card grey lighten-3 hoverable">
                    <div class="card-image">
                      <img src="https://evwilkin.github.io/images/materializecss.png">
                    </div>
                    <div class="card-content">
                      <p class="grey-text text-darken-2">Materialize</p>
                    </div>
                  </div>
                </a>
              </div>
              <div class="col s6 m3 l3">
                <a class="light-blue-text" href="https://jquery.com/" target="_blank">
                  <div class="card grey lighten-3 hoverable">
                    <div class="card-image">
                      <img src="https://drive.google.com/uc?export=view&id=0B6wTGzSOtvNBdFI0ZXRGb01xNzQ">
                    </div>
                    <div class="card-content">
                      <p class="grey-text text-darken-2">JQuery</p>
                    </div>
                  </div>
                </a>
              </div>
              <div class="col s6 m3 l3">
                <a class="light-blue-text" href="https://gitpython.readthedocs.io" target="_blank">
                  <div class="card grey lighten-3 hoverable">
                    <div class="card-image">
                      <img src="https://drive.google.com/uc?export=view&id=0B6wTGzSOtvNBakk4ek1uRGxqYVE">
                    </div>
                    <div class="card-content">
                      <p class="grey-text text-darken-2">GitPython</p>
                    </div>
                  </div>
                </a>
              </div>
              <div class="col s6 m3 l3">
                <a class="light-blue-text" href="https://github.com/nodeca/js-yaml" target="_blank">
                  <div class="card grey lighten-3 hoverable">
                    <div class="card-image">
                    </div>
                    <div class="card-content">
                      <p class="grey-text text-darken-2">js-yaml</p>
                    </div>
                  </div>
                </a>
              </div>
            </div>
        </div>
        <div class="modal-footer">
          <a class=" modal-action modal-close waves-effect btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <div id="modal_lint" class="modal">
        <div class="modal-content">
            <textarea rows="8" readonly></textarea>
        </div>
        <div class="modal-footer">
          <a class="modal-action modal-close waves-effect btn-flat light-blue-text">OK</a>
        </div>
    </div>
    <!-- Main Editor Area -->
    <div class="row">
        <div class="col m4 l3 hide-on-small-only">
            <br>
            <div class="input-field col s12">
                <select onchange="insert(this.value)">
                    <option value="" disabled selected>Select trigger platform</option>
                    <option value="event">Event</option>
                    <option value="homeassistant">Home Assistant</option>
                    <option value="mqtt">MQTT</option>
                    <option value="numeric_state">Numeric State</option>
                    <option value="state">State</option>
                    <option value="sun">Sun</option>
                    <option value="template">Template</option>
                    <option value="time">Time</option>
                    <option value="zone">Zone</option>
                </select>
                <label>Trigger platforms</label>
            </div>
            <div class="input-field col s12">
                <select id="events" onchange="insert(this.value)"></select>
                <label>Events</label>
            </div>
            <div class="input-field col s12">
                <input type="text" id="entities-search" class="autocomplete" placeholder="sensor.example">
                <label>Search entity</label>
            </div>
            <div class="input-field col s12">
                <select id="entities" onchange="insert(this.value)"></select>
                <label>Entities</label>
            </div>
            <div class="input-field col s12">
                <select onchange="insert(this.value)">
                    <option value="" disabled selected>Select condition</option>
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
        <div class="col s12 m8 l9">
          <div class="card input-field col s12 grey lighten-4 hoverable pathtip">
              <input class="currentfile_input" value="" id="currentfile" type="text">
              <i class="material-icons" id="lint-status" onclick="show_lint_error()"></i>
          </div>
        </div>
        <div class="col s12 m8 l9 z-depth-2" id="editor"></div>
        <div id="edit_float" class="fixed-action-btn vertical click-to-toggle">
          <a class="btn-floating btn-large red accent-2 hoverable">
            <i class="material-icons">edit</i>
          </a>
          <ul>
            <li><a class="btn-floating yellow tooltipped" data-position="left" data-delay="50" data-tooltip="Undo" onclick="editor.execCommand('undo')"><i class="material-icons">undo</i></a></li>
            <li><a class="btn-floating green tooltipped" data-position="left" data-delay="50" data-tooltip="Redo" onclick="editor.execCommand('redo')"><i class="material-icons">redo</i></a></li>
            <li><a class="btn-floating blue tooltipped" data-position="left" data-delay="50" data-tooltip="Indent" onclick="editor.execCommand('indent')"><i class="material-icons">format_indent_increase</i></a></li>
            <li><a class="btn-floating orange tooltipped" data-position="left" data-delay="50" data-tooltip="Outdent" onclick="editor.execCommand('outdent')"><i class="material-icons">format_indent_decrease</i></a></li>
            <li><a class="btn-floating brown tooltipped" data-position="left" data-delay="50" data-tooltip="Fold" onclick="toggle_fold()"><i class="material-icons">all_out</i></a></li>
            <li><a class="btn-floating grey tooltipped" data-position="left" data-delay="50" data-tooltip="(Un)comment" onclick="editor.execCommand('togglecomment')">#</a></li>
          </ul>
        </div>
      </div>
      <!-- Left filebrowser sidenav -->
      <div class="row">
        <ul id="slide-out" class="side-nav grey lighten-4">
          <li class="no-padding">
            <ul class="row no-padding center hide-on-small-only grey lighten-4" style="margin-bottom: 0;">
              <a class="col s3 waves-effect fbtoolbarbutton tooltipped modal-trigger" href="#modal_newfile" data-position="bottom" data-delay="500" data-tooltip="New File"><i class="grey-text text-darken-2 material-icons fbtoolbarbutton_icon">note_add</i></a>
              <a class="col s3 waves-effect fbtoolbarbutton tooltipped modal-trigger" href="#modal_newfolder" data-position="bottom" data-delay="500" data-tooltip="New Folder"><i class="grey-text text-darken-2 material-icons fbtoolbarbutton_icon">create_new_folder</i></a>
              <a class="col s3 waves-effect fbtoolbarbutton tooltipped modal-trigger" href="#modal_upload" data-position="bottom" data-delay="500" data-tooltip="Upload File"><i class="grey-text text-darken-2 material-icons fbtoolbarbutton_icon">file_upload</i></a>
              <a class="col s3 waves-effect fbtoolbarbutton tooltipped dropdown-button $githidden" data-activates="dropdown_gitmenu" data-alignment='right' data-beloworigin='true' data-delay='500' data-position="bottom" data-tooltip="Git"><i class="mdi mdi-git grey-text text-darken-2 material-icons" style="padding-top: 17px;"></i></a>
            </ul>
            <ul class="row center toolbar_mobile hide-on-med-and-up grey lighten-4" style="margin-bottom: 0;">
              <a class="col s3 waves-effect fbtoolbarbutton modal-trigger" href="#modal_newfile"><i class="grey-text text-darken-2 material-icons fbtoolbarbutton_icon">note_add</i></a>
              <a class="col s3 waves-effect fbtoolbarbutton modal-trigger" href="#modal_newfolder"><i class="grey-text text-darken-2 material-icons fbtoolbarbutton_icon">create_new_folder</i></a>
              <a class="col s3 waves-effect fbtoolbarbutton modal-trigger" href="#modal_upload"><i class="grey-text text-darken-2 material-icons fbtoolbarbutton_icon">file_upload</i></a>
              <a class="col s3 waves-effect fbtoolbarbutton dropdown-button $githidden" data-activates="dropdown_gitmenu_mobile" data-alignment='right' data-beloworigin='true'><i class="mdi mdi-git grey-text text-darken-2 material-icons" style="padding-top: 17px;"></i></a>
            </ul>
          </li>
          <li>
            <div class="col s2 no-padding" style="min-height: 64px">
              <a id="uplink" class="col s12 waves-effect" style="min-height: 64px; padding-top: 15px; cursor: pointer;"><i class="arrow grey-text text-darken-2 material-icons">arrow_back</i></a>
            </div>
            <div class="col s10 " style="white-space: nowrap; overflow: auto; min-height: 64px">
              <div id="fbheader" class="leftellipsis"></div>
            </div>
          </li>
          <ul id='branches' class="dropdown-content branch_select z-depth-2 grey lighten-4">
            <ul id="branchlist"></ul>
          </ul>
          <li>
            <ul class="row no-padding" style="margin-bottom: 0;">
              <a id="branchselector" class="col s10 dropdown-button waves-effect truncate grey-text text-darken-2" data-beloworigin="true" data-activates='branches'><i class="grey-text text-darken-2 left material-icons" style="margin-left: 0; margin-right: 0; padding-top: 12px; padding-right: 8px;">arrow_drop_down</i>Branch:<span id="fbheaderbranch"></span></a>
              <a id="newbranchbutton" class="waves-effect col s2 center modal-trigger" href="#modal_newbranch"><i class="grey-text text-darken-2 center material-icons" style="padding-top: 12px;">add</i></a>
            </ul>
            <div class="divider" style="margin-top: 0;"></div>
          </li>
          <li>
            <ul id="fbelements"></ul>
          </li>
          <div class="row col s12 shadow"></div>
          <div class="z-depth-3 hide-on-med-and-up">
            <div class="input-field col s12" style="margin-top: 30px;">
              <select onchange="insert(this.value)">
                <option value="" disabled selected>Select trigger platform</option>
                <option value="event">Event</option>
                <option value="mqtt">MQTT</option>
                <option value="numeric_state">Numeric State</option>
                <option value="state">State</option>
                <option value="sun">Sun</option>
                <option value="template">Template</option>
                <option value="time">Time</option>
                <option value="zone">Zone</option>
              </select>
              <label>Trigger Platforms</label>
            </div>
            <div class="input-field col s12">
              <select id="events_side" onchange="insert(this.value)"></select>
              <label>Events</label>
            </div>
            <div class="input-field col s12">
                <input type="text" id="entities-search_side" class="autocomplete" placeholder="sensor.example">
                <label>Search entity</label>
            </div>
            <div class="input-field col s12">
              <select id="entities_side" onchange="insert(this.value)"></select>
              <label>Entities</label>
            </div>
            <div class="input-field col s12">
              <select onchange="insert(this.value)">
                <option value="" disabled selected>Select condition</option>
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
              <select id="services_side" onchange="insert(this.value)"></select>
              <label>Services</label>
            </div>
          </div>
        </ul>
      </div>
      <!-- Ace Editor SideNav -->
      <div class="row">
        <ul id="ace_settings" class="side-nav">
          <li class="center s12 grey lighten-3 z-depth-1 subheader">Editor Settings</li>
          <div class="row col s12">
              <p class="col s12"> <a class="waves-effect waves-light btn light-blue modal-trigger" href="#modal_acekeyboard">Keyboard Shortcuts</a> </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="set_save_prompt(this.checked)" id="savePrompt" />
                  <Label for="savePrompt">Prompt before save</label>
              </p>
              <p class="col s12">
                <input type="checkbox" class="blue_check" onclick="set_hide_filedetails(this.checked)" id="hideDetails" />
                <Label for="hideDetails">Hide details in browser</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('animatedScroll', !editor.getOptions().animatedScroll)" id="animatedScroll" />
                  <Label for="animatedScroll">Animated Scroll</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('behavioursEnabled', !editor.getOptions().behavioursEnabled)" id="behavioursEnabled" />
                  <Label for="behavioursEnabled">Behaviour Enabled</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('displayIndentGuides', !editor.getOptions().displayIndentGuides)" id="displayIndentGuides" />
                  <Label for="displayIndentGuides">Display Indent Guides</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('fadeFoldWidgets', !editor.getOptions().fadeFoldWidgets)" id="fadeFoldWidgets" />
                  <Label for="fadeFoldWidgets">Fade Fold Widgets</label>
              </p>
              <div class="input-field col s12">
                  <input type="number" onchange="editor.setOption('fontSize', parseInt(this.value))" min="6" id="fontSize">
                  <label class="active" for="fontSize">Font Size</label>
              </div>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('highlightActiveLine', !editor.getOptions().highlightActiveLine)" id="highlightActiveLine" />
                  <Label for="highlightActiveLine">Hightlight Active Line</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('highlightGutterLine', !editor.getOptions().highlightGutterLine)" id="highlightGutterLine" />
                  <Label for="highlightGutterLine">Hightlight Gutter Line</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('highlightSelectedWord', !editor.getOptions().highlightSelectedWord)" id="highlightSelectedWord" />
                  <Label for="highlightSelectedWord">Hightlight Selected Word</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('hScrollBarAlwaysVisible', !editor.getOptions().hScrollBarAlwaysVisible)" id="hScrollBarAlwaysVisible" />
                  <Label for="hScrollBarAlwaysVisible">H Scroll Bar Always Visible</label>
              </p>
              <div class="input-field col s12">
                  <select onchange="editor.setKeyboardHandler(this.value)" id="setKeyboardHandler">
                      <option value="">ace</option>
                      <option value="ace/keyboard/vim">vim</option>
                      <option value="ace/keyboard/emacs">emacs</option>
                  </select>
                  <label for="setKeyboardHandler">Keyboard Handler</label>
              </div>
              <div class="input-field col s12">
                  <select onchange="editor.setOption('mode', this.value)" id="mode">
                      <option value="ace/mode/abap">abap</option>
                      <option value="ace/mode/abc">abc</option>
                      <option value="ace/mode/actionscript">actionscript</option>
                      <option value="ace/mode/ada">ada</option>
                      <option value="ace/mode/apache_conf">apache_conf</option>
                      <option value="ace/mode/asciidoc">asciidoc</option>
                      <option value="ace/mode/assembly_x86">assembly_x86</option>
                      <option value="ace/mode/autohotkey">autohotkey</option>
                      <option value="ace/mode/batchfile">batchfile</option>
                      <option value="ace/mode/bro">bro</option>
                      <option value="ace/mode/c_cpp">c_cpp</option>
                      <option value="ace/mode/c9search">c9search</option>
                      <option value="ace/mode/cirru">cirru</option>
                      <option value="ace/mode/clojure">clojure</option>
                      <option value="ace/mode/cobol">cobol</option>
                      <option value="ace/mode/coffee">coffee</option>
                      <option value="ace/mode/coldfusion">coldfusion</option>
                      <option value="ace/mode/csharp">csharp</option>
                      <option value="ace/mode/css">css</option>
                      <option value="ace/mode/curly">curly</option>
                      <option value="ace/mode/d">d</option>
                      <option value="ace/mode/dart">dart</option>
                      <option value="ace/mode/diff">diff</option>
                      <option value="ace/mode/django">django</option>
                      <option value="ace/mode/dockerfile">dockerfile</option>
                      <option value="ace/mode/dot">dot</option>
                      <option value="ace/mode/drools">drools</option>
                      <option value="ace/mode/dummy">dummy</option>
                      <option value="ace/mode/dummysyntax">dummysyntax</option>
                      <option value="ace/mode/eiffel">eiffel</option>
                      <option value="ace/mode/ejs">ejs</option>
                      <option value="ace/mode/elixir">elixir</option>
                      <option value="ace/mode/elm">elm</option>
                      <option value="ace/mode/erlang">erlang</option>
                      <option value="ace/mode/forth">forth</option>
                      <option value="ace/mode/fortran">fortran</option>
                      <option value="ace/mode/ftl">ftl</option>
                      <option value="ace/mode/gcode">gcode</option>
                      <option value="ace/mode/gherkin">gherkin</option>
                      <option value="ace/mode/gitignore">gitignore</option>
                      <option value="ace/mode/glsl">glsl</option>
                      <option value="ace/mode/gobstones">gobstones</option>
                      <option value="ace/mode/golang">golang</option>
                      <option value="ace/mode/groovy">groovy</option>
                      <option value="ace/mode/haml">haml</option>
                      <option value="ace/mode/handlebars">handlebars</option>
                      <option value="ace/mode/haskell">haskell</option>
                      <option value="ace/mode/haskell_cabal">haskell_cabal</option>
                      <option value="ace/mode/haxe">haxe</option>
                      <option value="ace/mode/hjson">hjson</option>
                      <option value="ace/mode/html">html</option>
                      <option value="ace/mode/html_elixir">html_elixir</option>
                      <option value="ace/mode/html_ruby">html_ruby</option>
                      <option value="ace/mode/ini">ini</option>
                      <option value="ace/mode/io">io</option>
                      <option value="ace/mode/jack">jack</option>
                      <option value="ace/mode/jade">jade</option>
                      <option value="ace/mode/java">java</option>
                      <option value="ace/mode/javascript">javascript</option>
                      <option value="ace/mode/json">json</option>
                      <option value="ace/mode/jsoniq">jsoniq</option>
                      <option value="ace/mode/jsp">jsp</option>
                      <option value="ace/mode/jsx">jsx</option>
                      <option value="ace/mode/julia">julia</option>
                      <option value="ace/mode/kotlin">kotlin</option>
                      <option value="ace/mode/latex">latex</option>
                      <option value="ace/mode/less">less</option>
                      <option value="ace/mode/liquid">liquid</option>
                      <option value="ace/mode/lisp">lisp</option>
                      <option value="ace/mode/livescript">livescript</option>
                      <option value="ace/mode/logiql">logiql</option>
                      <option value="ace/mode/lsl">lsl</option>
                      <option value="ace/mode/lua">lua</option>
                      <option value="ace/mode/luapage">luapage</option>
                      <option value="ace/mode/lucene">lucene</option>
                      <option value="ace/mode/makefile">makefile</option>
                      <option value="ace/mode/markdown">markdown</option>
                      <option value="ace/mode/mask">mask</option>
                      <option value="ace/mode/matlab">matlab</option>
                      <option value="ace/mode/maze">maze</option>
                      <option value="ace/mode/mel">mel</option>
                      <option value="ace/mode/mushcode">mushcode</option>
                      <option value="ace/mode/mysql">mysql</option>
                      <option value="ace/mode/nix">nix</option>
                      <option value="ace/mode/nsis">nsis</option>
                      <option value="ace/mode/objectivec">objectivec</option>
                      <option value="ace/mode/ocaml">ocaml</option>
                      <option value="ace/mode/pascal">pascal</option>
                      <option value="ace/mode/perl">perl</option>
                      <option value="ace/mode/pgsql">pgsql</option>
                      <option value="ace/mode/php">php</option>
                      <option value="ace/mode/powershell">powershell</option>
                      <option value="ace/mode/praat">praat</option>
                      <option value="ace/mode/prolog">prolog</option>
                      <option value="ace/mode/properties">properties</option>
                      <option value="ace/mode/protobuf">protobuf</option>
                      <option value="ace/mode/python">python</option>
                      <option value="ace/mode/r">r</option>
                      <option value="ace/mode/razor">razor</option>
                      <option value="ace/mode/rdoc">rdoc</option>
                      <option value="ace/mode/rhtml">rhtml</option>
                      <option value="ace/mode/rst">rst</option>
                      <option value="ace/mode/ruby">ruby</option>
                      <option value="ace/mode/rust">rust</option>
                      <option value="ace/mode/sass">sass</option>
                      <option value="ace/mode/scad">scad</option>
                      <option value="ace/mode/scala">scala</option>
                      <option value="ace/mode/scheme">scheme</option>
                      <option value="ace/mode/scss">scss</option>
                      <option value="ace/mode/sh">sh</option>
                      <option value="ace/mode/sjs">sjs</option>
                      <option value="ace/mode/smarty">smarty</option>
                      <option value="ace/mode/snippets">snippets</option>
                      <option value="ace/mode/soy_template">soy_template</option>
                      <option value="ace/mode/space">space</option>
                      <option value="ace/mode/sql">sql</option>
                      <option value="ace/mode/sqlserver">sqlserver</option>
                      <option value="ace/mode/stylus">stylus</option>
                      <option value="ace/mode/svg">svg</option>
                      <option value="ace/mode/swift">swift</option>
                      <option value="ace/mode/tcl">tcl</option>
                      <option value="ace/mode/tex">tex</option>
                      <option value="ace/mode/text">text</option>
                      <option value="ace/mode/textile">textile</option>
                      <option value="ace/mode/toml">toml</option>
                      <option value="ace/mode/tsx">tsx</option>
                      <option value="ace/mode/twig">twig</option>
                      <option value="ace/mode/typescript">typescript</option>
                      <option value="ace/mode/vala">vala</option>
                      <option value="ace/mode/vbscript">vbscript</option>
                      <option value="ace/mode/velocity">velocity</option>
                      <option value="ace/mode/verilog">verilog</option>
                      <option value="ace/mode/vhdl">vhdl</option>
                      <option value="ace/mode/wollok">wollok</option>
                      <option value="ace/mode/xml">xml</option>
                      <option value="ace/mode/xquery">xquery</option>
                      <option value="ace/mode/yaml">yaml</option>
                  </select>
                  <label for="mode">Mode</label>
              </div>
              <div class="input-field col s12">
                  <select onchange="editor.setOption('newLineMode', this.value)" id="newLineMode">
                      <option value="auto">Auto</option>
                      <option value="windows">Windows</option>
                      <option value="unix">Unix</option>
                  </select>
                  <label for="newLineMode">New Line Mode</label>
              </div>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('overwrite', !editor.getOptions().overwrite)" id="overwrite" />
                  <Label for="overwrite">Overwrite</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('readOnly', !editor.getOptions().readOnly)" id="readOnly" />
                  <Label for="readOnly">Read Only</label>
              </p>
              <div class="input-field col s12">
                  <input value="2" type="number" onchange="editor.setOption('scrollSpeed', parseInt(this.value))" id="scrollSpeed">
                  <label class="active" for="scrollSpeed">Scroll Speed</label>
              </div>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('showFoldWidgets', !editor.getOptions().showFoldWidgets)" id="showFoldWidgets" />
                  <Label for="showFoldWidgets">Show Fold Widgets</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('showGutter', !editor.getOptions().showGutter)" id="showGutter" />
                  <Label for="showGutter">Show Gutter</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('showInvisibles', !editor.getOptions().showInvisibles)" id="showInvisibles" />
                  <Label for="showInvisibles">Show Invisibles</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('showPrintMargin', !editor.getOptions().showPrintMargin)" id="showPrintMargin" />
                  <Label for="showPrintMargin">Show Print Margin</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('showLineNumbers', !editor.getOptions().showLineNumbers)" id="showLineNumbers" />
                  <Label for="showLineNumbers">Show Line Numbers</label>
              </p>
              <div class="input-field col s12">
                  <input type="number" onchange="editor.setOption('tabSize', parseInt(this.value))" min="1" id="tabSize">
                  <label class="active" for="tabSize">Tab Size</label>
              </div>
              <div class="input-field col s12">
                  <select onchange="editor.setTheme(this.value)" id="theme">
                      <optgroup label="Light Themes">
                          <option value="ace/theme/chrome">Chrome</option>
                          <option value="ace/theme/clouds">Clouds</option>
                          <option value="ace/theme/crimson_editor">Crimson Editor</option>
                          <option value="ace/theme/dawn">Dawn</option>
                          <option value="ace/theme/dreamweaver">Dreamweaver</option>
                          <option value="ace/theme/eclipse">Eclipse</option>
                          <option value="ace/theme/github">GitHub</option>
                          <option value="ace/theme/iplastic">IPlastic</option>
                          <option value="ace/theme/solarized_light">Solarized Light</option>
                          <option value="ace/theme/textmate">TextMate</option>
                          <option value="ace/theme/tomorrow">Tomorrow</option>
                          <option value="ace/theme/xcode">XCode</option>
                          <option value="ace/theme/kuroir">Kuroir</option>
                          <option value="ace/theme/katzenmilch">KatzenMilch</option>
                          <option value="ace/theme/sqlserver">SQL Server</option>
                      </optgroup>
                      <optgroup label="Dark Themes">
                          <option value="ace/theme/ambiance">Ambiance</option>
                          <option value="ace/theme/chaos">Chaos</option>
                          <option value="ace/theme/clouds_midnight">Clouds Midnight</option>
                          <option value="ace/theme/cobalt">Cobalt</option>
                          <option value="ace/theme/gruvbox">Gruvbox</option>
                          <option value="ace/theme/idle_fingers">idle Fingers</option>
                          <option value="ace/theme/kr_theme">krTheme</option>
                          <option value="ace/theme/merbivore">Merbivore</option>
                          <option value="ace/theme/merbivore_soft">Merbivore Soft</option>
                          <option value="ace/theme/mono_industrial">Mono Industrial</option>
                          <option value="ace/theme/monokai">Monokai</option>
                          <option value="ace/theme/pastel_on_dark">Pastel on dark</option>
                          <option value="ace/theme/solarized_dark">Solarized Dark</option>
                          <option value="ace/theme/terminal">Terminal</option>
                          <option value="ace/theme/tomorrow_night">Tomorrow Night</option>
                          <option value="ace/theme/tomorrow_night_blue">Tomorrow Night Blue</option>
                          <option value="ace/theme/tomorrow_night_bright">Tomorrow Night Bright</option>
                          <option value="ace/theme/tomorrow_night_eighties">Tomorrow Night 80s</option>
                          <option value="ace/theme/twilight">Twilight</option>
                          <option value="ace/theme/vibrant_ink">Vibrant Ink</option>
                      </optgroup>
                  </select>
                  <label for="theme">Theme</label>
              </div>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('useSoftTabs', !editor.getOptions().useSoftTabs)" id="useSoftTabs" />
                  <Label for="useSoftTabs">Use Soft Tabs</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('useWorker', !editor.getOptions().useWorker)" id="useWorker" />
                  <Label for="useWorker">Use Worker</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('vScrollBarAlwaysVisible', !editor.getOptions().vScrollBarAlwaysVisible)" id="vScrollBarAlwaysVisible" />
                  <Label for="vScrollBarAlwaysVisible">V Scroll Bar Always Visible</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.setOption('wrapBehavioursEnabled', !editor.getOptions().wrapBehavioursEnabled)" id="wrapBehavioursEnabled" />
                  <Label for="wrapBehavioursEnabled">Wrap Behaviours Enabled</label>
              </p>
              <p class="col s12">
                  <input type="checkbox" class="blue_check" onclick="editor.getSession().setUseWrapMode(!editor.getSession().getUseWrapMode());if(editor.getSession().getUseWrapMode()){document.getElementById('wrap_limit').focus();document.getElementById('wrap_limit').onchange();}" id="wrap" />
                  <Label for="wrap">Wrap Mode</label>
              </p>
              <div class="input-field col s12">
                  <input id="wrap_limit" type="number" onchange="editor.setOption('wrap', parseInt(this.value))" min="1" value="80">
                  <label class="active" for="wrap_limit">Wrap Limit</label>
              </div> <a class="waves-effect waves-light btn light-blue" onclick="save_ace_settings()">Save Settings Locally</a>
              <p class="center col s12"> Ace Editor 1.4.2 </p>
          </div>
        </ul>
      </div>
</main>
<input type="hidden" id="fb_currentfile" value="" />
<!-- Scripts -->
<script src="https://code.jquery.com/jquery-3.3.1.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.100.2/js/materialize.min.js"></script>
<script>
    function ws_connect() {
        function msg(str) {
            document.getElementById("ws_events").value = str + "\n\n" + document.getElementById("ws_events").value;
            $('#ws_events').trigger('autoresize');
        }

        try {
            ws = new WebSocket(document.getElementById("ws_uri").value);
            ws.addEventListener("open", function(event) {
                if (document.getElementById("ws_password").value.split(".").length == 3) {
                    var auth = {
                        type: "auth",
                        access_token: document.getElementById("ws_password").value
                    };
                }
                else {
                    var auth = {
                        type: "auth",
                        api_password: document.getElementById("ws_password").value
                    };
                }
                var data = {
                    id: 1,
                    type: "subscribe_events"
                };
                if (document.getElementById("ws_password").value) {
                    ws.send(JSON.stringify(auth));
                }
                ws.send(JSON.stringify(data));
            });
            ws.onmessage = function(event) {
                msg(event.data);
            }
            ws.onclose = function() {
                msg('Socket closed');
                document.getElementById('ws_b_c').classList.remove('disabled');
                document.getElementById('ws_b_d').classList.add('disabled');
            };
            ws.onopen = function() {
                msg('Socket connected');
                document.getElementById('ws_b_c').classList.add('disabled');
                document.getElementById('ws_b_d').classList.remove('disabled');
            };
        }
        catch(err) {
            console.log("Error: " + err.message);
        }
    }

    function ws_disconnect() {
        try {
            ws.close();
        }
        catch(err) {
            console.log("Error: " + err.message);
        }
    }
</script>
<script type="text/javascript">
    var init_loadfile = $loadfile;
    var global_current_filepath = null;
    var global_current_filename = null;

    function got_focus_or_visibility() {
        if (global_current_filename && global_current_filepath) {
            // The globals are set, set the localStorage to those values
            var current_file = {current_filepath: global_current_filepath,
                                current_filename: global_current_filename}
            localStorage.setItem('current_file', JSON.stringify(current_file));
        }
        else {
            // This tab had no prior file opened, clearing from localStorage
            localStorage.removeItem('current_file');
        }
    }

    window.onfocus = function() {
        got_focus_or_visibility();
    }
    //window.onblur = function() {
    //    console.log("lost focus");
    //}

    // Got this from here: https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
    // Set the name of the hidden property and the change event for visibility
    var hidden, visibilityChange; 
    if (typeof document.hidden !== "undefined") { // Opera 12.10 and Firefox 18 and later support 
        hidden = "hidden";
        visibilityChange = "visibilitychange";
    }
    else if (typeof document.msHidden !== "undefined") {
        hidden = "msHidden";
        visibilityChange = "msvisibilitychange";
    }
    else if (typeof document.webkitHidden !== "undefined") {
        hidden = "webkitHidden";
        visibilityChange = "webkitvisibilitychange";
    }

    function handleVisibilityChange() {
        if (document[hidden]) {
            // We're doing nothing when the tab gets out of vision
        }
        else {
            // We're doing this if the tab becomes visible
            got_focus_or_visibility();
        }
    }
    // Warn if the browser doesn't support addEventListener or the Page Visibility API
    if (typeof document.addEventListener === "undefined" || typeof document.hidden === "undefined") {
        console.log("This requires a browser, such as Google Chrome or Firefox, that supports the Page Visibility API.");
    }
    else {
        // Handle page visibility change
        document.addEventListener(visibilityChange, handleVisibilityChange, false);
    }

    $(document).keydown(function(e) {
        if ((e.key == 's' || e.key == 'S' ) && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            save_check();
            return false;
        }
        return true;
    }); 

    $(document).ready(function () {
        $('select').material_select();
        $('.modal').modal();
        $('ul.tabs').tabs();
        $('.collapsible').collapsible({
          onOpen: function(el) {
            $('#branch_tab').click();
          },
        });
        $('.dropdown-button').dropdown({
            inDuration: 300,
            outDuration: 225,
            constrainWidth: false,
            hover: false,
            gutter: 0,
            belowOrigin: true,
            alignment: 'right',
            stopPropagation: false
        });
        $('.files-collapse').sideNav({
            menuWidth: 320,
            edge: 'left',
            closeOnClick: false,
            draggable: true
        });
        $('.ace_settings-collapse').sideNav({
            menuWidth: 300,
            edge: 'right',
            closeOnClick: true,
            draggable: false
        });
        // This fixes the dead spaces when trying to close the file browser
        $(document).on('click', '.drag-target', function(){$('.button-collapse').sideNav('hide');})
        listdir('.');
        document.getElementById('savePrompt').checked = get_save_prompt();
        document.getElementById('hideDetails').checked = get_hide_filedetails();
        var entities_search = new Object();
        if (states_list) {
            for (var i = 0; i < states_list.length; i++) {
                entities_search[states_list[i].attributes.friendly_name + ' (' + states_list[i].entity_id + ')'] = null;
            }
        }
        $('#entities-search').autocomplete({
            data: entities_search,
            limit: 40,
            onAutocomplete: function(val) {
                insert(val.split("(")[1].split(")")[0]);
            },
            minLength: 1,
        });
        $('#entities-search_side').autocomplete({
            data: entities_search,
            limit: 40,
            onAutocomplete: function(val) {
                insert(val.split("(")[1].split(")")[0]);
            },
            minLength: 1,
        });
    });
</script>
<script type="text/javascript">
    document.addEventListener("DOMContentLoaded", function() {
        $('.preloader-background').delay(800).fadeOut('slow');
        $('.preloader-wrapper').delay(800).fadeOut('slow');
        if (init_loadfile) {
            init_loadfile_name = init_loadfile.split('/').pop();
            loadfile(init_loadfile, init_loadfile_name);
        }
        else {
            if (!localStorage.getItem("new_tab")) {
                var old_file = localStorage.getItem("current_file");
                if (old_file) {
                    old_file = JSON.parse(old_file);
                    loadfile(old_file.current_filepath, old_file.current_filename);
                }
            }
            else {
                localStorage.removeItem("current_file");
            }
            localStorage.removeItem("new_tab");
        }
    });
</script>
<script>
    var modemapping = new Object();
    modemapping['c'] = 'ace/mode/c_cpp';
    modemapping['cpp'] = 'ace/mode/c_cpp';
    modemapping['css'] = 'ace/mode/css';
    modemapping['gitignore'] = 'ace/mode/gitignore';
    modemapping['htm'] = 'ace/mode/html';
    modemapping['html'] = 'ace/mode/html';
    modemapping['js'] = 'ace/mode/javascript';
    modemapping['json'] = 'ace/mode/json';
    modemapping['php'] = 'ace/mode/php';
    modemapping['py'] = 'ace/mode/python';
    modemapping['sh'] = 'ace/mode/sh';
    modemapping['sql'] = 'ace/mode/sql';
    modemapping['txt'] = 'ace/mode/text';
    modemapping['xml'] = 'ace/mode/xml';
    modemapping['yaml'] = 'ace/mode/yaml';

    function sort_select(id) {
        var options = $('#' + id + ' option');
        var arr = options.map(function (_, o) {
            return {
                t: $(o).text(), v: o.value
            };
        }).get();
        arr.sort(function (o1, o2) {
            var t1 = o1.t.toLowerCase(), t2 = o2.t.toLowerCase();
            return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
        });
        options.each(function (i, o) {
            o.value = arr[i].v;
            $(o).text(arr[i].t);
        });
    }

    var separator = '$separator';
    var services_list = $services;
    var events_list = $events;
    var states_list = $states;

    if (events_list) {
        var events = document.getElementById("events");
        for (var i = 0; i < events_list.length; i++) {
            var option = document.createElement("option");
            option.value = events_list[i].event;
            option.text = events_list[i].event;
            events.add(option);
        }
        var events = document.getElementById("events_side");
        for (var i = 0; i < events_list.length; i++) {
            var option = document.createElement("option");
            option.value = events_list[i].event;
            option.text = events_list[i].event;
            events.add(option);
        }
        sort_select('events');
        sort_select('events_side');
    }

    if (states_list) {
        var entities = document.getElementById("entities");
        for (var i = 0; i < states_list.length; i++) {
            var option = document.createElement("option");
            option.value = states_list[i].entity_id;
            option.text = states_list[i].attributes.friendly_name + ' (' + states_list[i].entity_id + ')';
            entities.add(option);
        }
        var entities = document.getElementById("entities_side");
        for (var i = 0; i < states_list.length; i++) {
            var option = document.createElement("option");
            option.value = states_list[i].entity_id;
            option.text = states_list[i].attributes.friendly_name + ' (' + states_list[i].entity_id + ')';
            entities.add(option);
        }
        sort_select('entities');
        sort_select('entities_side');
    }

    if (services_list) {
        var services = document.getElementById("services");
        for (var i = 0; i < services_list.length; i++) {
            for (var k in services_list[i].services) {
                var option = document.createElement("option");
                option.value = services_list[i].domain + '.' + k;
                option.text = services_list[i].domain + '.' + k;
                services.add(option);
            }
        }
        var services = document.getElementById("services_side");
        for (var i = 0; i < services_list.length; i++) {
            for (var k in services_list[i].services) {
                var option = document.createElement("option");
                option.value = services_list[i].domain + '.' + k;
                option.text = services_list[i].domain + '.' + k;
                services.add(option);
            }
        }
        sort_select('services');
        sort_select('services_side');
    }

    function listdir(path) {
        $.get(encodeURI("api/listdir?path=" + path), function(data) {
            if (!data.error) {
                renderpath(data);
            }
            else {
                console.log("Permission denied."); 
            }
        });
        document.getElementById("slide-out").scrollTop = 0;
    }

    function renderitem(itemdata, index) {
        var li = document.createElement('li');
        li.classList.add("collection-item", "fbicon_pad", "col", "s12", "no-padding", "white");
        var item = document.createElement('a');
        item.classList.add("waves-effect", "col", "s10", "fbicon_pad");
        var iicon = document.createElement('i');
        iicon.classList.add("material-icons", "fbmenuicon_pad");
        var stats = document.createElement('span');
        date = new Date(itemdata.modified*1000);
        stats.classList.add('stats');
        if (itemdata.type == 'dir') {
            iicon.innerHTML = 'folder';
            item.setAttribute("onclick", "listdir('" + encodeURI(itemdata.fullpath) + "')");
            stats.innerHTML = "Mod.: " + date.toUTCString();
        }
        else {
            nameparts = itemdata.name.split('.');
            extension = nameparts[nameparts.length -1];
            if (['c', 'cpp', 'css', 'htm', 'html', 'js', 'json', 'php', 'py', 'sh', 'sql', 'xml', 'yaml'].indexOf(extension.toLocaleLowerCase()) > +1 ) {
                iicon.classList.add('mdi', 'mdi-file-xml');
            }
            else if (['txt', 'doc', 'docx'].indexOf(extension.toLocaleLowerCase()) > -1 ) {
                iicon.classList.add('mdi', 'mdi-file-document');
            }
            else if (['bmp', 'gif', 'jpg', 'jpeg', 'png', 'tif', 'webp'].indexOf(extension.toLocaleLowerCase()) > -1 ) {
                iicon.classList.add('mdi', 'mdi-file-image');
            }
            else if (['mp3', 'ogg', 'wav'].indexOf(extension) > -1 ) {
                iicon.classList.add('mdi', 'mdi-file-music');
            }
            else if (['avi', 'flv', 'mkv', 'mp4', 'mpg', 'mpeg', 'webm'].indexOf(extension.toLocaleLowerCase()) > -1 ) {
                iicon.classList.add('mdi', 'mdi-file-video');
            }
            else if (['pdf'].indexOf(extension.toLocaleLowerCase()) > -1 ) {
                iicon.classList.add('mdi', 'mdi-file-pdf');
            }
            else {
                iicon.classList.add('mdi', 'mdi-file');
            }
            item.setAttribute("onclick", "loadfile('" + encodeURI(itemdata.fullpath) + "', '" + itemdata.name + "')");
            stats.innerHTML = "Mod.: " + date.toUTCString() + "&nbsp;&nbsp;Size: " + (itemdata.size/1024).toFixed(1) + " KiB";
        }
        item.appendChild(iicon);
        var itext = document.createElement('div');
        itext.innerHTML = itemdata.name;
        itext.classList.add("filename");

        var hasgitadd = false;
        if (itemdata.gitstatus) {
            if (itemdata.gittracked == 'untracked') {
                itext.classList.add('text_darkred');
                hasgitadd = true;
            }
            else {
                if(itemdata.gitstatus == 'unstaged') {
                    itext.classList.add('text_darkred');
                    hasgitadd = true;
                }
                else if (itemdata.gitstatus == 'staged') {
                    itext.classList.add('text_darkgreen');
                }
            }
        }

        item.appendChild(itext);
        if (!get_hide_filedetails()) {
            item.appendChild(stats);
        }

        var dropdown = document.createElement('ul');
        dropdown.id = 'fb_dropdown_' + index;
        dropdown.classList.add('dropdown-content');
        dropdown.classList.add("z-depth-4");

        // Download button
        var dd_download = document.createElement('li');
        var dd_download_a = document.createElement('a');
        dd_download_a.classList.add("waves-effect", "fb_dd");
        dd_download_a.setAttribute('onclick', "download_file('" + encodeURI(itemdata.fullpath) + "')");
        dd_download_a.innerHTML = "Download";
        dd_download.appendChild(dd_download_a);
        dropdown.appendChild(dd_download);

        // Delete button
        var dd_delete = document.createElement('li');
        dd_delete.classList.add("waves-effect", "fb_dd");
        var dd_delete_a = document.createElement('a');
        dd_delete_a.setAttribute('href', "#modal_delete");
        dd_delete_a.classList.add("modal-trigger");
        dd_delete_a.innerHTML = "Delete";
        dd_delete.appendChild(dd_delete_a);
        dropdown.appendChild(dd_delete);

        if (itemdata.gitstatus) {
            if (hasgitadd) {
                var divider = document.createElement('li');
                divider.classList.add('divider');
                dropdown.appendChild(divider);
                // git add button
                var dd_gitadd = document.createElement('li');
                var dd_gitadd_a = document.createElement('a');
                dd_gitadd_a.classList.add('waves-effect', 'fb_dd', 'modal-trigger');
                dd_gitadd_a.setAttribute('href', "#modal_gitadd");
                dd_gitadd_a.innerHTML = "git add";
                dd_gitadd.appendChild(dd_gitadd_a);
                dropdown.appendChild(dd_gitadd);
                // git diff button
                var dd_gitdiff = document.createElement('li');
                var dd_gitdiff_a = document.createElement('a');
                dd_gitdiff_a.classList.add('waves-effect', 'fb_dd', 'modal-trigger');
                dd_gitdiff_a.setAttribute('onclick', "gitdiff()");
                dd_gitdiff_a.innerHTML = "git diff";
                dd_gitdiff.appendChild(dd_gitdiff_a);
                dropdown.appendChild(dd_gitdiff);
            }
        }

        var menubutton = document.createElement('a');
        menubutton.classList.add("fbmenubutton", "waves-effect", "dropdown-button", "col", "s2", "fbicon_pad");
        menubutton.classList.add('waves-effect');
        menubutton.classList.add('dropdown-button');
        menubutton.setAttribute('data-activates', dropdown.id);
        menubutton.setAttribute('data-alignment', 'right');

        var menubuttonicon = document.createElement('i');
        menubutton.classList.add('material-icons');
        menubutton.classList.add("right");
        menubutton.innerHTML = 'more_vert';
        menubutton.setAttribute('onclick', "document.getElementById('fb_currentfile').value='" + encodeURI(itemdata.fullpath) + "';$('span.fb_currentfile').html('" + itemdata.name + "')");
        li.appendChild(item);
        li.appendChild(menubutton);
        li.setAttribute("title", itemdata.name)
        li.appendChild(dropdown);
        return li;
    }

    function renderpath(dirdata) {
        var newbranchbutton = document.getElementById('newbranchbutton');
        newbranchbutton.style.cssText = "display: none !important"
        var fbelements = document.getElementById("fbelements");
        while (fbelements.firstChild) {
            fbelements.removeChild(fbelements.firstChild);
        }
        var fbheader = document.getElementById('fbheader');
        fbheader.innerHTML = dirdata.abspath;
        var branchselector = document.getElementById('branchselector');
        var fbheaderbranch = document.getElementById('fbheaderbranch');
        var branchlist = document.getElementById('branchlist');
        while (branchlist.firstChild) {
            branchlist.removeChild(branchlist.firstChild);
        }
        if (dirdata.activebranch) {
            newbranchbutton.style.display = "inline-block";
            fbheaderbranch.innerHTML = dirdata.activebranch;
            fbheaderbranch.style.display = "inline";
            branchselector.style.display = "block";
            for (var i = 0; i < dirdata.branches.length; i++) {
                var branch = document.createElement('li');
                var link = document.createElement('a');
                link.classList.add("branch_select", "truncate");
                link.innerHTML = dirdata.branches[i];
                link.href = '#';
                link.setAttribute('onclick', 'checkout("' + dirdata.branches[i] + '");collapseAll()')
                branch.appendChild(link);
                if (dirdata.branches[i] == dirdata.activebranch) {
                    link.classList.add("active", "grey", "darken-1");
                }
                else {
                    link.classList.add("grey-text", "text-darken-3", "branch_hover", "waves-effect", "grey", "lighten-4");
                }
                branchlist.appendChild(branch);
            }
        }
        else {
            fbheaderbranch.innerHTML = "";
            fbheaderbranch.style.display = "";
            branchselector.style.display = "none";
        }

        var uplink = document.getElementById('uplink');
        uplink.setAttribute("onclick", "listdir('" + encodeURI(dirdata.parent) + "')")

        for (var i = 0; i < dirdata.content.length; i++) {
            fbelements.appendChild(renderitem(dirdata.content[i], i));
        }
        $(".dropdown-button").dropdown();
    }

    function collapseAll() {
        $(".collapsible-header").removeClass(function() { return "active"; });
        $(".collapsible").collapsible({accordion: true});
        $(".collapsible").collapsible({accordion: false});
    }

    function checkout(){
        $(".collapsible-header").removeClass(function(){
            return "active";
        });
        $(".collapsible").collapsible({accordion: true});
        $(".collapsible").collapsible({accordion: false});
    }

    function loadfile(filepath, filenameonly) {
        if ($('.markdirty.red').length) {
            $('#modal_markdirty').modal('open');
        }
        else {
            url = "api/file?filename=" + filepath;
            fileparts = filepath.split('.');
            extension = fileparts[fileparts.length -1];
            raw_open = [
                "jpg",
                "jpeg",
                "png",
                "svg",
                "bmp",
                "webp",
                "gif"
            ]
            if (raw_open.indexOf(extension) > -1) {
                window.open(url, '_blank');
            }
            else {
                $.get(url, function(data) {
                    if (modemapping.hasOwnProperty(extension)) {
                        editor.setOption('mode', modemapping[extension]);
                    }
                    else {
                        editor.setOption('mode', "ace/mode/text");
                    }
                    editor.getSession().setValue(data, -1);
                    document.getElementById('currentfile').value = decodeURI(filepath);
                    editor.session.getUndoManager().markClean();
                    $('.markdirty').each(function(i, o){o.classList.remove('red');});
                    $('.hidesave').css('opacity', 0);
                    document.title = filenameonly + " - HASS Configurator";
                    global_current_filepath = filepath;
                    global_current_filename = filenameonly;
                    var current_file = {current_filepath: global_current_filepath,
                                        current_filename: global_current_filename}
                    localStorage.setItem('current_file', JSON.stringify(current_file));
                    check_lint();
                });
            }
        }
    }

    function closefile() {
        document.getElementById('currentfile').value='';
        editor.getSession().setValue('');
        $('.markdirty').each(function(i, o) {
            o.classList.remove('red');
        });
        localStorage.removeItem('current_file');
        global_current_filepath = null;
        global_current_filename = null;
        document.title = 'HASS Configurator';
    }

    function check_config() {
        $.get("api/check_config", function (resp) {
            if (resp.length == 0) {
                var $toastContent = $("<div><pre>Configuration seems valid.</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
            else {
                var $toastContent = $("<div><pre>" + resp[0].state + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
        });
    }

    function reload_automations() {
        $.get("api/reload_automations", function (resp) {
            var $toastContent = $("<div>Automations reloaded</div>");
            Materialize.toast($toastContent, 2000);
        });
    }

    function reload_scripts() {
        $.get("api/reload_scripts", function (resp) {
            var $toastContent = $("<div>Scripts reloaded</div>");
            Materialize.toast($toastContent, 2000);
        });
    }

    function reload_groups() {
        $.get("api/reload_groups", function (resp) {
            var $toastContent = $("<div><pre>Groups reloaded</pre></div>");
            Materialize.toast($toastContent, 2000);
        });
    }

    function reload_core() {
        $.get("api/reload_core", function (resp) {
            var $toastContent = $("<div><pre>Core reloaded</pre></div>");
            Materialize.toast($toastContent, 2000);
        });
    }

    function restart() {
        $.get("api/restart", function (resp) {
            if (resp.length == 0) {
                var $toastContent = $("<div><pre>Restarting HASS</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
            else {
                var $toastContent = $("<div><pre>" + resp + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
        });
    }

    function get_netstat() {
        $.get("api/netstat", function (resp) {
            if (resp.hasOwnProperty("allowed_networks")) {
                var allowed_list = document.getElementById("allowed_networks");
                while (allowed_list.firstChild) {
                    allowed_list.removeChild(allowed_list.firstChild);
                }
                var header = document.createElement("li");
                header.classList.add("collection-header");
                var header_h4 = document.createElement("h4");
                header_h4.innerText = "Allowed networks";
                header_h4.classList.add("grey-text");
                header_h4.classList.add("text-darken-3");
                header.appendChild(header_h4);
                allowed_list.appendChild(header);
                for (var i = 0; i < resp.allowed_networks.length; i++) {
                    var li = document.createElement("li");
                    li.classList.add("collection-item");
                    var li_div = document.createElement("div");
                    var address = document.createElement("span");
                    address.innerText = resp.allowed_networks[i];
                    li_div.appendChild(address);
                    var li_a = document.createElement("a");
                    li_a.classList.add("light-blue-text");
                    li_a.href = "#!";
                    li_a.classList.add("secondary-content");
                    var li_a_i = document.createElement("i");
                    li_a_i.classList.add("mdi");
                    li_a_i.classList.add("mdi-delete");
                    li_a_i.innerText = "Remove";
                    li_a.appendChild(li_a_i);
                    li_a.setAttribute("onclick", "helper_a_net_remove('" + resp.allowed_networks[i] + "')");
                    li_div.appendChild(li_a);
                    li.appendChild(li_div);
                    allowed_list.appendChild(li);
                }
            }
            if (resp.hasOwnProperty("banned_ips")) {
                var banlist = document.getElementById("banned_ips");
                while (banlist.firstChild) {
                    banlist.removeChild(banlist.firstChild);
                }
                var header = document.createElement("li");
                header.classList.add("collection-header");
                var header_h4 = document.createElement("h4");
                header_h4.innerText = "Banned IPs";
                header_h4.classList.add("grey-text");
                header_h4.classList.add("text-darken-3");
                header.appendChild(header_h4);
                banlist.appendChild(header);
                for (var i = 0; i < resp.banned_ips.length; i++) {
                    var li = document.createElement("li");
                    li.classList.add("collection-item");
                    var li_div = document.createElement("div");
                    var address = document.createElement("span");
                    address.innerText = resp.banned_ips[i];
                    li_div.appendChild(address);
                    var li_a = document.createElement("a");
                    li_a.classList.add("light-blue-text");
                    li_a.href = "#!";
                    li_a.classList.add("secondary-content");
                    var li_a_i = document.createElement("i");
                    li_a_i.classList.add("mdi");
                    li_a_i.classList.add("mdi-delete");
                    li_a_i.innerText = "Unban";
                    li_a.appendChild(li_a_i);
                    li_a.setAttribute("onclick", "helper_banned_unban('" + resp.banned_ips[i] + "')");
                    li_div.appendChild(li_a);
                    li.appendChild(li_div);
                    banlist.appendChild(li);
                }
            }
        });
    }

    function helper_a_net_remove(network) {
        document.getElementById("removenet").innerText = network;
        $('#modal_netstat').modal('close');
        $('#modal_a_net_remove').modal('open');
    }

    function a_net_remove() {
        var network = document.getElementById("removenet").innerText
        data = new Object();
        data.network = network;
        data.method = 'remove';
        $.post("api/allowed_networks", data).done(function(resp) {
            if (resp.error) {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 5000);
            }
            else {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
        });
    }

    function helper_a_net_add() {
        document.getElementById("addnet").innerText = document.getElementById("add_net_ip").value;
        document.getElementById("add_net_ip").value = "";
        $('#modal_netstat').modal('close');
        $('#modal_a_net_add').modal('open');
    }

    function a_net_add() {
        var network = document.getElementById("addnet").innerText
        data = new Object();
        data.network = network;
        data.method = 'add';
        $.post("api/allowed_networks", data).done(function(resp) {
            if (resp.error) {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 5000);
            }
            else {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
        });
    }

    function helper_banned_unban(ip) {
        document.getElementById("unbanip").innerText = ip;
        $('#modal_netstat').modal('close');
        $('#modal_unban').modal('open');
    }

    function banned_unban() {
        var ip = document.getElementById("unbanip").innerText
        data = new Object();
        data.ip = ip;
        data.method = 'unban';
        $.post("api/banned_ips", data).done(function(resp) {
            if (resp.error) {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 5000);
            }
            else {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
        });
    }

    function helper_banned_ban() {
        document.getElementById("banip").innerText = document.getElementById("add_banned_ip").value;
        document.getElementById("add_banned_ip").value = "";
        $('#modal_netstat').modal('close');
        $('#modal_ban').modal('open');
    }

    function banned_ban() {
        var ip = document.getElementById("banip").innerText
        data = new Object();
        data.ip = ip;
        data.method = 'ban';
        $.post("api/banned_ips", data).done(function(resp) {
            if (resp.error) {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 5000);
            }
            else {
                var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            }
        });
    }

    function save() {
        var filepath = document.getElementById('currentfile').value;
        if (filepath.length > 0) {
            data = new Object();
            data.filename = filepath;
            data.text = editor.getValue()
            $.post("api/save", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                    $('.markdirty').each(function(i, o){o.classList.remove('red');});
                    $('.hidesave').css('opacity', 0);
                    editor.session.getUndoManager().markClean();
                }
            });
        }
        else {
          Materialize.toast('Error:  Please provide a filename', 5000);
        }
    }

    function save_check() {
        var filepath = document.getElementById('currentfile').value;
        if (filepath.length > 0) {
            if (get_save_prompt()) {
                $('#modal_save').modal('open');
            }
            else {
                save();
            }
        }
        else {
            Materialize.toast('Error:  Please provide a filename', 5000);
            $(".pathtip").bind("animationend webkitAnimationEnd oAnimationEnd MSAnimationEnd", function(){
                $(this).removeClass("pathtip_color");
            }).addClass("pathtip_color");
       }
    }

    function download_file(filepath) {
        window.open("api/download?filename="+encodeURI(filepath));
    }

    function delete_file() {
        var path = document.getElementById('currentfile').value;
        if (path.length > 0) {
            data = new Object();
            data.path= path;
            $.post("api/delete", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML)
                    document.getElementById('currentfile').value='';
                    editor.setValue('');
                }
            });
        }
    }

    function exec_command() {
        var command = document.getElementById('commandline').value;
        if (command.length > 0) {
            data = new Object();
            data.command = command;
            data.timeout = 15;
            $.post("api/exec_command", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var history = document.getElementById('command_history');
                    history.innerText += resp.message + ': ' + resp.returncode + "\n";
                    if (resp.stdout) {
                        history.innerText += resp.stdout;
                    }
                    if (resp.stderr) {
                        history.innerText += resp.stderr;
                    }
                }
            });
        }
    }

    function delete_element() {
        var path = document.getElementById('fb_currentfile').value;
        if (path.length > 0) {
            data = new Object();
            data.path= path;
            $.post("api/delete", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                    if (document.getElementById('currentfile').value == path) {
                        document.getElementById('currentfile').value='';
                        editor.setValue('');
                    }
                }
            });
        }
    }

    function gitadd() {
        var path = document.getElementById('fb_currentfile').value;
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            $.post("api/gitadd", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                }
            });
        }
    }

    function gitdiff() {
        var path = document.getElementById('fb_currentfile').value;
        closefile();
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            $.post("api/gitdiff", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    editor.setOption('mode', modemapping['diff']);
                    editor.getSession().setValue(resp.message, -1);
                    editor.session.getUndoManager().markClean();
                }
            });
        }
    }

    function gitinit() {
        var path = document.getElementById("fbheader").innerHTML;
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            $.post("api/init", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                }
            });
        }
    }

    function commit(message) {
        var path = document.getElementById("fbheader").innerHTML;
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            data.message = message;
            $.post("api/commit", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                    document.getElementById('commitmessage').value = "";
                }
            });
        }
    }

    function gitpush() {
        var path = document.getElementById("fbheader").innerHTML;
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            $.post("api/push", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                }
            });
        }
    }

    function gitstash() {
        var path = document.getElementById("fbheader").innerHTML;
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            $.post("api/stash", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                    listdir(document.getElementById('fbheader').innerHTML);
                }
            });
        }
    }

    function checkout(branch) {
        var path = document.getElementById("fbheader").innerHTML;
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            data.branch = branch;
            $.post("api/checkout", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                }
            });
        }
    }

    function newbranch(branch) {
        var path = document.getElementById("fbheader").innerHTML;
        if (path.length > 0) {
            data = new Object();
            data.path = path;
            data.branch = branch;
            $.post("api/newbranch", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                }
            });
        }
    }

    function newfolder(foldername) {
        var path = document.getElementById('fbheader').innerHTML;
        if (path.length > 0 && foldername.length > 0) {
            data = new Object();
            data.path = path;
            data.name = foldername;
            $.post("api/newfolder", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                }
                listdir(document.getElementById('fbheader').innerHTML);
                document.getElementById('newfoldername').value = '';
            });
        }
    }

    function newfile(filename) {
        var path = document.getElementById('fbheader').innerHTML;
        if (path.length > 0 && filename.length > 0) {
            data = new Object();
            data.path = path;
            data.name = filename;
            $.post("api/newfile", data).done(function(resp) {
                if (resp.error) {
                    var $toastContent = $("<div><pre>" + resp.message + "\n" + resp.path + "</pre></div>");
                    Materialize.toast($toastContent, 5000);
                }
                else {
                    var $toastContent = $("<div><pre>" + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                }
                listdir(document.getElementById('fbheader').innerHTML);
                document.getElementById('newfilename').value = '';
            });
        }
    }

    function upload() {
        var file_data = $('#uploadfile').prop('files')[0];
        var form_data = new FormData();
        form_data.append('file', file_data);
        form_data.append('path', document.getElementById('fbheader').innerHTML);
        $.ajax({
            url: 'api/upload',
            dataType: 'json',
            cache: false,
            contentType: false,
            processData: false,
            data: form_data,
            type: 'post',
            success: function(resp){
                if (resp.error) {
                    var $toastContent = $("<div><pre>Error: " + resp.message + "</pre></div>");
                    Materialize.toast($toastContent, 2000);
                }
                else {
                    var $toastContent = $("<div><pre>Upload succesful</pre></div>");
                    Materialize.toast($toastContent, 2000);
                    listdir(document.getElementById('fbheader').innerHTML);
                    document.getElementById('uploadform').reset();
                }
            }
        });
    }

</script>
<script>
    ace.require("ace/ext/language_tools");
    var editor = ace.edit("editor");
    editor.on("input", function() {
        if (editor.session.getUndoManager().isClean()) {
            $('.markdirty').each(function(i, o){o.classList.remove('red');});
            $('.hidesave').css('opacity', 0);
        }
        else {
            $('.markdirty').each(function(i, o){o.classList.add('red');});
            $('.hidesave').css('opacity', 1);
        }
    });

    if (localStorage.hasOwnProperty("pochass")) {
        editor.setOptions(JSON.parse(localStorage.pochass));
        editor.setOptions({
            enableBasicAutocompletion: true,
            enableSnippets: true
        })
        editor.$blockScrolling = Infinity;
    }
    else {
        editor.getSession().setMode("ace/mode/yaml");
        editor.setOptions({
            showInvisibles: true,
            useSoftTabs: true,
            displayIndentGuides: true,
            highlightSelectedWord: true,
            enableBasicAutocompletion: true,
            enableSnippets: true
        })
        editor.$blockScrolling = Infinity;
    }

    function set_save_prompt(checked) {
        localStorage.setItem('save_prompt', JSON.stringify({save_prompt: checked}));
    }

    function get_save_prompt() {
        if (localStorage.getItem('save_prompt')) {
            var save_prompt = JSON.parse(localStorage.getItem('save_prompt'));
            return save_prompt.save_prompt;
        }
        return false;
    }

    function set_hide_filedetails(checked) {
        localStorage.setItem('hide_filedetails', JSON.stringify({hide_filedetails: checked}));
    }

    function get_hide_filedetails() {
        if (localStorage.getItem('hide_filedetails')) {
            var hide_filedetails = JSON.parse(localStorage.getItem('hide_filedetails'));
            return hide_filedetails.hide_filedetails;
        }
        return false;
    }

    function apply_settings() {
        var options = editor.getOptions();
        for (var key in options) {
            if (options.hasOwnProperty(key)) {
                var target = document.getElementById(key);
                if (target) {
                    if (typeof(options[key]) == "boolean" && target.type === 'checkbox') {
                        target.checked = options[key];
                        target.setAttribute("checked", options[key]);
                    }
                    else if (typeof(options[key]) == "number" && target.type === 'number') {
                        target.value = options[key];
                    }
                    else if (typeof(options[key]) == "string" && target.tagName == 'SELECT') {
                        target.value = options[key];
                    }
                }
            }
        }
    }

    apply_settings();

    function save_ace_settings() {
        localStorage.pochass = JSON.stringify(editor.getOptions())
        Materialize.toast("Ace Settings Saved", 2000);
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

    var foldstatus = true;

    function toggle_fold() {
        if (foldstatus) {
            editor.getSession().foldAll();
        }
        else {
            editor.getSession().unfold();
        }
        foldstatus = !foldstatus;
    }

</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/js-yaml/3.12.1/js-yaml.js" type="text/javascript" charset="utf-8"></script>
<script type="text/javascript">
var lint_timeout;
var lint_status = $('#lint-status'); // speed optimization
var lint_error = "";

function check_lint() {
    if (document.getElementById('currentfile').value.match(".yaml$")) {
        try {
            var text = editor.getValue().replace(/!(include|secret|env_var)/g,".$1"); // hack because js-yaml does not like !include/!secret
            jsyaml.safeLoad(text);
            lint_status.text("check_circle");
            lint_status.removeClass("cursor-pointer red-text grey-text");
            lint_status.addClass("green-text");
            lint_error = "";
        } catch (err) {
            lint_status.text("error");
            lint_status.removeClass("green-text grey-text");
            lint_status.addClass("cursor-pointer red-text");
            lint_error = err.message;
        }
    } else {
        lint_status.empty();
    }
}

function queue_lint(e) {
    if (document.getElementById('currentfile').value.match(".yaml$")) {
        clearTimeout(lint_timeout);
        lint_timeout = setTimeout(check_lint, 500);
        if (lint_status.text() != "cached") {
            lint_status.text("cached");
            lint_status.removeClass("cursor-pointer red-text green-text");
            lint_status.addClass("grey-text");
        }
    } else {
        lint_status.empty();
    }
}

function show_lint_error() {
    if(lint_error) {
        $("#modal_lint textarea").val(lint_error);
        $("#modal_lint").modal('open');
    }
}

editor.on('change', queue_lint);
</script>
</body>
</html>""")

# pylint: disable=unused-argument
def signal_handler(sig, frame):
    """Handle signal to shut down server."""
    global HTTPD
    LOG.info("Got signal: %s. Shutting down server", str(sig))
    HTTPD.server_close()
    sys.exit(0)

def load_settings(settingsfile):
    """Load settings from file and environment."""
    global LISTENIP, LISTENPORT, BASEPATH, SSL_CERTIFICATE, SSL_KEY, HASS_API, \
    HASS_API_PASSWORD, CREDENTIALS, ALLOWED_NETWORKS, BANNED_IPS, BANLIMIT, \
    DEV, IGNORE_PATTERN, DIRSFIRST, SESAME, VERIFY_HOSTNAME, ENFORCE_BASEPATH, \
    ENV_PREFIX, NOTIFY_SERVICE, USERNAME, PASSWORD, SESAME_TOTP_SECRET, TOTP, \
    GIT, REPO, PORT, IGNORE_SSL, HASS_WS_API
    settings = {}
    if settingsfile:
        try:
            if os.path.isfile(settingsfile):
                with open(settingsfile) as fptr:
                    settings = json.loads(fptr.read())
                    LOG.debug("Settings from file:")
                    LOG.debug(settings)
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
    GIT = settings.get("GIT", GIT)
    if GIT:
        try:
            # pylint: disable=redefined-outer-name
            from git import Repo as REPO
        except ImportError:
            LOG.warning("Unable to import Git module")
    LISTENIP = settings.get("LISTENIP", LISTENIP)
    LISTENPORT = settings.get("LISTENPORT", None)
    PORT = settings.get("PORT", PORT)
    if LISTENPORT is not None:
        PORT = LISTENPORT
    BASEPATH = settings.get("BASEPATH", BASEPATH)
    ENFORCE_BASEPATH = settings.get("ENFORCE_BASEPATH", ENFORCE_BASEPATH)
    SSL_CERTIFICATE = settings.get("SSL_CERTIFICATE", SSL_CERTIFICATE)
    SSL_KEY = settings.get("SSL_KEY", SSL_KEY)
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
    DEV = settings.get("DEV", DEV)
    IGNORE_PATTERN = settings.get("IGNORE_PATTERN", IGNORE_PATTERN)
    if IGNORE_PATTERN and not all(IGNORE_PATTERN):
        LOG.warning("Invalid value for IGNORE_PATTERN. Using empty list.")
        IGNORE_PATTERN = []
    DIRSFIRST = settings.get("DIRSFIRST", DIRSFIRST)
    SESAME = settings.get("SESAME", SESAME)
    SESAME_TOTP_SECRET = settings.get("SESAME_TOTP_SECRET", SESAME_TOTP_SECRET)
    VERIFY_HOSTNAME = settings.get("VERIFY_HOSTNAME", VERIFY_HOSTNAME)
    NOTIFY_SERVICE = settings.get("NOTIFY_SERVICE", NOTIFY_SERVICE_DEFAULT)
    IGNORE_SSL = settings.get("IGNORE_SSL", IGNORE_SSL)
    if IGNORE_SSL:
        # pylint: disable=protected-access
        ssl._create_default_https_context = ssl._create_unverified_context
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
            import pyotp
            TOTP = pyotp.TOTP(SESAME_TOTP_SECRET)
        except ImportError:
            LOG.warning("Unable to import pyotp module")
        except Exception as err:
            LOG.warning("Unable to create TOTP object: %s" % err)

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

def get_html():
    """Load the HTML from file in dev-mode, otherwise embedded."""
    if DEV:
        try:
            with open("dev.html") as fptr:
                html = Template(fptr.read())
                return html
        except Exception as err:
            LOG.warning(err)
            LOG.warning("Delivering embedded HTML")
    return INDEX

def password_problems(password, name="UNKNOWN"):
    """Rudimentary checks for password strength."""
    problems = 0
    password = str(password)
    if password is None:
        return problems
    if len(password) < 8:
        LOG.warning("Password %s is too short" % name)
        problems += 1
    if password.isalpha():
        LOG.warning("Password %s does not contain digits" % name)
        problems += 2
    if password.isdigit():
        LOG.warning("Password %s does not contain alphabetic characters" % name)
        problems += 4
    quota = len(set(password)) / len(password)
    exp = len(password) ** len(set(password))
    score = exp / quota / 8
    if score < 65536:
        LOG.warning("Password %s does not contain enough unique characters (%i)" % (
            name, len(set(password))))
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
        LOG.info("%s - %s" % (self.client_address[0], format % args))

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
                            with open(filepath, 'rb') as fptr:
                                content = fptr.read()
                            self.send_header('Content-type', mimetype[0])
                        else:
                            with open(filepath, 'rb') as fptr:
                                content += fptr.read().decode('utf-8')
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
                    if os.path.isfile(os.path.join(BASEDIR.encode('utf-8'), filename)):
                        with open(os.path.join(BASEDIR.encode('utf-8'), filename), 'rb') as fptr:
                            filecontent = fptr.read()
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
                                LOG.debug("Exception (no repo): %s" % str(err))
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
                # with urllib.request.urlopen(req) as response:
                #     print(json.loads(response.read().decode('utf-8')))
                #     res['service'] = "called successfully"
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
            html = get_html().safe_substitute(
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
                api_password=HASS_API_PASSWORD if HASS_API_PASSWORD else "")
            self.wfile.write(bytes(html, "utf8"))
            return
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
                        LOG.warning("Exception (no repo): %s" % str(err))
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
                        LOG.warning("Exception (no repo): %s" % str(err))
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
                        LOG.warning("Exception (no repo): %s" % str(err))
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
                        LOG.warning("Exception (no repo): %s" % str(err))
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
                        LOG.warning("Exception (no repo): %s" % str(err))
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
                        LOG.warning("Exception (no repo): %s" % str(err))
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
                    LOG.warning("Blocking access from %s" % self.client_address[0])
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
                    LOG.warning("Blocking access from %s" % self.client_address[0])
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
    LOG.info("%s" % data)
    try:
        with urllib.request.urlopen(req) as response:
            message = response.read().decode('utf-8')
            LOG.debug(message)
    except Exception as err:
        LOG.warning("Exception while creating notification: %s" % err)

def main(args):
    """Main function, duh!"""
    global HTTPD
    if args:
        load_settings(args[0])
    else:
        load_settings(None)
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
        LOG.warning("Exception while checking passwords: %s" % err)

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
    LOG.info('Listening on: %s://%s:%i' % ('https' if SSL_CERTIFICATE else 'http',
                                           LISTENIP,
                                           PORT))
    if BASEPATH:
        os.chdir(BASEPATH)
    HTTPD.serve_forever()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main(sys.argv[1:])
