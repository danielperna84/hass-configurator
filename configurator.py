#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Configurator for Home Assistant.
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
from urllib.parse import urlparse, parse_qs, unquote

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
### End of options

RELEASEURL = "https://api.github.com/repos/danielperna84/hass-poc-configurator/releases/latest"
VERSION = "0.1.1"
BASEDIR = "."
DEV = False
HTTPD = None
FAIL2BAN_IPS = {}
INDEX = Template("""<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1.0" />
    <title>HASS Configurator</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.98.0/css/materialize.min.css">
    <style type="text/css" media="screen">
        body {
            margin: 0;
            padding: 0;
            background-color: #fafafa;
        }

        #editor {
            position: fixed;
            top: 68px;
            right: 0;
            bottom: 0;
          }

        @media only screen and (max-width: 600px) {
          #editor {
              top: 60px;
            }
          }

        #fbheader {
            display: block;
            cursor: initial;
            pointer-events: none;
            color: rgba(0, 0, 0, 0.54);
            font-size: 15px;
            font-weight: 500;
            line-height: 48px;
        }

        a.collection-item {
            color: #616161 !important;
        }

        .filename {
            margin-left: 15px;
            vertical-align: text-bottom;
            font-weight: 400;
        }

        .green {
            color: #fff;
        }

        .red {
            color: #fff;
        }

        #dropdown_menu, #dropdown_menu_mobile {
            min-width: 200px;
        }

        .dropdown-content li>a,
        .dropdown-content li>span {
            color: #616161 !important;
        }

        .blue_check:checked+label:before {
            border-right: 2px solid #03a9f4;
            border-bottom: 2px solid #03a9f4;
        }

        .input-field input:focus+label {
            color: #03a9f4 !important;
        }

        .row .input-field input:focus {
            border-bottom: 1px solid #03a9f4 !important;
            box-shadow: 0 1px 0 0 #03a9f4 !important
        }

        .ace_optionsMenuEntry input {
            position: relative !important;
            left: 0 !important;
            opacity: 100 !important;
        }

        .ace_optionsMenuEntry select {
            position: relative !important;
            left: 0 !important;
            opacity: 100 !important;
            display: block !important;
        }

        .collection {
            margin: 0;
        }

        .collection .collection-item {
            border-bottom: 1px solid #eeeeee;
        }

        .collection .collection-item i.material-icons {
            vertical-align: text-bottom;
        }

        #modal_acekeyboard, #modal_components {
          top: auto;
          bottom: -100%;
          margin: 0;
          width: 96%;
          min-height: 95%;
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
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ace.js" type="text/javascript" charset="utf-8"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ext-modelist.js" type="text/javascript" charset="utf-8"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ext-language_tools.js" type="text/javascript" charset="utf-8"></script>
</head>
<body>
    <div class="preloader-background">
      <div class="preloader-wrapper big active">
      <div class="spinner-layer spinner-blue">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div><div class="gap-patch">
          <div class="circle"></div>
        </div><div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
      <div class="spinner-layer spinner-red">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div><div class="gap-patch">
          <div class="circle"></div>
        </div><div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
      <div class="spinner-layer spinner-yellow">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div><div class="gap-patch">
          <div class="circle"></div>
        </div><div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
      <div class="spinner-layer spinner-green">
        <div class="circle-clipper left">
          <div class="circle"></div>
        </div><div class="gap-patch">
          <div class="circle"></div>
        </div><div class="circle-clipper right">
          <div class="circle"></div>
        </div>
      </div>
    </div>
  </div>
  <div class="main">
    <div class="navbar-fixed">
        <nav class="light-blue">
            <div class="nav-wrapper">
                <ul class="left">
                    <li><a href="#" data-activates="slide-out" class="waves-effect waves-light button-collapse show-on-large"><i class="material-icons">folder</i></a></li>
                    <li><a class="waves-effect waves-light hide-on-med-and-up" onclick="editor.execCommand('replace')"><i class="material-icons">search</i></a></li>
                </ul>
                <ul class="right">
                    <li><a class="waves-effect waves-light"href="#modal_save"><i class="material-icons">save</i></a></li>
                    <!-- <li><a class="waves-effect waves-light tooltipped hide-on-small-only" data-position="bottom" data-delay="50" data-tooltip="New" onclick="Materialize.toast('\_()_/ ', 2000)"><i class="material-icons">note_add</i></a></li>
                    <li><a class="waves-effect waves-light tooltipped hide-on-small-only" data-position="bottom" data-delay="50" data-tooltip="Save" href="#modal_save"><i class="material-icons">save</i></a></li>
                    <li><a class="waves-effect waves-light tooltipped hide-on-small-only" data-position="bottom" data-delay="50" data-tooltip="Close" href="#modal_close"><i class="material-icons">close</i></a></li>
                    <li><a class="waves-effect waves-light tooltipped hide-on-small-only" data-position="bottom" data-delay="50" data-tooltip="Delete" href="#modal_delete"><i class="material-icons">delete</i></a></li>
                    <li><a class="waves-effect waves-light tooltipped hide-on-small-only" data-position="bottom" data-delay="50" data-tooltip="Search" onclick="editor.execCommand('replace')"><i class="material-icons">search</i></a></li>
                    <li><a class="waves-effect waves-light dropdown-button hide-on-med-and-up" href="#!" data-activates="dropdown_tools_mobile" data-beloworigin="true"><i class="material-icons right">edit</i></a></li> -->
                    <li><a class="waves-effect waves-light hide-on-small-only" onclick="editor.execCommand('replace')"><i class="material-icons">search</i></a></li>
                    <li><a class="waves-effect waves-light dropdown-button hide-on-small-only" href="#!" data-activates="dropdown_menu" data-beloworigin="true"><i class="material-icons right">more_vert</i></a></li>
                    <li><a class="waves-effect waves-light dropdown-button hide-on-med-and-up" href="#!" data-activates="dropdown_menu_mobile" data-beloworigin="true"><i class="material-icons right">more_vert</i></a></li>
                </ul>
            </div>
        </nav>
    </div>
    <ul id="dropdown_tools_mobile" class="dropdown-content z-depth-4">
        <li><a onclick="Materialize.toast('\_()_/ ', 2000)">New</a></li>
        <li><a href="#modal_save">Save</a></li>
        <li><a href="#modal_close">Close</a></li>
        <li class="divider"></li>
        <li><a href="#modal_delete">Delete</a></li>
    </ul>
    <ul id="dropdown_menu" class="dropdown-content z-depth-4">
        <li><a target="_blank" href="#modal_components">HASS Components</a></li>
        <li><a href="#" data-activates="ace_settings" class="ace_settings-collapse">Editor Settings</a></li>
        <li><a href="#modal_about">About PoC</a></li>
        <li class="divider"></li>
        <li><a href="#modal_restart">Restart HASS</a></li>
    </ul>
    <ul id="dropdown_menu_mobile" class="dropdown-content z-depth-4">
        <li><a target="_blank" href="https://home-assistant.io/help/">Need HASS Help?</a></li>
        <li><a target="_blank" href="https://home-assistant.io/components/">HASS Components</a></li>
        <li><a href="#" data-activates="ace_settings" class="ace_settings-collapse">Editor Settings</a></li>
        <li><a href="#modal_about">About PoC</a></li>
        <li class="divider"></li>
        <li><a href="#modal_restart">Restart HASS</a></li>
    </ul>
    <div id="modal_components" class="modal bottom-sheet modal-fixed-footer">
        <div class="modal-content_nopad">
            <iframe src="https://home-assistant.io/components/" width="100%" style="height: 90vh;"> </iframe>
        </div>
        <div class="modal-footer">
            <a href="#!" class="modal-action modal-close waves-effect waves-blue btn-flat ">Close</a>
        </div>
      </div>
    </div>
    <div id="modal_acekeyboard" class="modal bottom-sheet modal-fixed-footer">
        <div class="modal-content centered">
        <h4>Ace Keyboard Shortcuts</h4>
        </br>
        <ul class="collapsible popout" data-collapsible="expandable">
          <li>
            <div class="collapsible-header hoverable"><i class="material-icons">view_headline</i>Line Operations</div>
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
            <div class="collapsible-header hoverable"><i class="material-icons">photo_size_select_small</i>Selection</div>
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
            <div class="collapsible-header hoverable"><i class="material-icons">multiline_chart</i>Multicursor</div>
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
            <div class="collapsible-header hoverable"><i class="material-icons">call_missed_outgoing</i>Go To</div>
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
            <div class="collapsible-header hoverable"><i class="material-icons">find_replace</i>Find/Replace</div>
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
            <div class="collapsible-header hoverable"><i class="material-icons">all_out</i>Folding</div>
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
            <div class="collapsible-header hoverable"><i class="material-icons">devices_other</i>Other</div>
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
        <a href="#!" class="modal-action modal-close waves-effect waves-blue btn-flat ">Close</a>
      </div>
    </div>
    <div id="modal_save" class="modal">
        <div class="modal-content">
            <h4>Save</h4>
            <p>Do you really want to save?</p>
        </div>
        <div class="modal-footer"> <a href="#!" class=" modal-action modal-close waves-effect waves-red btn-flat">No</a> <a onclick="save()" class=" modal-action modal-close waves-effect waves-green btn-flat">Yes</a> </div>
    </div>
    <div id="modal_close" class="modal">
        <div class="modal-content">
            <h4>Close File</h4>
            <p>Are you sure you want to close the current file without saving?</p>
        </div>
        <div class="modal-footer"> <a href="#!" class=" modal-action modal-close waves-effect waves-red btn-flat">No</a> <a onclick="Materialize.toast('\_()_/ ', 2000)" class="modal-action modal-close waves-effect waves-green btn-flat">Yes</a> </div>
    </div>
    <div id="modal_delete" class="modal">
        <div class="modal-content">
            <h4>Delete</h4>
            <p>Are you sure you want to delete this file?</p>
        </div>
        <div class="modal-footer"> <a href="#!" class=" modal-action modal-close waves-effect waves-red btn-flat">No</a> <a onclick="Materialize.toast('\_()_/ ', 2000)" class="modal-action modal-close waves-effect waves-green btn-flat">Yes</a> </div>
    </div>
    <div id="modal_restart" class="modal">
        <div class="modal-content">
            <h4>Restart</h4>
            <p>Do you really want to restart HASS?</p>
        </div>
        <div class="modal-footer"> <a href="#!" class=" modal-action modal-close waves-effect waves-red btn-flat">No</a> <a onclick="restart()" class=" modal-action modal-close waves-effect waves-green btn-flat">Yes</a> </div>
    </div>
    <div id="modal_about" class="modal modal-fixed-footer">
        <div class="modal-content">
            <h4><a class="black-text" href="https://github.com/danielperna84/hass-poc-configurator/" target="_blank">HASS Configurator</a></h4>
            <p>Version: <a class="$versionclass" href="https://github.com/danielperna84/hass-poc-configurator/releases/latest" target="_blank">$current</a></p>
            <p>Web-based file editor designed to modify configuration files of <a class="light-blue-text" href="https://home-assistant.io/" target="_blank">Home Assistant</a> or other textual files. Use at your own risk.</p>
            <p>Published under the MIT license</p>
            <p>Developed by:</p>
            <ul>
                <li>
                    <div class="chip"> <img src="https://avatars3.githubusercontent.com/u/7396998?v=3&s=400" alt="Contact Person"> <a class="black-text" href="https://github.com/danielperna84" target="_blank">Daniel Perna</a> </div>
                </li>
                <li>
                    <div class="chip"> <img src="https://avatars2.githubusercontent.com/u/1509640?v=3&s=460" alt="Contact Person"> <a class="black-text" href="https://github.com/jmart518" target="_blank">JT Martinez</a> </div>
                </li>
            </ul>
            <p>Libraries used:</p>
            <ul>
                <li><a class="light-blue-text" href="https://ace.c9.io/" target="_blank">Ace</a></li>
                <li><a class="light-blue-text" href="http://materializecss.com/" target="_blank">MaterializeCSS</a></li>
                <li><a class="light-blue-text" href="https://jquery.com/" target="_blank">jQuery</a></li>
            </ul>
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
      <div class="col s12 m8 l9" id="editor"></div>
    </div>
    <div>
        <ul id="slide-out" class="side-nav grey lighten-4">
          <div class="z-depth-1" id="filebrowser"></div>
            <div class="row hide-on-med-and-up">
              </br>
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
            </div>
            <div class="row hide-on-med-and-up">
              <div class="input-field col s12">
                  <select id="events_side" onchange="insert(this.value)"> </select>
                  <label>Events</label>
              </div>
            </div>
            <div class="row hide-on-med-and-up">
              <div class="input-field col s12">
                  <select id="entities_side" onchange="insert(this.value)"> </select>
                  <label>Entities</label>
              </div>
            </div>
            <div class="row hide-on-med-and-up">
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
            <div class="row hide-on-med-and-up">
              <div class="input-field col s12">
                  <select id="services_side" onchange="insert(this.value)"> </select>
                  <label>Services</label>
              </div>
            </div>
        </ul>
        <div class="fixed-action-btn vertical click-to-toggle">
  <a class="btn-floating btn-large red hoverable">
    <i class="material-icons">edit</i>
  </a>
  <ul>
    <li><a class="btn-floating yellow tooltipped" data-position="left" data-delay="50" data-tooltip="Undo" onclick="editor.execCommand('undo')"><i class="material-icons">undo</i></a></li>
    <li><a class="btn-floating green tooltipped" data-position="left" data-delay="50" data-tooltip="Redo" onclick="editor.execCommand('redo')"><i class="material-icons">redo</i></a></li>
    <li><a class="btn-floating blue tooltipped" data-position="left" data-delay="50" data-tooltip="Indent" onclick="editor.execCommand('indent')"><i class="material-icons">format_indent_increase</i></a></li>
    <li><a class="btn-floating orange tooltipped" data-position="left" data-delay="50" data-tooltip="Outdent" onclick="editor.execCommand('outdent')"><i class="material-icons">format_indent_decrease</i></a></li>
    <li><a class="btn-floating brown tooltipped" data-position="left" data-delay="50" data-tooltip="Fold" onclick="toggle_fold()"><i class="material-icons">all_out</i></a></li>
  </ul>
</div>

    </div>
    <div class="row">
        <ul id="ace_settings" class="side-nav">
            <li><a class="center grey lighten-3 z-depth-1 subheader">Editor Settings</a></li>
            <form class="row col s12" action="#">
                <p class="col s12"> <a class="waves-effect waves-light btn light-blue" href="#modal_acekeyboard">Keyboard Shortcuts</a> </p>
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
                <p class="center col s12"> Ace Editor 1.2.6 </p>
            </form>
        </ul>
    </div>
    <input type="hidden" id="currentfile" value="" />
  </div>
</body>
<!--  Scripts-->
<script src="https://code.jquery.com/jquery-2.1.1.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.98.0/js/materialize.min.js"></script>
<script type="text/javascript">
    $(document).ready(function () {
        $('select').material_select();
        $('.modal').modal();
        $('.collapsible').collapsible();
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
            closeOnClick: false,
            draggable: true
        });
        $('.ace_settings-collapse').sideNav({
            menuWidth: 320, // Default is 300
            edge: 'right', // Choose the horizontal origin
            closeOnClick: true, // Closes side-nav on <a> clicks, useful for Angular/Meteor
            draggable: true // Choose whether you can drag to open on touch screens
        });
        listdir('.');
    });
</script>
<script type="text/javascript">
    document.addEventListener("DOMContentLoaded", function(){
	     $('.preloader-background').delay(800).fadeOut('slow');

	      $('.preloader-wrapper')
		      .delay(800)
		      .fadeOut('slow');
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
        var options = $('#entities option');
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
        var options = $('#services option');
        var arr = options.map(function (_, o) {
            return {
                t: $(o).text(), v: o.value
            };
        }).get();
        arr.sort(function (o1, o2) {
            var t1 = o1.t.toLowerCase(),
                t2 = o2.t.toLowerCase();
            return t1 > t2 ? 1 : t1 < t2 ? -1 : 0;
        });
        options.each(function (i, o) {
            o.value = arr[i].v;
            $(o).text(arr[i].t);
        });
    }
    function listdir(path) {
        $.get(encodeURI("api/listdir?path=" + path), function(data) {
            renderpath(data);
        });
    }

    function renderitem(itemdata) {
        var item = document.createElement('a');
        item.classList.add('collection-item');
        item.href = '#';
        var iicon = document.createElement('i');
        iicon.classList.add('material-icons');
        if (itemdata.type == 'dir') {
            iicon.innerHTML = 'folder';
            item.setAttribute("onclick", "listdir('" + encodeURI(itemdata.fullpath) + "')");
        }
        else {
            iicon.innerHTML = 'insert_drive_file';
            item.setAttribute("onclick", "loadfile('" + encodeURI(itemdata.fullpath) + "')");
        }
        item.appendChild(iicon);
        var itext = document.createElement('span');
        itext.innerHTML = itemdata.name;
        itext.classList.add('filename');
        item.appendChild(itext);
        return item;
    }

    function renderpath(dirdata) {
        var filebrowser = document.getElementById("filebrowser");
        while (filebrowser.firstChild) {
            filebrowser.removeChild(filebrowser.firstChild);
        }
        var collection = document.createElement('div');
        collection.classList.add('collection');
        collection.classList.add('with-header');
        var fbheader = document.createElement('span');
        fbheader.innerHTML = dirdata.abspath;
        fbheader.classList.add('collection-header');
        fbheader.id = 'fbheader';
        collection.appendChild(fbheader);
        var up = document.createElement('a');
        up.classList.add('collection-item');
        up.href = '#';
        up.id = "uplink";
        up.setAttribute("onclick", "listdir('" + encodeURI(dirdata.parent) + "')")
        var upicon = document.createElement('i');
        upicon.classList.add('material-icons');
        upicon.innerHTML = 'folder';
        up.appendChild(upicon);
        var uptext = document.createElement('span');
        uptext.innerHTML = '..';
        uptext.classList.add('filename');
        up.appendChild(uptext);
        collection.appendChild(up);

        for (var i = 0; i < dirdata.content.length; i++) {
            collection.appendChild(renderitem(dirdata.content[i]));
        }

        filebrowser.appendChild(collection);
    }

    function loadfile(filepath) {
        $.get("api/file?filename=" + filepath, function(data) {
            editor.setValue(data);
            editor.selection.selectFileStart();
            editor.focus();
            document.getElementById('currentfile').value = filepath;
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

    function save() {
        var filepath = document.getElementById('currentfile').value;
        if (filepath.length > 0) {
            data = new Object();
            data.filename = filepath;
            data.text = editor.getValue()
            $.post("api/save", data).done(function(resp) {
                var $toastContent = $("<div><pre>" + resp + "</pre></div>");
                Materialize.toast($toastContent, 2000);
            });
        }
    }
</script>
<script>
    ace.require("ace/ext/language_tools");
    var editor = ace.edit("editor");
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
        // Not used for now. We'll put a few buttons on top of the editor -> Toolbar. (Search, folding etc.)
        if (foldstatus) {
            editor.getSession().foldAll();
        }
        else {
            editor.getSession().unfold();
        }
        foldstatus = !foldstatus;
    }

</script>
</html>""")

