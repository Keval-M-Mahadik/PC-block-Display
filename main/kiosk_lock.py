import tkinter as tk
from tkinter import messagebox
import os, time, datetime, signal
try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None

# ---------------- CONFIG ----------------
ADMIN_PASSWORD = "2258"        
HIDE_CURSOR = False
BLOCK_RIGHT_CLICK = True
LOG_FILE = "kiosk_attempts.log"
LOCKOUT_THRESHOLD = 3         # wrong tries before temporary lockout
LOCKOUT_MS = 45_000           # 30 seconds lockout
# ---------------------------------------

#os.makedirs(EVIDENCE_DIR, exist_ok=True)

# Ignore SIGINT/SIGTERM (so Ctrl+C won't kill easily)
def _ignore_signal(sig, frame):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} signal_ignored={sig}\n")
    return

try:
    signal.signal(signal.SIGINT, _ignore_signal)
    signal.signal(signal.SIGTERM, _ignore_signal)
except Exception:
    pass

# ---------- TK root ----------
root = tk.Tk()
root.title("Kiosk Keypad Secure Demo")
root.attributes("-fullscreen", True)
root.overrideredirect(False)
root.protocol("WM_DELETE_WINDOW", lambda: None)  # disable window close

# Globals
wrong_attempts = 0
admin_btn = None
keypad_frame = None
input_var = None
msg_label = None

# Utilities
def log_attempt(success):
    ts = datetime.datetime.now().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} success={success}\n")

def capture_evidence(reason="attempt"):
    if ImageGrab is None:
        return
    try:
        img = ImageGrab.grab()
        fname = os.path.join(EVIDENCE_DIR, f"{reason}_{int(time.time())}.png")
        img.save(fname)
    except Exception as e:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.datetime.now().isoformat()} evidence_failed={e}\n")

# Input blocking (block all keys inside the app)
def block_key(event):
    return "break"

def block_rightclick(event):
    return "break"

