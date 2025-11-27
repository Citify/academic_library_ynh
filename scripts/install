#!/bin/bash

#=================================================
# IMPORT GENERIC HELPERS
#=================================================

source _common.sh
source /usr/share/yunohost/helpers

#=================================================
# INITIALIZE AND STORE SETTINGS
#=================================================

ynh_app_setting_set --app=$app --key=domain --value=$domain
ynh_app_setting_set --app=$app --key=path --value=$path
ynh_app_setting_set --app=$app --key=is_public --value=$is_public

#=================================================
# INSTALL DEPENDENCIES
#=================================================
ynh_script_progression --message="Installing dependencies..." --weight=5

ynh_install_app_dependencies $pkg_dependencies

#=================================================
# CREATE DEDICATED USER
#=================================================
ynh_script_progression --message="Configuring system user..." --weight=1

ynh_system_user_create --username=$app --home_dir="$install_dir"

#=================================================
# DOWNLOAD, CHECK AND UNPACK SOURCE
#=================================================
ynh_script_progression --message="Setting up source files..." --weight=1

ynh_app_setting_set --app=$app --key=install_dir --value=$install_dir

# Create necessary directories
mkdir -p "$install_dir"
mkdir -p "$install_dir/uploads/books"
mkdir -p "$install_dir/uploads/covers"
mkdir -p "$install_dir/templates"

# Copy application files
cp ../app.py "$install_dir/"
cp ../requirements.txt "$install_dir/"
cp -r ../templates/* "$install_dir/templates/"

chmod 750 "$install_dir"
chmod -R o-rwx "$install_dir"
chown -R $app:www-data "$install_dir"
chmod -R 770 "$install_dir/uploads"

#=================================================
# PYTHON VIRTUALENV
#=================================================
ynh_script_progression --message="Setting up Python virtual environment..." --weight=5

python3 -m venv "$install_dir/venv"
"$install_dir/venv/bin/pip" install --upgrade pip
"$install_dir/venv/bin/pip" install -r "$install_dir/requirements.txt"

#=================================================
# ADD A CONFIGURATION
#=================================================
ynh_script_progression --message="Adding configuration..." --weight=1

# Update SECRET_KEY with random value
secret_key=$(ynh_string_random --length=50)
ynh_replace_string --match_string="your-super-secret-key-change-this-1234567890" \
    --replace_string="$secret_key" --target_file="$install_dir/app.py"

ynh_app_setting_set --app=$app --key=secret_key --value=$secret_key

#=================================================
# SETUP SYSTEMD
#=================================================
ynh_script_progression --message="Configuring systemd service..." --weight=1

ynh_add_systemd_config

#=================================================
# SETUP LOGROTATE
#=================================================
ynh_script_progression --message="Configuring log rotation..." --weight=1

ynh_use_logrotate

#=================================================
# INTEGRATE SERVICE IN YUNOHOST
#=================================================
ynh_script_progression --message="Integrating service in YunoHost..." --weight=1

yunohost service add $app --description="Academic Library Service" \
    --log="/var/log/$app/$app.log"

#=================================================
# ADD NGINX CONFIGURATION
#=================================================
ynh_script_progression --message="Configuring NGINX..." --weight=1

ynh_add_nginx_config

#=================================================
# START SYSTEMD SERVICE
#=================================================
ynh_script_progression --message="Starting systemd service..." --weight=1

ynh_systemd_action --service_name=$app --action="start" --log_path="/var/log/$app/$app.log"

#=================================================
# SETUP SSOWAT
#=================================================
ynh_script_progression --message="Configuring permissions..." --weight=1

if [ $is_public -eq 1 ]; then
    ynh_permission_update --permission="main" --add="visitors"
fi

#=================================================
# RELOAD NGINX
#=================================================
ynh_script_progression --message="Reloading NGINX..." --weight=1

ynh_systemd_action --service_name=nginx --action=reload

#=================================================
# END OF SCRIPT
#=================================================

ynh_script_progression --message="Installation of $app completed" --last
