import tkinter as tk
import numpad
import config
import value as g

root = tk.Tk()
g.first_open_conf(root.winfo_screenwidth(), root.winfo_screenheight())
root.minsize(width=int(root.winfo_screenwidth()/5), height=int(root.winfo_screenheight()*2/3))
g.width_main=int(g.width_main)
g.height_main=int(g.height_main)
root.title(u"SIPTELLER")
root.geometry(f"{g.width_main}x{g.height_main}")
root.tk_setPalette(background=f"{g.bgcolor}")

# 上下2行の比率を設定
root.grid_rowconfigure(0, weight=4)
root.grid_rowconfigure(1, weight=5)
root.grid_columnconfigure(0, weight=1)

# 上の領域（2列に分ける）
top_frame = tk.Frame(root, bg="lightblue")
top_frame.grid(row=0, column=0, sticky="nsew")
top_frame.grid_columnconfigure(0, weight=3)
top_frame.grid_columnconfigure(1, weight=1)
top_frame.grid_rowconfigure(0, weight=1)

# 左右フレーム
top_frame_left = tk.Frame(top_frame, bg="lightblue")
top_frame_left.grid(row=0, column=0, sticky="nsew")

top_frame_right = tk.Frame(top_frame, bg="lightblue")
top_frame_right.grid_rowconfigure(0, weight=1)
top_frame_right.grid_columnconfigure(0, weight=1)
top_frame_right.grid(row=0, column=1, sticky="nsew")

# 下の領域
bottom_frame = tk.Frame(root, bg="lightgreen")
bottom_frame.grid(row=1, column=0, sticky="nsew")
bottom_frame.grid_rowconfigure(2, weight=1)
bottom_frame.grid_columnconfigure(2, weight=1)

# ボタンの設置
button = tk.Button(top_frame_right, text="Numpad", command=numpad.numpad)
button.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

button2 = tk.Button(bottom_frame, text="Config", command=config.open_config_window)
button2.grid(row=2, column=2, sticky="nsew", padx=5, pady=5)

# 閉じる処理
root.protocol("WM_DELETE_WINDOW", lambda: g.on_close_main(root, root.winfo_width(), root.winfo_height()))

root.mainloop()
