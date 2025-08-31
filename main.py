import tkinter as tk
from tkinter import simpledialog, messagebox
import keyboard
from pynput import mouse
import threading
import time

# ------------- Drag & Drop Listbox -------------
class DragListbox(tk.Listbox):
    def __init__(self, master, app_ref, **kw):
        super().__init__(master, **kw)
        self.app = app_ref
        self.bind('<Button-1>', self.set_current)
        self.bind('<B1-Motion>', self.shift_selection)
        self['selectmode'] = tk.SINGLE

    def set_current(self, event):
        self.current_index = self.nearest(event.y)

    def shift_selection(self, event):
        i = self.nearest(event.y)
        if i != self.current_index:
            # swap data
            self.app.events[i], self.app.events[self.current_index] = \
                self.app.events[self.current_index], self.app.events[i]
            # swap visual
            val = self.get(self.current_index)
            self.delete(self.current_index)
            self.insert(i, val)
            self.current_index = i
            self.selection_clear(0, tk.END)
            self.selection_set(i)

class KeyLoopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Клавиши + мышь + тайминг")
        self.root.geometry("660x560")
        self.root.resizable(False, False)

        # events: [('key'|'mouse', value, delay), ...]
        self.events = []
        self.running = False
        self.listening = False

        self.hotkey_start = "F7"
        self.hotkey_stop = "F8"

        # ---------- Toolbar ----------
        toolbar = tk.Frame(root)
        toolbar.pack(pady=8)

        self.listen_btn = tk.Button(toolbar, text="Слушать", width=12, command=self.toggle_listening)
        self.listen_btn.pack(side=tk.LEFT, padx=4)

        self.start_btn = tk.Button(toolbar, text=f"Старт ({self.hotkey_start})", command=self.start_loop)
        self.start_btn.pack(side=tk.LEFT, padx=4)

        self.stop_btn = tk.Button(toolbar, text=f"Стоп ({self.hotkey_stop})", command=self.stop_loop)
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        self.settings_btn = tk.Button(toolbar, text="⚙️", width=3, command=self.open_settings)
        self.settings_btn.pack(side=tk.LEFT, padx=4)

        # ---------- Event List (Drag & Drop) ----------
        list_frame = tk.Frame(root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.event_listbox = DragListbox(list_frame, self, height=15, width=70)
        self.event_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(list_frame, orient="vertical")
        sb.config(command=self.event_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.event_listbox.config(yscrollcommand=sb.set)

        # double click to edit timing
        self.event_listbox.bind("<Double-1>", lambda e: self.edit_timing())

        # ---------- Controls ----------
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=6)

        tk.Button(btn_frame, text="Удалить", width=10, command=self.delete_selected).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Изменить тайминг", width=16, command=self.edit_timing).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Очистить", width=10, command=self.clear_events).pack(side=tk.LEFT, padx=4)

        # ---------- Mouse Listener ----------
        self.mouse_listener = None
        self.bind_hotkeys()

    # ------------------ Listen / Stop Listen ------------------
    def toggle_listening(self):
        if not self.listening:
            self.listening = True
            self.listen_btn.config(text="Стоп слушать")
            keyboard.on_press(self.on_key_event)
            self.start_mouse_listener()
        else:
            self.listening = False
            self.listen_btn.config(text="Слушать")
            keyboard.unhook_all()
            self.stop_mouse_listener()
            self.bind_hotkeys()

    def start_mouse_listener(self):
        def on_click(x, y, button, pressed):
            if not pressed or not self.listening:
                return
            btn_name = str(button).replace('Button.', '')
            if btn_name == 'left':
                widget_under = self.root.winfo_containing(x, y)
                if isinstance(widget_under, tk.Button):
                    return
            self.events.append(('mouse', btn_name, 0.1))
            self.refresh_listbox()

        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.start()

    def stop_mouse_listener(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

    def on_key_event(self, event):
        if self.listening:
            self.events.append(('key', event.name, 0.1))
            self.refresh_listbox()

    # ------------------ List Management ------------------
    def delete_selected(self):
        idx = self.event_listbox.curselection()
        if idx:
            idx = idx[0]
            self.events.pop(idx)
            self.refresh_listbox()

    def clear_events(self):
        self.events.clear()
        self.refresh_listbox()

    def refresh_listbox(self):
        self.event_listbox.delete(0, tk.END)
        for typ, val, delay in self.events:
            icon = "⌨️" if typ == "key" else "🖱️"
            self.event_listbox.insert(tk.END, f"{icon} {val:<15}  {delay:.2f} с")

    # ------------------ Edit Timing ------------------
    def edit_timing(self):
        idx = self.event_listbox.curselection()
        if not idx:
            messagebox.showwarning("Предупреждение", "Выберите строку для изменения тайминга.")
            return
        idx = idx[0]
        _, val, old_delay = self.events[idx]
        new_delay = simpledialog.askfloat("Тайминг", f"Задержка перед «{val}» (сек):", initialvalue=old_delay, minvalue=0.01)
        if new_delay is not None:
            self.events[idx] = (self.events[idx][0], val, new_delay)
            self.refresh_listbox()

    # ------------------ Playback Loop ------------------
    def start_loop(self):
        if not self.events:
            messagebox.showwarning("Предупреждение", "Список событий пуст!")
            return
        if self.running:
            return
        self.running = True

        def loop():
            while self.running:
                for typ, val, delay in self.events:
                    if not self.running:
                        break
                    if typ == 'key':
                        keyboard.send(val)
                    elif typ == 'mouse':
                        keyboard.send(val)
                    time.sleep(delay)
                time.sleep(0.2)
        threading.Thread(target=loop, daemon=True).start()

    def stop_loop(self):
        self.running = False

    # ------------------ Hotkeys Settings ------------------
    def open_settings(self):
        top = tk.Toplevel(self.root)
        top.title("Настройки горячих клавиш")
        top.geometry("300x160")
        top.resizable(False, False)
        top.grab_set()

        tk.Label(top, text="Горячая клавиша СТАРТ:").pack(pady=4)
        start_var = tk.StringVar(value=self.hotkey_start)
        tk.Entry(top, textvariable=start_var, justify="center").pack()

        tk.Label(top, text="Горячая клавиша СТОП:").pack(pady=4)
        stop_var = tk.StringVar(value=self.hotkey_stop)
        tk.Entry(top, textvariable=stop_var, justify="center").pack()

        def save():
            new_start = start_var.get().strip()
            new_stop = stop_var.get().strip()
            if not new_start or not new_stop:
                messagebox.showerror("Ошибка", "Клавиши не могут быть пустыми.")
                return
            try:
                keyboard.unhook_all_hotkeys()
                keyboard.add_hotkey(new_start, self.start_loop)
                keyboard.add_hotkey(new_stop, self.stop_loop)
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
                self.bind_hotkeys()
                return

            self.hotkey_start = new_start
            self.hotkey_stop = new_stop
            self.start_btn.config(text=f"Старт ({self.hotkey_start})")
            self.stop_btn.config(text=f"Стоп ({self.hotkey_stop})")
            top.destroy()

        tk.Button(top, text="Сохранить", command=save).pack(pady=10)

    def bind_hotkeys(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        try:
            keyboard.add_hotkey(self.hotkey_start, self.start_loop)
            keyboard.add_hotkey(self.hotkey_stop, self.stop_loop)
        except Exception as e:
            print("bind_hotkeys error:", e)

# ------------- Run -------------
if __name__ == "__main__":
    root = tk.Tk()
    app = KeyLoopApp(root)
    root.mainloop()