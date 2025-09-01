import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog, messagebox
import keyboard
from pynput import mouse
import threading
import time
import json
import os

CONFIG_DIR = "configs"
os.makedirs(CONFIG_DIR, exist_ok=True)

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
            self.app.events[i], self.app.events[self.current_index] = \
                self.app.events[self.current_index], self.app.events[i]
            val = self.get(self.current_index)
            self.delete(self.current_index)
            self.insert(i, val)
            self.current_index = i
            self.selection_clear(0, tk.END)
            self.selection_set(i)

class KeyLoopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoKeySequencer")
        self.root.geometry("720x620")
        self.root.resizable(False, False)

        # events: [('key'|'mouse', value, delay, mode), ...]
        self.events = []
        self.running = False
        self.listening = False
        self.current_config = None

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

        # ---------- Config Controls ----------
        cfg_frame = tk.Frame(root)
        cfg_frame.pack(pady=4)

        tk.Label(cfg_frame, text="Конфиг:").pack(side=tk.LEFT)
        self.config_combo = ttk.Combobox(cfg_frame, width=25, state="readonly")
        self.config_combo.pack(side=tk.LEFT, padx=4)
        self.config_combo.bind("<<ComboboxSelected>>", self.on_config_selected)

        tk.Button(cfg_frame, text="Сохранить", width=10, command=self.save_config).pack(side=tk.LEFT, padx=4)
        tk.Button(cfg_frame, text="Сохранить как", width=12, command=self.save_config_as).pack(side=tk.LEFT, padx=4)
        tk.Button(cfg_frame, text="Удалить", width=10, command=self.delete_config).pack(side=tk.LEFT, padx=4)
        tk.Button(cfg_frame, text="Обновить", width=10, command=self.refresh_configs).pack(side=tk.LEFT, padx=4)

        # ---------- Event List ----------
        list_frame = tk.Frame(root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.event_listbox = DragListbox(list_frame, self, height=16, width=80)
        self.event_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(list_frame, orient="vertical")
        sb.config(command=self.event_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.event_listbox.config(yscrollcommand=sb.set)

        # ---------- Controls ----------
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=6)

        tk.Button(btn_frame, text="Удалить", width=10, command=self.delete_selected).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Изменить параметры кнопки", width=22,
                  command=self.edit_event_params).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Очистить", width=10, command=self.clear_events).pack(side=tk.LEFT, padx=4)

        # ---------- Mouse Listener ----------
        self.mouse_listener = None
        self.bind_hotkeys()
        self.refresh_configs()
        self.load_last_or_default()

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
            self.add_event('mouse', btn_name)  # ### NEW
        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.start()

    def stop_mouse_listener(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

    def on_key_event(self, event):
        if self.listening:
            self.add_event('key', event.name)  # ### NEW

    # ---------- NEW: добавление события без диалога ----------
    def add_event(self, typ, val):
        self.events.append((typ, val, 0.1, "press"))  # по умолчанию "press"
        self.refresh_listbox()
    # ---------- END NEW ----------

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
        for typ, val, delay, mode in self.events:
            icon = "⌨️" if typ == "key" else "🖱️"
            m = "P" if mode == "press" else "H"
            self.event_listbox.insert(tk.END,
                                      f"{icon} {val:<12} {m}  {delay:.2f} с")

    # ---------- изменение параметров события ----------
    def edit_event_params(self):
        idx = self.event_listbox.curselection()
        if not idx:
            messagebox.showwarning("Предупреждение",
                                   "Выберите строку для изменения параметров.")
            return
        idx = idx[0]
        typ, val, old_delay, old_mode = self.events[idx]

        top = tk.Toplevel(self.root)
        top.title("Изменить параметры")
        top.geometry("250x180")
        top.resizable(False, False)
        top.grab_set()

        tk.Label(top, text="Задержка (сек):").pack(pady=2)
        delay_var = tk.DoubleVar(value=old_delay)
        tk.Spinbox(top, from_=0.01, to=60, increment=0.1,
                   textvariable=delay_var, width=8, justify="center").pack()

        mode_var = tk.StringVar(value=old_mode)
        tk.Label(top, text="Режим:").pack(pady=5)
        tk.Radiobutton(top, text="Нажать", variable=mode_var,
                       value="press").pack(anchor='w')
        tk.Radiobutton(top, text="Зажать", variable=mode_var,
                       value="hold").pack(anchor='w')

        def save():
            try:
                new_delay = float(delay_var.get())
            except ValueError:
                new_delay = 0.1
            new_mode = mode_var.get()
            self.events[idx] = (typ, val, new_delay, new_mode)
            self.refresh_listbox()
            top.destroy()

        tk.Button(top, text="Сохранить", command=save).pack(pady=8)

    # ------------------ Config I/O ------------------
    def refresh_configs(self):
        files = [f for f in os.listdir(CONFIG_DIR) if f.endswith('.json')]
        self.config_combo['values'] = files
        if files and self.config_combo.get() not in files:
            self.config_combo.current(0)

    def load_last_or_default(self):
        files = self.config_combo['values']
        if files:
            self.config_combo.current(0)
            self.load_config(os.path.join(CONFIG_DIR, files[0]))

    def on_config_selected(self, event):
        cfg_name = self.config_combo.get()
        if cfg_name:
            self.load_config(os.path.join(CONFIG_DIR, cfg_name))

    def load_config(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            fixed = []
            for item in loaded:
                if len(item) == 3:
                    fixed.append(item + ["press"])
                elif len(item) == 4:
                    fixed.append(item)
                else:
                    raise ValueError("Неверный формат конфига")
            self.events = fixed
            self.current_config = os.path.basename(path)
            self.refresh_listbox()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить конфиг:\n{e}")

    def save_config(self):
        if not self.current_config:
            self.save_config_as()
            return
        path = os.path.join(CONFIG_DIR, self.current_config)
        self._write_config(path)

    def save_config_as(self):
        cfg_name = simpledialog.askstring("Сохранить как", "Имя конфига:", initialvalue="my_sequence")
        if not cfg_name:
            return
        if not cfg_name.endswith('.json'):
            cfg_name += '.json'
        path = os.path.join(CONFIG_DIR, cfg_name)
        self._write_config(path)
        self.current_config = cfg_name
        self.refresh_configs()
        self.config_combo.set(cfg_name)

    def _write_config(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Сохранено", f"Конфиг сохранён:\n{os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")

    def delete_config(self):
        cfg_name = self.config_combo.get()
        if not cfg_name:
            messagebox.showwarning("Предупреждение", "Выберите конфиг для удаления.")
            return
        path = os.path.join(CONFIG_DIR, cfg_name)
        if messagebox.askyesno("Удалить", f"Удалить конфиг «{cfg_name}»?"):
            try:
                os.remove(path)
                self.refresh_configs()
                self.clear_events()
                self.current_config = None
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

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
                for typ, val, delay, mode in self.events:
                    if not self.running:
                        break
                    if typ == 'key':
                        if mode == "press":
                            keyboard.send(val)
                        else:
                            keyboard.press(val)
                            time.sleep(delay)
                            keyboard.release(val)
                    elif typ == 'mouse':
                        if mode == "press":
                            keyboard.send(val)
                        else:
                            keyboard.press(val)
                            time.sleep(delay)
                            keyboard.release(val)
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