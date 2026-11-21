"""
ESP32 Tamagotchi PC Controller & Test Utility
Allows sending button inputs (1, 2, 3, 4), manually setting stats,
and triggering any animation over Serial to your ESP32.

Features:
- Global & Local Keyboard listeners for keys 1, 2, 3, 4 (and numpad).
- Manual Stat Adjusters (Hunger, Cleanliness, Happiness, Energy) with sliders and presets.
- Animation Trigger Panel (Idle, Happy, Hungry, Dirty, Eating, Sleeping, Washing, Playing).
- Realtime pet stats parsing and status display.
- Serial Monitor with custom command sending.
"""

import sys
import time
import threading
import queue
import re
import serial
import serial.tools.list_ports

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
    HAS_TK = True
except ImportError:
    HAS_TK = False

DEFAULT_BAUD = 115200

# Background sound player thread for non-blocking buzzer emulation
sound_queue = queue.Queue()

def sound_player_loop():
    while True:
        try:
            item = sound_queue.get()
            if item is None:
                break
            freq, duration, enabled = item
            if enabled and HAS_WINSOUND and freq > 0:
                try:
                    c_freq = max(37, min(32767, int(freq)))
                    winsound.Beep(c_freq, max(1, int(duration)))
                except Exception:
                    pass
            elif enabled and freq == 0 and duration > 0:
                time.sleep(duration / 1000.0)
        except Exception:
            pass
        finally:
            sound_queue.task_done()

threading.Thread(target=sound_player_loop, daemon=True).start()

