# HASS Configurator
[![Build Status](https://travis-ci.org/danielperna84/hass-configurator.svg?branch=master)](https://travis-ci.org/danielperna84/hass-configurator)
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fdanielperna84%2Fhass-configurator.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fdanielperna84%2Fhass-configurator?ref=badge_shield)
### Configuration UI for Home Assistant

The HASS-Configurator is a small webapp (you access it via web browser) that provides a filesystem-browser and text-editor to modify files on the machine the configurator is running on. It has been created to allow easy configuration of [Home Assistant](https://home-assistant.io/). It is powered by [Ace editor](https://ace.c9.io/), which supports syntax highlighting for various code/markup languages. [YAML](https://en.wikipedia.org/wiki/YAML) files (the default language for Home Assistant configuration files) will be automatically checked for syntax errors while editing.  
__IMPORTANT:__ The configurator fetches JavaScript libraries, CSS and fonts from CDNs. Hence it does __NOT__ work when your client device is offline. And it is only available for __Python 3__.

### Feature list:

- Web-Based editor to modify your files with syntax highlighting and automatic yaml-linting
- Upload and download files
- Lists of available triggers, events, entities, conditions and services. Selected element gets inserted into the editor at the last cursor position.
- Home Assistant event observer (connect to Home Assistant via WebSocket and see all the events that happen)
- Restart Home Assistant directly with the click of a button
- SSL support
- Optional authentication and IP filtering for added security
- Direct links to Home Assistant documentation and icons
- Execute shell commands
- Stage and commit changes in Git repositories, create and switch between branches, push to SSH remotes
- Customizable editor settings (saved using [localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage))
- Standalone mode that hides the Home Assistant related panel on the left side (triggers, entities etc.). Set `HASS_API` to `None` or use the commandline flag `-s` / `--standalone` to enable this mode.

#### Screenshot HASS Configurator:
![Screenshot](https://github.com/danielperna84/hass-configurator/blob/master/screenshots/main.png)

If there is anything you want to have differently, feel free to fork and enhance. And if something is not working, create an issue here and I will have a look at it.  
_WARNING_: This tool allows you to browse your filesystem and modify files. So be careful which files you edit, or you might break critical parts of your system.

### Installation
Possible methods to install the configurator are documented in the Wiki: [Installation](https://github.com/danielperna84/hass-configurator/wiki/Installation)

### Configuration
Available options to customize the behaviour of the configurator are documented in the Wiki: [Configuration](https://github.com/danielperna84/hass-configurator/wiki/Configuration)

### Keeping the configurator running
Since the configurator script on its own is no service, you'll have to take some extra steps to keep it running. More information on this topic can be found in the Wiki: [Daemonizing](https://github.com/danielperna84/hass-configurator/wiki/Daemonizing)

### API

There is an API available to programmatically add and remove IP addresses / networks to and from `ALLOWED_NETWORKS` and `BANNED_IPS`. Usage is documented in the Wiki: [API](https://github.com/danielperna84/hass-configurator/wiki/API)

### Embedding into Home Assistant
Once you have properly set up the configurator, you can use the [panel_iframe](https://home-assistant.io/components/panel_iframe/) component of Home Assistant to embed the configurator directly into the Home Assistant UI.  
An example configuration would look like this:

```yaml
panel_iframe:
  configurator:
    title: Configurator
    icon: mdi:wrench
    url: http://1.2.3.4:3218
```
__IMPORTANT__: Be careful when setting up port forwarding to the configurator while embedding into Home Assistant. If you don't restrict access by requiring authentication and / or blocking based on client IP addresses, your configuration will be exposed to the web!


## License
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fdanielperna84%2Fhass-configurator.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2Fdanielperna84%2Fhass-configurator?ref=badge_large)