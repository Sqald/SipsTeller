import tkinter
import value as g
from playsound import playsound
import threading
import time
import pyaudio
import wave

def numpad():
    root = tkinter.Tk()
    root.title(u"numpad")
    root.minsize(width=int(root.winfo_screenwidth()/5), height=int(root.winfo_screenheight()*2/3))
    g.read_conf()
    root.geometry(f"{g.width_num}x{g.height_num}")
    root.tk_setPalette(background=f"{g.bgcolor}")
    frame_top = tkinter.Frame(root, bg="lightgray")
    frame_bottom = tkinter.Frame(root, bg="white")

    frame_top.grid(row=0, column=0, sticky="nsew")
    frame_bottom.grid(row=1, column=0, sticky="nsew")

    root.grid_rowconfigure(0, weight=2)
    root.grid_rowconfigure(1, weight=1)  
    root.grid_columnconfigure(0, weight=1)

    buttons = []
    phone_num = tkinter.StringVar()
    entry = tkinter.Entry(master=frame_bottom, textvariable=phone_num, font=(None,24))
    label = tkinter.Label(master=frame_bottom, textvariable=phone_num, font=("Helvetica",36))
    button = tkinter.Button(frame_bottom, text="Call", highlightbackground="#66FF66", bg="#66FF66", fg="#000", relief="raised", font=("Helvetica", 20))
    button2 = tkinter.Button(frame_bottom, text="Hang up", highlightbackground="#FF3300", bg="#FF3300", fg="#000", relief="raised", font=("Helvetica", 20))
    entry.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=3)
    label.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=3)
    button.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
    button2.grid(row=2, column=2, sticky="nsew", padx=5, pady=5)
    button_texts = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "＊", "0", "#"]

    def add_num(t):
        label_text = label.cget("text")
        new_text = label_text + str(t)
        entry.delete(0, tkinter.END)
        entry.insert(0, new_text)
        label.config(text=new_text)


    def play_sound(button_text):
        chunk = 1024
        if button_text == "＊":
            wf = wave.open(f"dtmf/aster.wav", 'rb')
        elif button_text == "#":
            wf = wave.open(f"dtmf/hash.wav", 'rb')
        else :
            wf = wave.open(f"dtmf/{button_text}.wav", 'rb')

        p = pyaudio.PyAudio()
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )

        data = wf.readframes(chunk)
        while data:
            stream.write(data)
            data = wf.readframes(chunk)

        stream.stop_stream()
        stream.close()
        p.terminate()
        is_playing = False

    def on_button_press(event):
        thread = threading.Thread(target=play_sound, args=(event.widget['text'],))
        thread.start()

    for text in button_texts:
        button = tkinter.Button(frame_bottom, text=text, relief="raised", font=("Helvetica", 20),command=lambda t=text:add_num(t))
        button.bind("<Button-1>", on_button_press)
        buttons.append(button)  

    for index, button in enumerate(buttons):
        row = (index // 3) + 3
        col = index % 3 
        button.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

    for row in range(4): 
        frame_bottom.grid_rowconfigure(row + 3, weight=1)
    for col in range(3): 
        frame_bottom.grid_columnconfigure(col, weight=1, uniform="group1") 
    root.protocol("WM_DELETE_WINDOW", lambda:g.on_close_num(root, root.winfo_width(), root.winfo_height())) 

    root.mainloop()