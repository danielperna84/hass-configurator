# hass-poc-configurator
Proof of concept confguration UI for Home Assistant

Since there currently is no nice way to edit the yaml-files HASS is using through the UI, I've code-snippet-patchworked this small webapp that lists yaml (and conf) files in the directory it's being executed in in a nice little [jsTree](https://www.jstree.com/). By clicking on an element, the file is loaded into an embedded [Ace editor](https://ace.c9.io/), which has syntax hightlighting for yaml. When done editing the file, click the save-button and you're done. Dialogs are being displayed using the [SimpleModal](http://www.ericmmartin.com/projects/simplemodal/) plug-in for jQuery.

_Update:_
I've decided to make some minor improvements to this:

1. Toolbar to toggle some editor options
2. Fetching of bootstrap-data from HASS to get available entity ids, events etc.  
Selecting one of those list items will directly insert the value at the current cursor position within the editor


This isn't designed to be pretty or complete in any way. All this is is a temporary workaround for people tired of SSH-ing into their machines. And maybe there's even someone who takes this as a reference and builds something like this directly into HASS, which would be totally awesome!
If there's anything you want to have differently, feel free to fork and enhance.

Installation is easy. There are no dependencies on Python modules that are not part of the standard library. And all the fancy JavaScript libraries are loaded from CDN (which means this doesn't work when you're offline).  
- Copy [configurator.py](https://github.com/danielperna84/hass-poc-configurator/blob/master/configurator.py) to your HASS configuration directory (e.g /home/hass/.homeassistant)
- Make it executable (`sudo chmod 755 configurator.py`)
- Execute it (`sudo ./configurator.py`)
- To terminate the process do the usual `CTRL+C`, maybe once or twice

By default the webapp listens on IP `0.0.0.0` (which is every IP the machine has) on port `3218`. If you leave it that way and you DON'T USE SSL, you can embed the configurator into HASS using a [panel_iframe](https://home-assistant.io/components/panel_iframe/):

```yaml
panel_iframe:
  configurator:
    title: Configurator
    url: http://123.123.132.132:3218
```

Since this is no service, one way to always keep this running would be to use [screen](http://ss64.com/bash/screen.html). If it's not already installed on your system, you can do `sudo apt-get install screen` to get it. When it's installed, start a screen session by executing `screen`. Then navigate to your HASS directory and start the configurator like described above. Put the screen session into the background by pressing `CTRL+A` and then `CTRL+D`.
To resume the screen session, log in to your machine and execute `screen -r`.

And here a screenshot of this thing embedded into HASS:
![Screenshot](https://github.com/danielperna84/hass-poc-configurator/blob/master/hass-poc-configurator.png)
