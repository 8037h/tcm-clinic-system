# 中医馆医师排班与绩效记录管理系统

基于 Django 5.2 和 SQLite。第一阶段包含登录、注册、首页、基础模型及后台管理；沿用原有接诊记录页面和数据。

在本目录执行 `./start.ps1`；或安装 `requirements.txt` 后运行 `python manage.py migrate`、`python manage.py runserver`。

首次使用后台管理时执行 `python manage.py createsuperuser`。管理员可在后台把用户关联到医师资料；自行注册的账号为普通用户。业务页面要求登录。
