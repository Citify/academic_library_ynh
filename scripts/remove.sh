#!/bin/bash

yunohost service remove academic_library
sudo systemctl stop academic_library
sudo rm /etc/systemd/system/academic_library.service
sudo systemctl daemon-reload
sudo rm -rf /var/www/academic_library
yunohost app remove academic_library
