import hashlib
import tkinter
import value as g
import os
import configparser

passwd = None

def open_config_window():
    root = tkinter.Tk()
    root.title(u"Config")
    root.minsize(width=int(root.winfo_screenwidth()/5), height=int(root.winfo_screenheight()*2/3))
    g.read_conf()
    user_folder = os.path.expanduser("~")
    folder = os.path.join(user_folder, "Documents")
    config_dir = os.path.join(folder, "sipteller")
    config_path = os.path.join(config_dir, "config.txt")
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    root.geometry(f"{g.width_main}x{g.height_main}")
    root.mainloop()


def setup():
    global passwd

    print()