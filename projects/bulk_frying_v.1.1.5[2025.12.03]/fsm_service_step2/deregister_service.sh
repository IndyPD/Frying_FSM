#!/bin/bash
ServiceName=frying_fsm

sudo service $ServiceName stop
sudo update-rc.d -f $ServiceName remove
sudo rm /etc/${ServiceName}_script
sudo rm /etc/init.d/$ServiceName
