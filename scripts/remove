#!/bin/bash

#=================================================
# IMPORT GENERIC HELPERS
#=================================================

source _common.sh
source /usr/share/yunohost/helpers

#=================================================
# REMOVE SYSTEM CONFIGURATIONS
#=================================================
ynh_script_progression --message="Removing system configurations..." --weight=1

# Remove the service from YunoHost
if ynh_exec_warn_less yunohost service status $app >/dev/null; then
    yunohost service remove $app
fi

# Remove systemd service
ynh_remove_systemd_config

# Remove logrotate configuration
ynh_remove_logrotate

# Remove NGINX configuration
ynh_remove_nginx_config

#=================================================
# REMOVE DEPENDENCIES
#=================================================
ynh_script_progression --message="Removing dependencies..." --weight=1

ynh_remove_app_dependencies

#=================================================
# REMOVE APP DATA
#=================================================
ynh_script_progression --message="Removing app data..." --weight=1

ynh_secure_remove --file="$install_dir"

#=================================================
# REMOVE DEDICATED USER
#=================================================
ynh_script_progression --message="Removing dedicated user..." --weight=1

ynh_system_user_delete --username=$app

#=================================================
# END OF SCRIPT
#=================================================

ynh_script_progression --message="Removal of $app completed" --last
