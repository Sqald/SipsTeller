import os
import re
import configparser
import config 
import argparse

import subprocess
import threading

env = os.environ.copy()

parser = argparse.ArgumentParser(description="フォルダ指定 (フルパス)")
parser.add_argument("-f", "--folder", type=str, default=None, help="フォルダ指定用のパス")
args = parser.parse_args()

if args.folder:
    if os.path.isdir(args.folder):
        print(f"指定されたフォルダ: {args.folder}")
        config_dir = os.path.abspath(os.path.expanduser(args.folder))
    else:
        user_folder = os.path.expanduser("~")
        folder = os.path.join(user_folder, "Documents")
        config_dir = os.path.join(folder, "sipteller")
else:
    user_folder = os.path.expanduser("~")
    folder = os.path.join(user_folder, "Documents")
    config_dir = os.path.join(folder, "sipteller")

config_path = os.path.join(config_dir, "config.txt")
env["BARESIP_HOME"] = config_dir 

print("BARESIP_HOME:", env.get("BARESIP_HOME"))

def first_open_conf(window_width, window_height):

    # 設定ファイルが存在するか確認
    if os.path.exists(config_path):
        # ファイルが存在する場合、内容を読み込む
        with open(config_path, "r", encoding="utf-8") as file:
            for line in file:
                # 行から '変数=値' のパターンを検索
                match = re.match(r'(\w+) = ["\']?([^"\']+)["\']?', line.strip())
                if match:
                    var_name, var_value = match.groups()  # グループ1=変数, グループ2=値
                    # 動的にグローバル変数を作成
                    globals()[var_name] = var_value

    else:
        # フォルダが存在しない場合、作成する
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)  # フォルダを作成
        
        config.setup()

        # テンプレートの内容を定義
        template_content = f"""# SipsTeller config
[global]
bgcolor = "#FFFFFF"

[config]
width_main = {int(window_width/5)}
height_main = {int(window_height*2/3)}
width_num = {int(window_width/5)}
height_num = {int(window_height*2/3)}

[admin]
password = {str(config.passwd)}

[sip]
sip_address = 0.0.0.0
sip_port = 5060
sip_username = 0000
sip_password = 0000
    """

        # テンプレートを `config.txt` として作成
        with open(config_path, "w", encoding="utf-8") as file:
            file.write(template_content)

        with open(config_path, "r", encoding="utf-8") as file:
            for line in file:
                # 行から '変数=値' のパターンを検索
                match = re.match(r'(\w+) = ["\']?([^"\']+)["\']?', line.strip())
                if match:
                    var_name, var_value = match.groups()  # グループ1=変数, グループ2=値
                    # 動的にグローバル変数を作成
                    globals()[var_name] = var_value

def read_conf():
    with open(config_path, "r", encoding="utf-8") as file:
            for line in file:
                # 行から '変数=値' のパターンを検索
                match = re.match(r'(\w+) = ["\']?([^"\']+)["\']?', line.strip())
                if match:
                    var_name, var_value = match.groups()  # グループ1=変数, グループ2=値
                    # 動的にグローバル変数を作成
                    globals()[var_name] = var_value

<<<<<<< Updated upstream
def on_close(root, width_r, height_r): 
=======
def get_baresip_executable():
    from sys import platform
    base = os.path.join(os.path.dirname(__file__), "bin")
    if platform.startswith("win"):
        return os.path.join(base, "baresip.exe")
    elif platform.startswith("darwin"):
        return os.path.join(base, "baresip_mac")
    else:
        return "baresip"  # Linux等


def run_baresip():
    # バックグラウンドで Baresip を起動
    process = subprocess.Popen(
        ["baresip", "-f", config_dir],  # 必要な引数に合わせて修正
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    # 出力監視スレッド
    def read_output():
        for line in process.stdout:
            print("BARESIP>", line.strip())

    threading.Thread(target=read_output, daemon=True).start()
    return process

def send_command(command):
    if proc.stdin:
        proc.stdin.write(command  + '\n')
        proc.stdin.flush()

proc = run_baresip()

def on_close_num(root, width_r, height_r): 
>>>>>>> Stashed changes
    user_folder = os.path.expanduser("~")
    folder = os.path.join(user_folder, "Documents")
    config_dir = os.path.join(folder, "sipteller")
    config_path = os.path.join(config_dir, "config.txt")
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    config["config"]["width_num"] = str(width_r)
    config["config"]["height_num"] = str(height_r)
<<<<<<< Updated upstream
=======
    global width_num,height_num
    width_num = width_r
    height_num = height_r
    with open(config_path, "w", encoding="utf-8") as file:
        config.write(file)
    root.destroy()

def on_close_main(root, width_r, height_r): 
    user_folder = os.path.expanduser("~")
    folder = os.path.join(user_folder, "Documents")
    config_dir = os.path.join(folder, "sipteller")
    config_path = os.path.join(config_dir, "config.txt")
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    config["config"]["width_main"] = str(width_r)
    config["config"]["height_main"] = str(height_r)
    global width_main,height_main
    width_main = width_r
    height_main = height_r
>>>>>>> Stashed changes
    with open(config_path, "w", encoding="utf-8") as file:
        config.write(file)
    send_command("/quit")
    root.destroy()

def on_close(root): 
    root.destroy()
