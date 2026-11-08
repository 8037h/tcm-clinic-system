# 中医馆医师排班与绩效记录管理系统

基于 Python 和 Django 的课程设计项目，包含医师、科室、出诊排班、接诊、绩效、数据分析和操作日志等功能。

详细的代码结构、技术知识、业务流程和当前限制请查看 [项目技术说明](docs/项目技术说明.md)。

## 在线演示

[打开操作日志演示页面](https://semicolon-satchel-lingo.ngrok-free.dev/operation-logs/)。登录账号请向项目负责人获取。该演示使用独立的演示数据，支持体验系统操作；演示服务运行在项目负责人的电脑上，电脑或服务关闭后链接会暂时失效。首次访问可能出现 ngrok 提示页面。

## 一、下载项目

打开 [项目仓库](https://github.com/8037h/tcm-clinic-system)，点击绿色 **Code** 按钮，选择 **Download ZIP**，下载后解压。也可以使用 Git 克隆：

```powershell
git clone https://github.com/8037h/tcm-clinic-system.git
```

## 二、准备运行环境

以下步骤适用于 Windows。请先安装 Python 3.11 或 3.12，并在安装时勾选 **Add Python to PATH**。打开解压后的项目文件夹，在文件夹地址栏输入 `powershell` 并按回车；以下命令都在这个窗口中运行。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```

第一条命令创建项目的 Python 环境，第二条安装依赖，第三条创建本机数据库。安装依赖需要联网。

## 三、创建管理员

首次使用时，在同一个 PowerShell 窗口运行：

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

按提示输入用户名、邮箱（可留空）和密码。输入密码时屏幕不显示字符，输入完成后按回车即可。

## 四、启动和访问

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

浏览器打开 [系统首页](http://127.0.0.1:8000/)，用刚创建的管理员账号登录。Django 后台地址为 [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)。普通用户可在登录页注册，看到的功能取决于账号权限。

运行期间请保持 PowerShell 窗口打开；按 `Ctrl+C` 可停止服务。下次使用时，在项目目录打开 PowerShell，只需再次运行上面的 `runserver` 命令。

## 五、数据和协作说明

- 下载版不包含原电脑上的数据库、患者记录、账号和上传附件。首次迁移会在自己的项目文件夹生成 `db.sqlite3`，管理员账号也需要自己创建。
- `research` 目录内的 CSV 是公开医师出诊信息调研资料，不会自动导入系统业务数据库。
- GitHub 用于共享代码，各人电脑上的 SQLite 数据库不会自动同步。`127.0.0.1` 是当前电脑的本地地址，其他人不能用它直接访问你的系统。
- 如果 `py` 命令不可用，请确认 Python 安装成功；如果 8000 端口已被占用，可以运行 `.\.venv\Scripts\python.exe manage.py runserver 8001`，再访问 `http://127.0.0.1:8001/`。
