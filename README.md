![logo](https://github.com/user-attachments/assets/65b8b825-56c5-41db-8d95-6bdddef1ddf2)

# README

Home Assistant Molekule Integration

Version: 0.1.13-beta

### Description

This integration provides support for Molekule devices directly integrated into Home Assistant.  (Currently only Molekule Air Pro & Molekule Air).

[Note: Molekule Air less tested!]

This relies on the cloud, it talks directly to Molekule's web api.

This will show sensors for: 

* Air Quality
* VOC
* Humidity
* PM2.5
* PM10
* CO2
* Air Filter life.

This will add a fan entity that will allow you to: 

* Control Mode (Automatic / Manual)
* Control Fan Speed 

There is configuration for:

* How often to poll Molekule's api
* Whether or not for enable "Quiet" (aka Silent) mode when the unit is set to Automatic

### Installation
First add this repository [as a custom repository](https://hacs.xyz/docs/faq/custom_repositories/).

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=molekule)



### Notes

* Pull Requests and Issues are welcome.
* This is only tested with `Molekule Air Pro`, other models are not supported.
* This was inspired by: https://github.com/csirikak/homebridge-molekule  (Thanks!)


