#!/bin/bash
source /usr/share/yunohost/helpers

domain=$YNH_APP_ARG_DOMAIN
path=${YNH_APP_ARG_PATH%/}
app=$YNH_APP_INSTANCE_NAME
final_path="/var/www/$app"

ynh_app_setting_set --app=$app --key=domain --value=$domain
ynh_app_setting_set --app=$app --key=path   --value=$path

ynh_install_app_dependencies python3-venv python3-pip lxml

mkdir -p "$final_path"
cp -r ../source/* "$final_path/"
chown -R $app:www-data "$final_path"

python3 -m venv "$final_path/venv"
"$final_path/venv/bin/pip" install --upgrade pip
"$final_path/venv/bin/pip" install -r "$final_path/requirements.txt"

mkdir -p "$final_path/uploads/books" "$final_path/uploads/covers"
chown -R $app:www-data "$final_path/uploads"

ynh_add_systemd_config
ynh_add_nginx_config

yunohost service add $app --description "Academic Library"
ynh_systemd_action --service_name=$app --action=start

ynh_script_progression --message="Installation complete!" --last