def signal_handler(signal, frame):
    global HTTPD
    print("Shutting down server")
    HTTPD.server_close()
    sys.exit(0)

def load_settings(settingsfile):
    global LISTENIP, LISTENPORT, BASEPATH, SSL_CERTIFICATE, SSL_KEY, HASS_API, \
    HASS_API_PASSWORD, CREDENTIALS, ALLOWED_NETWORKS, BANNED_IPS, BANLIMIT
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
    except Exception as err:
        print(err)
        print("Not loading static settings")
    return False

def get_dircontent(path):
    dircontent = []
    for e in sorted(os.listdir(path), key=lambda x: x.lower()):
        edata = {}
        edata['name'] = e
        edata['dir'] = path
        edata['fullpath'] = os.path.abspath(os.path.join(path, e))
        edata['type'] = 'dir' if os.path.isdir(edata['fullpath']) else 'file'
        try:
            stats = os.stat(os.path.join(path, e))
            edata['size'] = stats.st_size
            edata['modified'] = stats.st_mtime
        except Exception:
            edata['size'] = 0
            edata['modified'] = 0
        dircontent.append(edata)

    return dircontent

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
        if req.path == '/api/file':
            content = ""
            self.send_header('Content-type','text/text')
            self.end_headers()
            filename = query.get('filename', None)
            try:
                if filename:
                    filename = unquote(filename[0]).encode('utf-8')
                    print(filename)
                    if os.path.isfile(os.path.join(BASEDIR.encode('utf-8'), filename)):
                        with open(os.path.join(BASEDIR.encode('utf-8'), filename)) as fptr:
                            content += fptr.read()
                    else:
                        content = "File not found"
            except Exception as err:
                print(err)
                content = str(err)
            self.wfile.write(bytes(content, "utf8"))
            return
        elif req.path == '/api/listdir':
            content = ""
            self.send_header('Content-type','text/json')
            self.end_headers()
            dirpath = query.get('path', None)
            try:
                if dirpath:
                    dirpath = unquote(dirpath[0]).encode('utf-8')
                    if os.path.isdir(dirpath):
                        dircontent = get_dircontent(dirpath.decode('utf-8'))
                        filedata = {'content': dircontent,
                            'abspath': os.path.abspath(dirpath).decode('utf-8'),
                            'parent': os.path.dirname(os.path.abspath(dirpath)).decode('utf-8')
                        }
                        self.wfile.write(bytes(json.dumps(filedata), "utf8"))
            except Exception as err:
                print(err)
                content = str(err)
                self.wfile.write(bytes(content, "utf8"))
            return
        elif req.path == '/api/abspath':
            content = ""
            self.send_header('Content-type','text/text')
            self.end_headers()
            dirpath = query.get('path', None)
            if dirpath:
                dirpath = unquote(dirpath[0]).encode('utf-8')
                print(dirpath)
                absp = os.path.abspath(dirpath)
                print(absp)
                if os.path.isdir(dirpath):
                    self.wfile.write(os.path.abspath(dirpath))
            return
        elif req.path == '/api/parent':
            content = ""
            self.send_header('Content-type','text/text')
            self.end_headers()
            dirpath = query.get('path', None)
            if dirpath:
                dirpath = unquote(dirpath[0]).encode('utf-8')
                print(dirpath)
                absp = os.path.abspath(dirpath)
                print(absp)
                if os.path.isdir(dirpath):
                    self.wfile.write(os.path.abspath(os.path.dirname(dirpath)))
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
            html = get_html().safe_substitute(bootstrap=boot, current=VERSION, versionclass=color, separator="\%s" % os.sep if os.sep == "\\" else os.sep)
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
        req = urlparse(self.path)
        postvars = {}
        response = {
            "error": True,
            "message": "Generic failure"
        }
        
        try:
            length = int(self.headers['content-length'])
            postvars = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=1)
            interror = False
        except Exception as err:
            print(err)
            response['message'] = "%s" % (str(err))
            interror = True

        if not interror:
            if req.path == '/api/save':
                if 'filename' in postvars.keys() and 'text' in postvars.keys():
                    if postvars['filename'] and postvars['text']:
                        try:
                            filename = unquote(postvars['filename'][0])
                            response['file'] = filename
                            with open(filename, 'wb') as fptr:
                                fptr.write(bytes(postvars['text'][0], "utf-8"))
                            self.send_response(200)
                            self.send_header('Content-type','text/json')
                            self.end_headers()
                            response['error'] = False
                            response['message'] = "File saved successfully"
                            self.wfile.write(bytes(json.dumps(response), "utf8"))
                            return
                        except Exception as err:
                            response['message'] = "%s" % (str(err))
                            print(err)
                else:
                    response['message'] = "Missing filename or text"
            elif req.path == '/api/delete':
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
                                self.send_header('Content-type','text/json')
                                self.end_headers()
                                response['error'] = False
                                response['message'] = "Deletetion successful"
                                self.wfile.write(bytes(json.dumps(response), "utf8"))
                                return
                            except Exception as err:
                                print(err)
                                response['error'] = True
                                response['message'] = str(err)
                              

                        except Exception as err:
                            response['message'] = "%s" % (str(err))
                            print(err)
                else:
                    response['message'] = "Missing filename or text"
            elif req.path == '/api/newfolder':
                if 'path' in postvars.keys() and 'name' in postvars.keys():
                    if postvars['path'] and postvars['name']:
                        try:
                            basepath = unquote(postvars['path'][0])
                            name = unquote(postvars['name'][0])
                            response['path'] = os.path.join(basepath, name)
                            try:
                                os.makedirs(response['path'])
                                self.send_response(200)
                                self.send_header('Content-type','text/json')
                                self.end_headers()
                                response['error'] = False
                                response['message'] = "Folder created"
                                self.wfile.write(bytes(json.dumps(response), "utf8"))
                                return
                            except Exception as err:
                                print(err)
                                response['error'] = True
                                response['message'] = str(err)
                              

                        except Exception as err:
                            response['message'] = "%s" % (str(err))
                            print(err)
                else:
                    response['message'] = "Missing filename or text"
            else:
                response['message'] = "Invalid method"
        self.send_response(200)
        self.send_header('Content-type','text/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(response), "utf8"))
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
