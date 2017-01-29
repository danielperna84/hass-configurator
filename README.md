# hass-poc-configurator
###Proof of concept configuration UI for Home Assistant

Since there currently is no nice way to edit the yaml-files HASS is using through the HASS frontend, I've code-snippet-patchworked this small webapp that lists yaml (and conf) files in the directory it's being executed in in a nice little [jsTree](https://www.jstree.com/). By clicking on an element, the file is loaded into an embedded [Ace editor](https://ace.c9.io/), which has syntax hightlighting for yaml. When done editing the file, click the save-button and you're done. Dialogs are being displayed using the [SimpleModal](http://www.ericmmartin.com/projects/simplemodal/) plug-in for jQuery.

###Feature list:

- Web-Based editor to modify your yaml (and conf) files with syntax highlighting
- Lists of available triggers, events, entities, conditions and services. Selected element gets inserted into the editor at the last cursor position.
- Toggle displaying of whitespace
- Fold / Unfold the content for better overview
- Highlight selected word to see where else it's being used
- Restart HASS directly with the click of a button (API-password required)
- Direct links to HASS documentation
- SSL support (configuration required)

####Screenshot of the configurator embedded into HASS:
![Screenshot](https://github.com/danielperna84/hass-poc-configurator/blob/master/hass-poc-configurator.png)

This isn't designed to be pretty or complete in any way. It is a workaround for people tired of SSH-ing into their machines. And maybe there's even someone who takes this as a reference and builds something like this directly into HASS, which would be totally awesome!
If there's anything you want to have differently, feel free to fork and enhance.

###Installation
There are no dependencies on Python modules that are not part of the standard library. And all the fancy JavaScript libraries are loaded from CDN (which means this doesn't work when you're offline).  
- Copy [configurator.py](https://github.com/danielperna84/hass-poc-configurator/blob/master/configurator.py) to your HASS configuration directory (e.g /home/hass/.homeassistant)
- Make it executable (`sudo chmod 755 configurator.py`)
- Execute it (`sudo ./configurator.py`)
- To terminate the process do the usual `CTRL+C`, maybe once or twice

###Configuration
Near the top of the py-file you'll find some global variables you can change to customize the configurator a little bit.

####LISTENIP
The IP the service is listening on. By default it's binding to `0.0.0.0`, which is every interface on the system.
####LISTENPORT
The port the service is listening on. By default it's using 3218, but you can change this if you need to.
####BASEPATH
__On Linux systems__ it is possible to place configurator.py somewhere else. Set the `BASEPATH` to something like `"/home/hass/.homeassistant"`, and no matter where you're running the configurator from, it will [chroot](https://linux.die.net/man/1/chroot) into that directory and start serving files from there.
####SSL_CERTIFICATE / SSL_KEY
If you're using SSL, set the paths to your SSL files here. This is similar to the SSL setup you can do in HASS.
####HASS_API
The configurator fetches some data from your running HASS instance. If the API isn't available through the default URL, modify this variable to fix this.
####HASS_API_PASSWORD
If you plan on using the restart button, you have to set your API password. Calling the restart service of HASS is prohibited without authentication.

###Embedding into HASS
HASS has the [panel_iframe](https://home-assistant.io/components/panel_iframe/) component. With this it is possible to embed the configurator directly into HASS, allowing you to modify your configuration through the HASS frontend. An example configuration would look like this:

```yaml
panel_iframe:
  configurator:
    title: Configurator
    icon: mdi:wrench
    url: http://123.123.132.132:3218
```

####Keeping the configurator running
Since this is no service, one way to always keep this running (on Linux at least) would be to use [screen](http://ss64.com/bash/screen.html). If it's not already installed on your system, you can do `sudo apt-get install screen` to get it. When it's installed, start a screen session by executing `screen`. Then navigate to your HASS directory and start the configurator like described above. Put the screen session into the background by pressing `CTRL+A` and then `CTRL+D`.
To resume the screen session, log in to your machine and execute `screen -r`.