# ---------- Admin keypad UI (in-kiosk) ----------
def show_keypad_overlay():
    """Show an in-kiosk overlay containing a keypad for password entry.
       This DOES NOT use external dialogs; everything is inside the fullscreen app."""
    global keypad_frame, input_var, msg_label

    # If keypad already exists, bring to front
    if keypad_frame and keypad_frame.winfo_exists():
        keypad_frame.lift()
        return

    keypad_frame = tk.Toplevel(root)
    keypad_frame.transient(root)
    keypad_frame.grab_set()        # capture events to this overlay
    keypad_frame.overrideredirect(True)
    keypad_frame.attributes("-topmost", True)
    # semi-transparent background look
    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    keypad_frame.geometry(f"{w}x{h}+0+0")
    keypad_frame.config(bg="#000000")
    keypad_frame.attributes("-alpha", 0.95)  # slight transparency

    # container in center
    container = tk.Frame(keypad_frame, bg="#0b1220", bd=0, relief="flat")
    container.place(relx=0.5, rely=0.5, anchor="center")

    title = tk.Label(container, text="I am Hacker KITC ", fg="#ff0000", bg="#0b1220", font=("Segoe UI", 20, "bold"))
    title.pack(pady=(10,6))

    info = tk.Label(container, text="I am block your window or linux ", fg="white", bg="#0b1220")
    info.pack(pady=(0,10))

    input_var = tk.StringVar(value="")
    entry = tk.Entry(container, textvariable=input_var, show="*", font=("Segoe UI", 18), justify="center", width=12, bd=6)
    entry.pack(pady=(0,10))
    entry.configure(state="readonly")  # read-only so keyboard cannot type

    # message label
    msg_label = tk.Label(container, text="", fg="#ffaaaa", bg="#0b1220")
    msg_label.pack(pady=(0,6))

    # keypad layout
    kp = tk.Frame(container, bg="#0b1220")
    kp.pack()

    btn_cfg = {"font":("Segoe UI", 16), "width":4, "height":2, "bg":"#22c1c3"}

    def append_digit(d):
        current = input_var.get()
        if len(current) >= 16:
            return
        input_var.set(current + str(d))

    def backspace():
        input_var.set(input_var.get()[:-1])

    def clear_input():
        input_var.set("")

    def submit():
        global wrong_attempts
        val = input_var.get()
        if val == ADMIN_PASSWORD:
            log_attempt(True)
            capture_evidence("success")
            # release grab and destroy overlay then exit
            try:
                keypad_frame.grab_release()
            except:
                pass
            try:
                keypad_frame.destroy()
            except:
                pass
            root.destroy()
        else:
            wrong_attempts += 1
            log_attempt(False)
            capture_evidence("wrong")
            msg_label.config(text=f"Access Denied ({wrong_attempts})")
            clear_input()
            root.bell()
            if wrong_attempts >= LOCKOUT_THRESHOLD:
                # disable admin button temporarily
                if admin_btn:
                    admin_btn.config(state="disabled")
                    root.after(LOCKOUT_MS, lambda: admin_btn.config(state="normal"))
                    msg_label.config(text=f"Too many attempts. Locked for {LOCKOUT_MS//1000}s.")

    # Buttons 1-9, 0, back, clear, enter
    digits = [
        ("1",0,0),("2",0,1),("3",0,2),
        ("4",1,0),("5",1,1),("6",1,2),
        ("7",2,0),("8",2,1),("9",2,2),
        ("C",3,0),("0",3,1),("<",3,2)
    ]
    for (label,r,c) in digits:
        if label == "C":
            b = tk.Button(kp, text=label, command=clear_input, **btn_cfg)
        elif label == "<":
            b = tk.Button(kp, text=label, command=backspace, **btn_cfg)
        else:
            b = tk.Button(kp, text=label, command=lambda d=label: append_digit(d), **btn_cfg)
        b.grid(row=r, column=c, padx=6, pady=6)

    # submit row
    submit_btn = tk.Button(container, text="ENTER", command=submit, font=("Segoe UI", 16), bg="#4ade80", width=28)
    submit_btn.pack(pady=(10,12))

    # prevent keyboard events to focus or type into entry
    entry.configure(state="readonly")
    entry.bind("<Key>", lambda e: "break")

    # Provide small cancel in corner
    def cancel_overlay():
        try:
            keypad_frame.grab_release()
        except:
            pass
        try:
            keypad_frame.destroy()
        except:
            pass

    cancel_btn = tk.Button(keypad_frame, text="×", command=cancel_overlay, bg="#ff5c5c", fg="white", font=("Segoe UI", 12))
    cancel_btn.place(relx=0.99, rely=0.01, anchor="ne")


def start_kiosk_ui():
    global admin_btn
    main_frame = tk.Frame(root, bg="black")
    main_frame.pack(fill="both", expand=True)

    title = tk.Label(main_frame, text="SECURE KIOSK MODE", fg="#ff0000", bg="black", font=("Segoe UI", 36, "bold"))
    title.pack(pady=40)

    sub = tk.Label(main_frame, text="This is a Educational Demo. \n Click ADMIN and use the on-screen keypad to enter code.", fg="#ff0000", bg="black", font=("Segoe UI", 25, "bold"))
    sub.pack(pady=10)

    if HIDE_CURSOR:
        root.configure(cursor="none")

    admin_btn = tk.Button(root, text="ADMIN", command=show_keypad_overlay, bg="#22c1c3", fg="#012", font=("Segoe UI", 12), padx=12, pady=6)
    admin_btn.place(relx=0.98, rely=0.02, anchor="ne")

    # block keys and right click globally inside the app
    root.bind_all("<Key>", block_key, add=True)
    if BLOCK_RIGHT_CLICK:
        root.bind_all("<Button-3>", block_rightclick, add=True)
        root.bind_all("<Button-2>", block_rightclick, add=True)


if __name__ == "__main__":
    # Directly start kiosk UI (boot removed)
    start_kiosk_ui()
    try:
        root.mainloop()
    except Exception:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.datetime.now().isoformat()} main_exception\n")
        try:
            root.destroy()
        except:
            pass

