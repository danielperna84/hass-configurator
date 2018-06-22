# HASS Configurator
[![Build Status](https://travis-ci.org/danielperna84/hass-configurator.svg?branch=master)](https://travis-ci.org/danielperna84/hass-configurator)
### Configuration UI for Home Assistant

While the configuration UI of [Home Assistant](https://home-assistant.io/) is still in development, you can use this small webapp to modify your configuration. It's essentially an embedded [Ace editor](https://ace.c9.io/), which has syntax hightlighting and automatic linting for yaml files (and a ton of other features you can turn on and off). There is also an integrated file browser to select whatever file you want to edit. When you are done with editing the file, click the save-button (or hit CTRL+s/CMD+s) and it will replace the original file.  
[JT Martinez](https://github.com/jmart518) has done a wonderful job by implementing [Material Design](http://materializecss.com/).

### Feature list:

- Web-Based editor to modify your files with syntax highlighting and automatic yaml-linting
- Upload and download files
- Lists of available triggers, events, entities, conditions and services. Selected element gets inserted into the editor at the last cursor position.
- Home Assistant event observer (connect to HASS via WebSocket and see all the events that happen)
- Restart HASS directly with the click of a button
- SSL support
- Optional authentication and IP filtering for added security
- Direct links to Home Assistant documentation and icons
- Execute shell commands
- Stage and commit changes in Git repositories, create and switch between branches, push to SSH remotes
- Customizable editor settings (saved using [localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage))

#### Screenshot HASS Configurator:
![Screenshot](https://github.com/danielperna84/hass-configurator/blob/master/screenshots/main.png)

If there is anything you want to have differently, feel free to fork and enhance. And if something is not working, create an issue here and I will have a look at it.  
_WARNING_: This tool allows you to browse your filesystem and modify files. So be careful which files you edit, or you might break critical parts of your system.

### Installation
There are no dependencies on Python modules that are not part of the standard library. And all the fancy JavaScript libraries are loaded from CDN (which means this does not work when you are offline).  
- Copy [configurator.py](https://github.com/danielperna84/hass-configurator/blob/master/configurator.py) to your HASS configuration directory (e.g /home/homeassistant/.homeassistant)
- Make it executable (`sudo chmod 755 configurator.py`)
- (Optional) Set the `GIT` variable in configurator.py to `True` if [GitPython](https://gitpython.readthedocs.io/) is installed on your system
- Execute it (`sudo ./configurator.py`)
- To terminate the process do the usual `CTRL+C`, maybe once or twice

### Configuration
Near the top of the py-file you will find some global variables you can change to customize the configurator a little bit. If you are unfamiliar with Python: when setting variables of the type _string_, you have to write that within quotation marks. The default settings are fine for just checking this out quickly. With more customized setups you will have to change some settings though.  
To keep your setting across updates it is also possible to save settings in an external file. In that case copy [settings.conf](https://github.com/danielperna84/hass-configurator/blob/master/settings.conf) whereever you like and append the full path to the file to the command when starting the configurator. E.g. `sudo .configurator.py /home/homeassistant/.homeassistant/mysettings.conf`. This file is in JSON format. So make sure it has a valid syntax (you can set the editor to JSON to get syntax highlighting for the settings). The major difference to the settings in the py-file is, that `None` becomes `null`.

#### LISTENIP (string)
The IP address the service is listening on. By default it is binding to `0.0.0.0`, which is every IPv4 interface on the system. When using `::`, all available IPv6- and IPv4-addresses will be used.
#### LISTENPORT (integer)
The port the service is listening on. By default it is using 3218, but you can change this if you need to.
#### BASEPATH (string)
It is possible to place configurator.py somewhere else. Set the `BASEPATH` to something like `"/home/homeassistant/.homeassistant"`, and no matter where you are running the configurator from, it will start serving files from there. This is needed if you plan on running the configurator with systemd.
#### ENFORCE_BASEPATH (bool)
Set ENFORCE_BASEPATH to `True` to lock the configurator into the basepath and thereby prevent it from opening files outside of the BASEPATH
#### SSL_CERTIFICATE / SSL_KEY (string)
If you're using SSL, set the paths to your SSL files here. This is similar to the SSL setup you can do in HASS.
#### HASS_API (string)
The configurator fetches some data from your running HASS instance. If the API isn't available through the default URL, modify this variable to fix this.
#### HASS_API_PASSWORD (string)
If you plan on using the restart button, you have to set your API password. Calling the restart service of HASS is prohibited without authentication.
#### CREDENTIALS (string)
Set credentials in the form of `"username:password"` if authentication should be required for access.
#### ALLOWED_NETWORKS (list)
Limit access to the configurator by adding allowed IP addresses / networks to the list, e.g `ALLOWED_NETWORKS = ["192.168.0.0/24", "172.16.47.23"]`. If you are using the [hass.io addon](https://www.home-assistant.io/addons/configurator/) of the configurator, add the docker-network `172.30.0.0/16` to this list.
#### BANNED_IPS (list)
List of statically banned IP addresses, e.g. `BANNED_IPS = ["1.1.1.1", "2.2.2.2"]`
#### BANLIMIT (integer)
Ban IPs after n failed login attempts. Restart service to reset banning. The default of `0` disables this feature. `CREDENTIALS` has to be set for this to work.
#### IGNORE_PATTERN (list)
Files and folders to ignore in the UI, e.g. `IGNORE_PATTERN = [".*", "*.log", "__pycache__"]`
#### GIT (bool)
Set this variable to `True` to enable Git integration. This feature requires [GitPython](https://gitpython.readthedocs.io)
 to be installed on the system that is running the configurator. For thechnical reasons this feature can't be enabled with a static configuration file.  
To push local commits to a remote repository, you have to add the remote manually: `git remote add origin ssh://somehost:/user/repo.git`  
Verify, that the user that is running the configurator is allowed to push without any interaction (by using SSH PubKey authentication for example).
#### DIRSFIRST (bool)
If set to `true`, directories will be displayed at the top.
#### SESAME (string)
If set to _somesecretkeynobodycanguess_, you can browse to `https://your.configurator:3218/somesecretkeynobodycanguess` from any IP, and it will be removed from the `BANNED_IPS` list (in case it has been banned before) and added to the `ALLOWED_NETWORKS` list. Once the request has been processed you will automatically be redirected to the configurator. Think of this as dynamically allowing access from untrusted IPs by providing a secret key (_open sesame!_). Keep in mind, that once the IP has been added, you will either have to restart the configurator or manually remove the IP through the _Network status_ to revoke access.
#### VERIFY_HOSTNAME (string)
HTTP requests include the hostname to which the request has been made. To improve security you can set this parameter to `yourdomain.example.com`. This will check if the hostname within the request matches the one you are expecting. If it does not match, a `403 Forbidden` response will be sent. As a result attackers that scan your IP address won't be able to connect unless they know the correct hostname. Be careful with this option though, because it prohibits you from accessing the configurator directly via IP.
 
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

### API

Starting at version 0.2.5 you can add / remove IP addresses and networks from and to the `ALLOWED_NETWORKS` and `BANNED_IPS` lists at runtime. Keep in mind though, that these changes are not persistent and will be lost when the service is restarted. The API can be used through the UI in the _Network status_ menu or by sending POST requests. A possible use case could be programmatically allowing access from your dynamic public IP, which can be required for some setups involving SSL.

#### API targets:

- `api/allowed_networks`
   #### Methods:
   - `add`
   - `remove`
   #### Example:
   - `curl -d "method=add&network=1.2.3.4" -X POST http://127.0.0.1:3218/api/allowed_networks`
- `api/banned_ips`
   #### Methods:
   - `ban`
   - `unban`
   #### Example:
   - Example: `curl -d "method=ban&ip=9.9.9.9" -X POST http://127.0.0.1:3218/api/banned_ips`

### Embedding into HASS
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

### Keeping the configurator running
Since the configurator script on its own is no service, you'll have to take some extra steps to keep it running. Here are three options (for Linux), but there are more, depending on your usecase.

1. Simple fork into the background with the command `nohup sudo ./configurator.py &`
2. If your system is using systemd (that's usually what you'll find on a Raspberry PI), there's a [template file](https://github.com/danielperna84/hass-configurator/blob/master/hass-configurator.systemd) you can use and then apply the same process to integrate it as mentioned in the [HASS documentation](https://home-assistant.io/getting-started/autostart-systemd/). If you use this method you have to set the `BASEPATH` variable according to your environment.
3. If you have [supervisor](http://supervisord.org/) running on your system, [hass-poc-configurator.supervisor](https://github.com/danielperna84/hass-configurator/blob/master/hass-configurator.supervisor) would be an example configuration you could use to control the configurator.
4. A tool called [tmux](https://tmux.github.io/), which should be pre-installed with recent AIO installers.
5. A tool called [screen](http://ss64.com/bash/screen.html). If it's not already installed on your system, you can do `sudo apt-get install screen` to get it. When it's installed, start a screen session by executing `screen`. Then navigate to your HASS directory and start the configurator like described above. Put the screen session into the background by pressing `CTRL+A` and then `CTRL+D`.
To resume the screen session, log in to your machine and execute `screen -r`.

### Docker
If you are using docker to run your homeassistant instance at home you can find corresponding docker images for the configurator on [dockerhub](https://hub.docker.com/r/causticlab/hass-configurator-docker/).
For usage visit the [repository](https://github.com/CausticLab/hass-configurator-docker)
