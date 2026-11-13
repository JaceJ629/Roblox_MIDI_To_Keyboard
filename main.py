import mido
import time
import keyboard as kb
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pynput.keyboard import Controller, Key

keyboard = Controller()

SPEED = 1

KEY_SEQUENCE = list("1!2@34$5%6^78*9(0qQwWeErtTyYuiIoOpPasSdDfgGhHjJklLzZxcCvVbBnm")
BASE_MIDI = 36

VELOCITY_LEVELS = 8
current_velocity = 0

held_notes = {}
sustain_held = False
stop_event = threading.Event()
playing = False


def get_key(note):
    index = note - BASE_MIDI

    if 0 <= index < len(KEY_SEQUENCE):
        return KEY_SEQUENCE[index]

    return None


def get_base_key(k):
    return {
        '!': '1',
        '@': '2',
        '$': '4',
        '%': '5',
        '^': '6',
        '*': '8',
        '(': '9'
    }.get(k, k.lower() if k.isupper() else k)


def press_key(k):
    if k.isupper() or k in "!@$%^*(":
        base = get_base_key(k)
        keyboard.press(Key.shift)
        keyboard.press(base)
        keyboard.release(Key.shift)
    else:
        keyboard.press(k)


def release_key(k):
    if k.isupper() or k in "!@$%^*(":
        keyboard.release(get_base_key(k))
    else:
        keyboard.release(k)


def release_all():
    global sustain_held

    for note, key in list(held_notes.items()):
        release_key(key)

    held_notes.clear()

    if sustain_held:
        keyboard.release(Key.space)
        sustain_held = False


def set_velocity(velocity):
    global current_velocity

    velocity = max(1, min(127, velocity))
    target_level = round((velocity - 1) / 126 * (VELOCITY_LEVELS - 1))

    while current_velocity < target_level:
        keyboard.press(Key.page_up)
        keyboard.release(Key.page_up)
        current_velocity += 1
        time.sleep(0.01)

    while current_velocity > target_level:
        keyboard.press(Key.page_down)
        keyboard.release(Key.page_down)
        current_velocity -= 1
        time.sleep(0.01)


def reset_velocity():
    global current_velocity

    for _ in range(8):
        keyboard.press(Key.page_down)
        keyboard.release(Key.page_down)
        time.sleep(0.01)

    current_velocity = 0


def play_midi(path, use_velocity, use_sustain):
    global playing, sustain_held

    try:
        midi = mido.MidiFile(path)

        if use_velocity:
            reset_velocity()

        root.after(0, lambda: status_label.config(text="Playing..."))

        for msg in midi:
            if stop_event.is_set():
                break

            if stop_event.wait(msg.time / SPEED):
                break

            if msg.type == "note_on" and msg.velocity > 0:
                if use_velocity:
                    set_velocity(msg.velocity)

                key = get_key(msg.note)

                if key:
                    press_key(key)
                    held_notes[msg.note] = key

            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                if msg.note in held_notes:
                    release_key(held_notes[msg.note])
                    del held_notes[msg.note]

            elif msg.type == "control_change" and msg.control == 64:
                if use_sustain:
                    if msg.value >= 64 and not sustain_held:
                        keyboard.press(Key.space)
                        sustain_held = True

                    elif msg.value < 64 and sustain_held:
                        keyboard.release(Key.space)
                        sustain_held = False

    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Playback Error", str(e)))

    finally:
        release_all()
        playing = False
        stop_event.clear()
        root.after(0, lambda: status_label.config(text="Ready"))


def select_file():
    path = filedialog.askopenfilename(
        title="Select MIDI File",
        filetypes=[("MIDI Files", "*.mid *.midi")]
    )

    if path:
        file_path.set(path)


def start_playback():
    global playing

    path = file_path.get()

    if not path:
        messagebox.showwarning("No File", "Please select a MIDI file first.")
        return

    if playing:
        return

    playing = True
    stop_event.clear()

    use_velocity = velocity_enabled.get()
    use_sustain = sustain_enabled.get()

    status_label.config(text="Starting in 3 seconds...")

    def countdown():
        for i in range(3, 0, -1):
            if stop_event.wait(1):
                playing = False
                root.after(0, lambda: status_label.config(text="Ready"))
                return

            root.after(0, lambda i=i: status_label.config(
                text=f"Starting in {i - 1} seconds..."
            ))

        if not stop_event.is_set():
            threading.Thread(
                target=play_midi,
                args=(path, use_velocity, use_sustain),
                daemon=True
            ).start()

    threading.Thread(target=countdown, daemon=True).start()


def stop_playback():
    if playing:
        stop_event.set()
        release_all()
        status_label.config(text="Stopping playback...")


def update_status(text):
    status_label.config(text=text)


def on_close():
    stop_event.set()
    release_all()
    root.destroy()


# GUI
root = tk.Tk()
root.title("Roblox MIDI Player")
root.geometry("550x225")
root.resizable(False, False)

file_path = tk.StringVar()
velocity_enabled = tk.BooleanVar(value=True)
sustain_enabled = tk.BooleanVar(value=True)

tk.Label(root, text="MIDI File:").pack(pady=(15, 5))

file_frame = tk.Frame(root)
file_frame.pack()

tk.Entry(
    file_frame,
    textvariable=file_path,
    width=48
).pack(side=tk.LEFT, padx=5)

tk.Button(
    file_frame,
    text="Browse",
    command=select_file
).pack(side=tk.LEFT)

tk.Checkbutton(
    root,
    text="Enable Velocity",
    variable=velocity_enabled
).pack(pady=(10, 0))

tk.Checkbutton(
    root,
    text="Enable Sustain",
    variable=sustain_enabled
).pack()

button_frame = tk.Frame(root)
button_frame.pack(pady=10)

tk.Button(
    button_frame,
    text="Play",
    width=12,
    command=start_playback
).pack(side=tk.LEFT, padx=5)

tk.Button(
    button_frame,
    text="Stop (ESC)",
    width=12,
    command=stop_playback
).pack(side=tk.LEFT, padx=5)

status_label = tk.Label(root, text="Ready")
status_label.pack()

# Global ESC shortcut
kb.add_hotkey("esc", stop_playback)

# ESC also works when the GUI is focused
root.bind("<Escape>", lambda event: stop_playback())

root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()