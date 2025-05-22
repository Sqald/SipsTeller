import sys
import tkinter as tk
import numpad
import config
import value as g

root = tk.Tk()
g.first_open_conf(root.winfo_screenwidth(), root.winfo_screenheight())
g.width_main=int(g.width_main)
g.height_main=int(g.height_main)
root.title(u"SIPTELLER")
root.geometry(f"{g.width_main}x{g.height_main}")
root.tk_setPalette(background=f"{g.bgcolor}")
button = tk.Button(root, text="Numpad", command=numpad.numpad)
button2 = tk.Button(root, text="Config", command=config.open_config_window)
button.grid(row=0, column=0,sticky="nw")
button2.grid(row=2, column=2,sticky="s")

<<<<<<< Updated upstream
=======
root.protocol("WM_DELETE_WINDOW", lambda:g.on_close_main(root, root.winfo_width(), root.winfo_height())) 

>>>>>>> Stashed changes
root.mainloop()