def find_esp_port():
    ports = list(serial.tools.list_ports.comports())
    # Exclude Bluetooth virtual serial ports
    valid = [p for p in ports if "bluetooth" not in p.description.lower()]
    for p in valid:
        desc = p.description.lower()
        if any(k in desc for k in ["ch343", "ch340", "cp210", "ftdi", "esp", "usb"]):
            return p.device
    if valid:
        return valid[0].device
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
    root.title(f"Kekusis Controller & Debugger ({port_name})")
    root.geometry("520x920")
    root.configure(bg="#0f172a")
    root.resizable(False, True)

    # State variables
    status_var = tk.StringVar(value="Waiting for Kekusis status...")
    hunger_var = tk.IntVar(value=100)
    clean_var = tk.IntVar(value=100)
    happy_var = tk.IntVar(value=100)
    energy_var = tk.IntVar(value=100)
    mood_var = tk.StringVar(value="IDLE")
    log_text = None
    buzzer_sound_enabled = tk.BooleanVar(value=True)
    buzzer_indicator_var = tk.StringVar(value="♪ Buzzer: Idle")
    buzzer_flash_timer = [None]
    buzzer_indicator_lbl = None

    def parse_status_line(text):
        # [PET STATUS] Kekusis -> Hunger: 99% | Clean: 83% | Happy: 100% | Energy: 80% | Mood: IDLE
        m = re.search(r"Hunger:\s*(\d+)%.*?Clean:\s*(\d+)%.*?Happy:\s*(\d+)%.*?Energy:\s*(\d+)%.*?Mood:\s*([A-Za-z]+)", text)
        if m:
            h, c, p, e, mood = m.groups()
            hunger_var.set(int(h))
            clean_var.set(int(c))
            happy_var.set(int(p))
            energy_var.set(int(e))
            mood_var.set(mood)
            status_var.set(f"Hunger: {h}% | Clean: {c}% | Happy: {p}% | Energy: {e}% | Mood: {mood}")

    def on_rx(text):
        def _update():
            if "[PET STATUS]" in text:
                parse_status_line(text)
            elif "Stats updated" in text or "set to" in text:
                controller.send_command("status")

            m_snd = re.search(r"\[SND\]\s+(\d+)\s+(\d+)", text)
            if m_snd:
                freq = int(m_snd.group(1))
                dur = int(m_snd.group(2))
                if buzzer_sound_enabled.get():
                    sound_queue.put((freq, dur, True))
                if buzzer_indicator_lbl is not None:
                    if freq > 0:
                        buzzer_indicator_var.set(f"♪ {freq}Hz ({dur}ms)")
                        buzzer_indicator_lbl.config(fg="#4ade80")
                    else:
                        buzzer_indicator_var.set(f"♪ Rest ({dur}ms)")
                        buzzer_indicator_lbl.config(fg="#38bdf8")
                    if buzzer_flash_timer[0] is not None:
                        root.after_cancel(buzzer_flash_timer[0])
                    buzzer_flash_timer[0] = root.after(350, lambda: buzzer_indicator_lbl.config(fg="#94a3b8") if buzzer_indicator_lbl else None)
                
            if log_text is not None:
                try:
                    log_text.config(state="normal")
                    log_text.insert(tk.END, text)
                    log_text.see(tk.END)
                    log_text.config(state="disabled")
                except Exception:
                    pass
        try:
            root.after(0, _update)
        except Exception:
            pass

    controller = SerialController(port_name, on_receive_callback=on_rx)

    # Header
    header_frame = tk.Frame(root, bg="#0f172a")
    header_frame.pack(fill="x", padx=16, pady=(12, 6))

    title_lbl = tk.Label(header_frame, text="KEKUSIS TAMAGOTCHI", font=("Segoe UI", 15, "bold"), fg="#38bdf8", bg="#0f172a")
    title_lbl.pack(anchor="w")

    sub_lbl = tk.Label(header_frame, text="Interactive Hardware Remote & Animation Tester",
                       font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a")
    sub_lbl.pack(anchor="w")

    # Realtime Stat Status Banner
    banner_frame = tk.Frame(root, bg="#1e293b", bd=1, relief="solid")
    banner_frame.pack(fill="x", padx=16, pady=6)

    stat_lbl = tk.Label(banner_frame, textvariable=status_var, font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", pady=6)
    stat_lbl.pack()

    # SECTION 1: Hardware Buttons
    sec1 = tk.LabelFrame(root, text=" 🎮 HARDWARE BUTTONS & ACTIONS ", font=("Segoe UI", 9, "bold"),
                         fg="#cbd5e1", bg="#0f172a", bd=1, relief="groove")
    sec1.pack(fill="x", padx=16, pady=6)

    last_trigger_time = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    DEBOUNCE_DELAY = 0.05

    def trigger_key(num):
        now = time.time()
        if now - last_trigger_time[num] < DEBOUNCE_DELAY:
            return
        last_trigger_time[num] = now
        controller.send_button(num)

    btn_frame = tk.Frame(sec1, bg="#0f172a")
    btn_frame.pack(fill="x", padx=8, pady=8)

    def make_btn(parent, text, subtext, color, active_col, num):
        f = tk.Frame(parent, bg=color, bd=0, relief="flat", cursor="hand2")
        lbl1 = tk.Label(f, text=text, font=("Segoe UI", 11, "bold"), fg="white", bg=color)
        lbl1.pack(pady=(4, 0))
        lbl2 = tk.Label(f, text=subtext, font=("Segoe UI", 8), fg="#e2e8f0", bg=color)
        lbl2.pack(pady=(0, 4))

        def on_click(e=None):
            trigger_key(num)

        f.bind("<Button-1>", on_click)
        lbl1.bind("<Button-1>", on_click)
        lbl2.bind("<Button-1>", on_click)
        return f

    b1 = make_btn(btn_frame, "[ 1 ] FEED", "Lane 1 / Snack", "#c26d05", "#e68407", 1)
    b1.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")

    b2 = make_btn(btn_frame, "[ 2 ] WASH", "Lane 2 / Bubble", "#0369a1", "#0284c7", 2)
    b2.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")

    b3 = make_btn(btn_frame, "[ 3 ] PLAY", "Lane 3 / Reaction", "#be185d", "#db2777", 3)
    b3.grid(row=0, column=2, padx=4, pady=4, sticky="nsew")

    b4 = make_btn(btn_frame, "[ 4 ] SLEEP", "Lane 4 / Rest", "#4d7c0f", "#65a30d", 4)
    b4.grid(row=0, column=3, padx=4, pady=4, sticky="nsew")

    for col in range(4):
        btn_frame.columnconfigure(col, weight=1)

    # Keyboard listeners for 1, 2, 3, 4 (active ONLY when GUI window has focus!)
    for k in ["1", "2", "3", "4"]:
        num = int(k)
        root.bind_all(f"<Key-{k}>", lambda e, n=num: trigger_key(n))
        root.bind_all(f"<KP_{k}>", lambda e, n=num: trigger_key(n))

    # SECTION 2: Manual Stat Setters
    sec2 = tk.LabelFrame(root, text=" 📊 MANUAL STAT CONTROLS ", font=("Segoe UI", 9, "bold"),
                         fg="#cbd5e1", bg="#0f172a", bd=1, relief="groove")
    sec2.pack(fill="x", padx=16, pady=6)

    def send_stat(stat_name, val):
        controller.send_command(f"set {stat_name} {int(val)}")

    stats_grid = tk.Frame(sec2, bg="#0f172a")
    stats_grid.pack(fill="x", padx=10, pady=6)

    stat_defs = [
        ("Hunger (H)", "hunger", hunger_var, "#fb923c"),
        ("Cleanliness (C)", "clean", clean_var, "#38bdf8"),
        ("Happiness (P)", "happy", happy_var, "#f472b6"),
        ("Energy (E)", "energy", energy_var, "#facc15")
    ]

    for idx, (title, s_cmd, var, color) in enumerate(stat_defs):
        lbl = tk.Label(stats_grid, text=title, font=("Segoe UI", 9, "bold"), fg=color, bg="#0f172a", width=14, anchor="w")
        lbl.grid(row=idx, column=0, padx=4, pady=2, sticky="w")

        scale = tk.Scale(stats_grid, from_=0, to=100, orient="horizontal", variable=var,
                         bg="#0f172a", fg="white", highlightthickness=0, troughcolor="#1e293b",
                         activebackground=color, length=240, font=("Segoe UI", 8))
        scale.grid(row=idx, column=1, padx=4, pady=2, sticky="ew")

        btn = tk.Button(stats_grid, text="SET", font=("Segoe UI", 8, "bold"), bg="#334155", fg="white",
                        bd=0, padx=8, pady=2, cursor="hand2",
                        command=lambda sc=s_cmd, v=var: send_stat(sc, v.get()))
        btn.grid(row=idx, column=2, padx=4, pady=2)

    stats_grid.columnconfigure(1, weight=1)

    # Preset Quick Buttons
    preset_frame = tk.Frame(sec2, bg="#0f172a")
    preset_frame.pack(fill="x", padx=10, pady=(2, 8))

    def apply_preset(h, c, p, e):
        hunger_var.set(h)
        clean_var.set(c)
        happy_var.set(p)
        energy_var.set(e)
        controller.send_command(f"set stats {h} {c} {p} {e}")

    tk.Button(preset_frame, text="✨ All 100% (Max)", font=("Segoe UI", 8), bg="#1e293b", fg="#4ade80",
              bd=0, padx=6, pady=3, cursor="hand2",
              command=lambda: apply_preset(100, 100, 100, 100)).pack(side="left", padx=3, expand=True, fill="x")

    tk.Button(preset_frame, text="🥩 Hungry Test (15%)", font=("Segoe UI", 8), bg="#1e293b", fg="#fb923c",
              bd=0, padx=6, pady=3, cursor="hand2",
              command=lambda: apply_preset(15, 80, 80, 80)).pack(side="left", padx=3, expand=True, fill="x")

    tk.Button(preset_frame, text="🧼 Dirty Test (15%)", font=("Segoe UI", 8), bg="#1e293b", fg="#38bdf8",
              bd=0, padx=6, pady=3, cursor="hand2",
              command=lambda: apply_preset(80, 15, 80, 80)).pack(side="left", padx=3, expand=True, fill="x")

    tk.Button(preset_frame, text="💤 Sleepy Test (15%)", font=("Segoe UI", 8), bg="#1e293b", fg="#facc15",
              bd=0, padx=6, pady=3, cursor="hand2",
              command=lambda: apply_preset(80, 80, 80, 15)).pack(side="left", padx=3, expand=True, fill="x")

    # SECTION 3: Animation Player
    sec3 = tk.LabelFrame(root, text=" 🎬 PLAY ANIMATION OVERRIDE ", font=("Segoe UI", 9, "bold"),
                         fg="#cbd5e1", bg="#0f172a", bd=1, relief="groove")
    sec3.pack(fill="x", padx=16, pady=6)

    anim_frame = tk.Frame(sec3, bg="#0f172a")
    anim_frame.pack(fill="x", padx=8, pady=8)

    animations = [
        ("🐱 Idle", "idle", "#334155"),
        ("❤️ Happy", "happy", "#be185d"),
        ("🥩 Hungry", "hungry", "#c26d05"),
        ("🧼 Dirty", "dirty", "#0e7490"),
        ("🍎 Eating", "eating", "#b91c1c"),
        ("💤 Sleep", "sleeping", "#4338ca"),
        ("🥱 Sleepy", "sleepy", "#475569"),
        ("😏 Squint", "squint", "#059669"),
        ("🫧 Wash", "washing", "#0369a1"),
        ("🎮 Play", "playing", "#6d28d9")
    ]

    def trigger_anim(anim_name):
        controller.send_command(f"anim {anim_name}")

    for idx, (label, a_name, col) in enumerate(animations):
        r = idx // 5
        c = idx % 5
        ab = tk.Button(anim_frame, text=label, font=("Segoe UI", 8, "bold"), bg=col, fg="white",
                       bd=0, padx=2, pady=5, cursor="hand2",
                       command=lambda a=a_name: trigger_anim(a))
        ab.grid(row=r, column=c, padx=2, pady=3, sticky="nsew")

    for c in range(5):
        anim_frame.columnconfigure(c, weight=1)

    # SECTION 4: Buzzer Emulator
    sec4_bz = tk.LabelFrame(root, text=" 🔊 BUZZER EMULATOR & SOUND EFFECTS ", font=("Segoe UI", 9, "bold"),
                            fg="#cbd5e1", bg="#0f172a", bd=1, relief="groove")
    sec4_bz.pack(fill="x", padx=16, pady=6)

    bz_top = tk.Frame(sec4_bz, bg="#0f172a")
    bz_top.pack(fill="x", padx=8, pady=(4, 4))

    cb_pc_audio = tk.Checkbutton(bz_top, text="PC Audio (winsound)", variable=buzzer_sound_enabled,
                                 font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#0f172a", selectcolor="#1e293b",
                                 activebackground="#0f172a", activeforeground="#38bdf8")
    cb_pc_audio.pack(side="left")

    def toggle_esp_sound():
        nonlocal esp_sound_on
        esp_sound_on = not esp_sound_on
        controller.send_command(f"sound {'on' if esp_sound_on else 'off'}")
        btn_esp_mute.config(text=f"ESP Buzzer: {'ON' if esp_sound_on else 'OFF'}",
                            fg="#4ade80" if esp_sound_on else "#f87171")

    esp_sound_on = True
    btn_esp_mute = tk.Button(bz_top, text="ESP Buzzer: ON", font=("Segoe UI", 8, "bold"),
                             bg="#1e293b", fg="#4ade80", bd=0, padx=6, pady=2, cursor="hand2",
                             command=toggle_esp_sound)
    btn_esp_mute.pack(side="left", padx=8)

    buzzer_indicator_lbl = tk.Label(bz_top, textvariable=buzzer_indicator_var, font=("Segoe UI", 8, "bold"),
                                    fg="#94a3b8", bg="#1e293b", padx=8, pady=2, relief="solid", bd=1)
    buzzer_indicator_lbl.pack(side="right")

    # SFX Button Grid (2 rows of 5)
    sfx_frame = tk.Frame(sec4_bz, bg="#0f172a")
    sfx_frame.pack(fill="x", padx=8, pady=(2, 6))

    sfx_list = [
        ("🔘 Click", "btn", "#334155"),
        ("🍎 Catch", "catch", "#b91c1c"),
        ("🫧 Pop", "pop", "#0369a1"),
        ("❌ Wrong", "wrong", "#7f1d1d"),
        ("🏆 Win", "win", "#15803d"),
        ("💔 Miss", "miss", "#581c87"),
        ("💤 Sleep", "sleep", "#4338ca"),
        ("☀️ Wake", "wake", "#c26d05"),
        ("🐱 Pet", "pet", "#be185d"),
        ("⚠️ Alert", "alert", "#b45309"),
    ]

    for idx, (label, sfx_id, col) in enumerate(sfx_list):
        r = idx // 5
        c = idx % 5
        sb = tk.Button(sfx_frame, text=label, font=("Segoe UI", 8, "bold"), bg=col, fg="white",
                       bd=0, padx=2, pady=4, cursor="hand2",
                       command=lambda s=sfx_id: controller.send_command(f"buzzer {s}"))
        sb.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")

    for c in range(5):
        sfx_frame.columnconfigure(c, weight=1)

    # SECTION 5: Serial Monitor & Command Input
    sec5 = tk.LabelFrame(root, text=" 🖥️ SERIAL MONITOR ", font=("Segoe UI", 9, "bold"),
                         fg="#cbd5e1", bg="#0f172a", bd=1, relief="groove")
    sec5.pack(fill="both", expand=True, padx=16, pady=(6, 12))

    log_text = scrolledtext.ScrolledText(sec5, bg="#020617", fg="#38bdf8", font=("Consolas", 8), height=7, takefocus=0)
    log_text.pack(fill="both", expand=True, padx=8, pady=(6, 4))
    log_text.config(state="disabled")

    cmd_frame = tk.Frame(sec5, bg="#0f172a")
    cmd_frame.pack(fill="x", padx=8, pady=(0, 6))

    cmd_entry = tk.Entry(cmd_frame, bg="#1e293b", fg="white", font=("Segoe UI", 9), insertbackground="white", bd=0)
    cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=3)

    def send_custom_cmd(e=None):
        txt = cmd_entry.get().strip()
        if txt:
            controller.send_command(txt)
            cmd_entry.delete(0, tk.END)

    cmd_entry.bind("<Return>", send_custom_cmd)

    tk.Button(cmd_frame, text="SEND", font=("Segoe UI", 8, "bold"), bg="#2563eb", fg="white", bd=0, padx=10, pady=2,
              command=send_custom_cmd).pack(side="left", padx=2)

    tk.Button(cmd_frame, text="CLEAR", font=("Segoe UI", 8), bg="#334155", fg="#94a3b8", bd=0, padx=8, pady=2,
              command=lambda: (log_text.config(state="normal"), log_text.delete("1.0", tk.END), log_text.config(state="disabled"))).pack(side="left", padx=2)

    # Initial status fetch
    root.after(800, lambda: controller.send_command("status"))

    def on_closing():
        controller.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def launch_cli(port_name):
    print(f"\n==========================================")
    print(f"  ESP32 TAMAGOTCHI CLI CONTROLLER ({port_name})")
    print(f"==========================================")
    print("Press [1], [2], [3], [4] + ENTER to trigger buttons.")
    print("Commands:")
    print("  set hunger <0-100> | set clean <0-100> | set happy <0-100> | set energy <0-100>")
    print("  set stats <h> <c> <p> <e>")
    print("  anim <idle|happy|hungry|dirty|eating|sleeping|washing|playing>")
    print("  buzzer <btn|catch|pop|wrong|win|miss|sleep|wake|pet|alert>")
    print("  sound on|off | status | feed | wash | play | sleep | quit\n")

    def cli_on_rx(line):
        m = re.search(r"\[SND\]\s+(\d+)\s+(\d+)", line)
        if m:
            freq, dur = int(m.group(1)), int(m.group(2))
            sound_queue.put((freq, dur, True))
        print(line, end="")

    controller = SerialController(port_name, on_receive_callback=cli_on_rx)

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
