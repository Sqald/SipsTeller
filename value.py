import os
import re
import configparser
import config


def first_open_conf(window_width, window_height):
    user_folder = os.path.expanduser("~")
    folder = os.path.join(user_folder, "Documents")
    config_dir = os.path.join(folder, "sipteller")
    config_path = os.path.join(config_dir, "config.txt")

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
    user_folder = os.path.expanduser("~")
    folder = os.path.join(user_folder, "Documents")
    config_dir = os.path.join(folder, "sipteller")
    config_path = os.path.join(config_dir, "config.txt")
    with open(config_path, "r", encoding="utf-8") as file:
            for line in file:
                # 行から '変数=値' のパターンを検索
                match = re.match(r'(\w+) = ["\']?([^"\']+)["\']?', line.strip())
                if match:
                    var_name, var_value = match.groups()  # グループ1=変数, グループ2=値
                    # 動的にグローバル変数を作成
                    globals()[var_name] = var_value

def on_close(root, width_r, height_r): 
    user_folder = os.path.expanduser("~")
    folder = os.path.join(user_folder, "Documents")
    config_dir = os.path.join(folder, "sipteller")
    config_path = os.path.join(config_dir, "config.txt")
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    config["config"]["width_num"] = str(width_r)
    config["config"]["height_num"] = str(height_r)
    with open(config_path, "w", encoding="utf-8") as file:
        config.write(file)
    root.destroy()
