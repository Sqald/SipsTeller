import hashlib
import tkinter
import value as g

def pass_check():
    root = tkinter.Tk()
    root.title(u"Password Check")
    root.minsize(width=int(root.winfo_screenwidth()/10), height=int(root.winfo_screenheight()*2/15))
    g.read_conf()
    root.geometry(f"{int(root.winfo_screenwidth()/10)}x{int(root.winfo_screenheight()*2/15)}")
    root.mainloop()

def config():
    root = tkinter.Tk()
    root.title(u"Config")
    root.minsize(width=int(root.winfo_screenwidth()/5), height=int(root.winfo_screenheight()*2/3))
    g.read_conf()
    root.geometry(f"{g.width_main}x{g.height_main}")
    root.mainloop()


def setup():
    global passwd

    print()