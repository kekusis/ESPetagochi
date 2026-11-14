"""
ESP32 Tamagotchi PC Controller & Test Utility
Allows sending button inputs (1, 2, 3, 4) and commands over Serial to your ESP32.

Features:
- Global & Local Keyboard listeners for keys 1, 2, 3, 4 (and numpad).
- Clean, simple, minimalist modern UI.
- Live pet status and serial monitor.
"""

import sys
import time
import threading
import serial
import serial.tools.list_ports

try:
    import keyboard
    HAS_KEYBOARD_LIB = True
except ImportError:
    HAS_KEYBOARD_LIB = False

try:
    import tkinter as tk
    from tkinter import scrolledtext
    HAS_TK = True
except ImportError:
    HAS_TK = False

DEFAULT_BAUD = 115200

def find_esp_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if any(k in desc for k in ["ch343", "ch340", "cp210", "serial", "uart", "esp"]):
            return p.device
    if ports:
        return ports[0].device
    return "COM7"

class SerialController:
    def __init__(self, port, baud=DEFAULT_BAUD, on_receive_callback=None):
        self.port = port
        self.baud = baud
        self.ser = None
        self.running = False
        self.on_receive = on_receive_callback
        self.connect()

    def connect(self):
        try:
            self.ser = serial.Serial()
            self.ser.port = self.port
            self.ser.baudrate = self.baud
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.timeout = 0.1
            self.ser.open()
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            # Start background time sync thread
            self.sync_thread = threading.Thread(target=self._time_sync_loop, daemon=True)
            self.sync_thread.start()
            return True, f"Connected to {self.port} at {self.baud} baud."
        except Exception as e:
            return False, f"Failed to connect: {e}"

    def _time_sync_loop(self):
        time.sleep(1.0)
        while self.running:
            self.send_command(f"TIME {int(time.time())}")
            time.sleep(30.0)

    def send_button(self, btn_num):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(f"{btn_num}\n".encode("utf-8"))
                return True
            except Exception:
                pass
        return False

    def send_command(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(f"{cmd}\n".encode("utf-8"))
                return True
            except Exception:
                pass
        return False

    def _read_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode("utf-8", errors="replace")
                if line:
                    if self.on_receive:
                        self.on_receive(line)
                    else:
                        print(line, end="")
            except Exception:
                break

    def close(self):
        self.running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass

def launch_gui(port_name):
    root = tk.Tk()
    root.title(f"Kekusis Controller ({port_name})")
    root.geometry("460x520")
    root.configure(bg="#12151c")
    root.resizable(False, False)

    status_var = tk.StringVar(value="Waiting for Kekusis...")

    def on_rx(text):
        if "[PET STATUS]" in text:
            # Parse pet status line
            status_var.set(text.replace("[PET STATUS]", "").strip())
        if log_text:
            log_text.config(state="normal")
            log_text.insert(tk.END, text)
            log_text.see(tk.END)
            log_text.config(state="disabled")

    controller = SerialController(port_name, on_receive_callback=on_rx)

    # Header
    title_lbl = tk.Label(root, text="KEKUSIS", font=("Segoe UI", 16, "bold"), fg="#5ebfec", bg="#12151c")
    title_lbl.pack(pady=(12, 2))

    hint_lbl = tk.Label(root, text="Press 1, 2, 3, or 4 on your keyboard (or click buttons below)",
                        font=("Segoe UI", 9), fg="#8fa0b5", bg="#12151c")
    hint_lbl.pack(pady=(0, 10))

    # Buttons Frame (2x2 Grid)
    btn_frame = tk.Frame(root, bg="#12151c")
    btn_frame.pack(padx=20, pady=5, fill="x")

    # Debounce tracking for keys and clicks
    last_trigger_time = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    DEBOUNCE_DELAY = 0.18  # 180ms debounce window

    def trigger_key(num):
        now = time.time()
        if now - last_trigger_time[num] < DEBOUNCE_DELAY:
            return  # Drop duplicate event
        last_trigger_time[num] = now

        controller.send_button(num)

        # Visual feedback on button
        target_btn = [b1, b2, b3, b4][num - 1]
        orig_bg = ["#c26d05", "#0369a1", "#be185d", "#4d7c0f"][num - 1]
        active_bg = ["#e68407", "#0284c7", "#db2777", "#65a30d"][num - 1]
        target_btn.config(bg=active_bg)
        for w in target_btn.winfo_children():
            w.config(bg=active_bg)
        root.after(90, lambda: (target_btn.config(bg=orig_bg), [w.config(bg=orig_bg) for w in target_btn.winfo_children()]))

    def make_btn(parent, text, subtext, color, active_col, num):
        f = tk.Frame(parent, bg=color, bd=0, relief="flat", cursor="hand2")
        lbl1 = tk.Label(f, text=text, font=("Segoe UI", 12, "bold"), fg="white", bg=color)
        lbl1.pack(pady=(6, 0))
        lbl2 = tk.Label(f, text=subtext, font=("Segoe UI", 8), fg="#e2e8f0", bg=color)
        lbl2.pack(pady=(0, 6))

        def on_click(e=None):
            trigger_key(num)

        f.bind("<Button-1>", on_click)
        lbl1.bind("<Button-1>", on_click)
        lbl2.bind("<Button-1>", on_click)
        return f

    b1 = make_btn(btn_frame, "[ 1 ]  FEED", "Lane 1 / Snack Catch", "#c26d05", "#e68407", 1)
    b1.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

    b2 = make_btn(btn_frame, "[ 2 ]  WASH", "Lane 2 / Bubble Scrub", "#0369a1", "#0284c7", 2)
    b2.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

    b3 = make_btn(btn_frame, "[ 3 ]  PLAY", "Lane 3 / Reaction", "#be185d", "#db2777", 3)
    b3.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")

    b4 = make_btn(btn_frame, "[ 4 ]  SLEEP", "Lane 4 / Rest Toggle", "#4d7c0f", "#65a30d", 4)
    b4.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")

    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)

    # Bindings in Tkinter (works whenever GUI window is in focus)
    for k in ["1", "2", "3", "4"]:
        num = int(k)
        root.bind_all(f"<Key-{k}>", lambda e, n=num: trigger_key(n))
        root.bind_all(f"<KP_{k}>", lambda e, n=num: trigger_key(n)) # Numpad

    # Global keyboard listener (works even if window lost focus!)
    if HAS_KEYBOARD_LIB:
        try:
            keyboard.on_press_key("1", lambda e: trigger_key(1))
            keyboard.on_press_key("2", lambda e: trigger_key(2))
            keyboard.on_press_key("3", lambda e: trigger_key(3))
            keyboard.on_press_key("4", lambda e: trigger_key(4))
        except Exception as e:
            print("Note: Global keyboard hook error:", e)

    # Compact Status Bar
    stat_lbl = tk.Label(root, textvariable=status_var, font=("Segoe UI", 9), fg="#38bdf8", bg="#1a202c", padx=10, pady=4)
    stat_lbl.pack(fill="x", padx=25, pady=(8, 6))

    # Serial Log area (read only so it never captures keyboard focus!)
    log_text = scrolledtext.ScrolledText(root, bg="#080b11", fg="#7dd3fc", font=("Consolas", 8), height=8, takefocus=0)
    log_text.pack(padx=25, pady=(0, 10), fill="both", expand=True)
    log_text.config(state="disabled")

    # Bottom Quick Tools
    bottom_frame = tk.Frame(root, bg="#12151c")
    bottom_frame.pack(pady=(0, 10))

    tk.Button(bottom_frame, text="Status", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8), bd=0, padx=8, pady=2,
              command=lambda: controller.send_command("status")).pack(side="left", padx=4)
    tk.Button(bottom_frame, text="Sleep/Wake", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8), bd=0, padx=8, pady=2,
              command=lambda: controller.send_command("sleep")).pack(side="left", padx=4)
    tk.Button(bottom_frame, text="Clear Log", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8), bd=0, padx=8, pady=2,
              command=lambda: (log_text.config(state="normal"), log_text.delete("1.0", tk.END), log_text.config(state="disabled"))).pack(side="left", padx=4)

    def on_closing():
        if HAS_KEYBOARD_LIB:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        controller.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def launch_cli(port_name):
    print(f"\n==========================================")
    print(f"  ESP32 TAMAGOTCHI CLI CONTROLLER ({port_name})")
    print(f"==========================================")
    print("Press [1], [2], [3], [4] + ENTER to trigger buttons.")
    print("Type 'status', 'feed', 'wash', 'play', 'sleep', or 'help'.")
    print("Type 'quit' or Ctrl+C to exit.\n")

    controller = SerialController(port_name)

    try:
        while True:
            cmd = input().strip()
            if cmd.lower() in ["q", "quit", "exit"]:
                break
            if cmd:
                controller.send_command(cmd)
    except KeyboardInterrupt:
        pass
    finally:
        controller.close()
        print("\nDisconnected.")

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else find_esp_port()
    print(f"Detected ESP32 port: {port}")
    if "--cli" in sys.argv or not HAS_TK:
        launch_cli(port)
    else:
        launch_gui(port)
