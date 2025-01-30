import sys
import tkinter
import numpad
import value as g

tk = tkinter

root = tk.Tk()
g.first_open_conf(root.winfo_screenwidth(), root.winfo_screenheight())
g.width_main=int(g.width_main)
g.height_main=int(g.height_main)
root.title(u"SIPTELLER")
root.geometry(f"{g.width_main}x{g.height_main}")
root.tk_setPalette(background=f"{g.bgcolor}")
button = tk.Button(root, text="Press me", command=numpad.numpad)
button.pack()

root.mainloop()