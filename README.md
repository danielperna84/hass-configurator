# HASS Configurator
###Configuration UI for Home Assistant

Since there currently is no nice way to edit the yaml-files HASS is using through the HASS frontend, I've code-snippet-patchworked this small webapp. It's essentially an embedded [Ace editor](https://ace.c9.io/), which has syntax hightlighting for yaml (and a ton of other features you can turn on and off). Of course there's also an integrated file browser to select whatever file you want to edit. When you're done with editing the file, click the save-button and it will replace the original.  
Thanks to the help of [JT Martinez](https://github.com/jmart518) this tool now presents itself in [Material Design](http://materializecss.com/).

###Feature list:

- Web-Based editor to modify your files with syntax highlighting
- Lists of available triggers, events, entities, conditions and services. Selected element gets inserted into the editor at the last cursor position.
- Restart HASS directly with the click of a button (API-password required)
- SSL support
- Optional authentication and IP filtering for added security
- Direct links to HASS documentation
- Modified editor settings can be saved using [localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)

####Screenshot of the configurator embedded into HASS:
![Screenshot](https://github.com/danielperna84/hass-poc-configurator/blob/master/hass-poc-configurator.png)

If there's anything you want to have differently, feel free to fork and enhance. And if something is not working, create an issue here and I'll have a look at it.

###Installation
There are no dependencies on Python modules that are not part of the standard library. And all the fancy JavaScript libraries are loaded from CDN (which means this doesn't work when you're offline).  
- Copy [configurator.py](https://github.com/danielperna84/hass-poc-configurator/blob/master/configurator.py) to your HASS configuration directory (e.g /home/hass/.homeassistant)
- Make it executable (`sudo chmod 755 configurator.py`)
- Execute it (`sudo ./configurator.py`)
- To terminate the process do the usual `CTRL+C`, maybe once or twice

###Configuration
Near the top of the py-file you'll find some global variables you can change to customize the configurator a little bit. If you're unfamiliar with Python: when setting variables of the type _string_, you have to write that within quotation marks. The default settings are fine for just checking this out quickly. With more customized setups you'll have to change some settings though.  
To keep your setting across updates it is also possible to save settings in an external file. In that case copy [settings.conf](https://github.com/danielperna84/hass-poc-configurator/blob/master/settings.conf) whereever you like and append the full path to the file to the command when starting the configurator. E.g. `sudo .configurator.py /home/hass/.homeassistant/mysettings.conf`. This file is in JSON format. So make sure it has a valid syntax (you can set the editor to JSON to get syntax highlighting for the settings). The major difference to the settings in the py-file is, that `None` becomes `null`.

####LISTENIP (string)
The IP the service is listening on. By default it's binding to `0.0.0.0`, which is every interface on the system.
####LISTENPORT (integer)
The port the service is listening on. By default it's using 3218, but you can change this if you need to.
####BASEPATH (string)
It is possible to place configurator.py somewhere else. Set the `BASEPATH` to something like `"/home/hass/.homeassistant"`, and no matter where you're running the configurator from, it will start serving files from there. This is needed if you plan on running the configurator with systemd.
####SSL_CERTIFICATE / SSL_KEY (string)
If you're using SSL, set the paths to your SSL files here. This is similar to the SSL setup you can do in HASS.
####HASS_API (string)
The configurator fetches some data from your running HASS instance. If the API isn't available through the default URL, modify this variable to fix this.
####HASS_API_PASSWORD (string)
If you plan on using the restart button, you have to set your API password. Calling the restart service of HASS is prohibited without authentication.
####CREDENTIALS (string)
Set credentials in the form of `"username:password"` if authentication should be required for access.
####ALLOWED_NETWORKS (list)
Limit access to the configurator by adding allowed IP addresses / networks to the list, e.g `ALLOWED_NETWORKS = ["192.168.0.0/24", "172.16.47.23"]`
####BANNED_IPS (list)
List of statically banned IP addresses, e.g. `BANNED_IPS = ["1.1.1.1", "2.2.2.2"]`
####BANLIMIT (integer)
Ban IPs after n failed login attempts. Restart service to reset banning. The default of `0` disables this feature. `CREDENTIALS` has to be set for this to work.

__Note regarding `ALLOWED_NETWORKS`, `BANNED_IPS` and `BANLIMIT`__:  
The way this is implemented works in the following order:

1. (Only if `CREDENTIALS` is set) Check credentials
  - Failure: Retry `BANLIMIT` times, after that return error 420 (unless you try again without any authentication headers set, e.g. private tab of your browser)
  - Success: Continue
2. Check if client IP address is in `BANNED_IPS`
  - Yes: Return error 420
  - No: Continue
3. Check if client IP address is in `ALLOWED_NETWORKS`
  - No: Return error 420
  - Yes: Continue and display UI of configurator

###Embedding into HASS
HASS has the [panel_iframe](https://home-assistant.io/components/panel_iframe/) component. With this it is possible to embed the configurator directly into HASS, allowing you to modify your configuration through the HASS frontend.  
An example configuration would look like this:

```yaml
panel_iframe:
  configurator:
    title: Configurator
    icon: mdi:wrench
    url: http://123.123.132.132:3218
```
__IMPORTANT__: Be careful when setting up port forwarding to the configurator while embedding into HASS. If you don't restrict access by requiring authentication and / or blocking based on client IP addresses, your configuration will be exposed to the web!

###Keeping the configurator running
Since the configurator script on its own is no service, you'll have to take some extra steps to keep it running. Here are three options (for Linux), but there are more, depending on your usecase.

1. Simple fork into the background with the command `nohup sudo ./configurator.py &`
2. If your system is using systemd (that's usually what you'll find on a Raspberry PI), there's a [template file](https://github.com/danielperna84/hass-poc-configurator/blob/master/hass-poc-configurator.systemd) you can use and then apply the same process to integrate it as mentioned in the [HASS documentation](https://home-assistant.io/getting-started/autostart-systemd/). If you use this method you have to set the `BASEPATH` variable according to your environment.
3. A tool called [screen](http://ss64.com/bash/screen.html). If it's not already installed on your system, you can do `sudo apt-get install screen` to get it. When it's installed, start a screen session by executing `screen`. Then navigate to your HASS directory and start the configurator like described above. Put the screen session into the background by pressing `CTRL+A` and then `CTRL+D`.
To resume the screen session, log in to your machine and execute `screen -r`.
