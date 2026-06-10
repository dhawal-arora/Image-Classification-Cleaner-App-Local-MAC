import tkinter as tk

from config import BG


def ask_password(root: tk.Tk, title: str, prompt: str,
                 confirm: bool = False) -> str | None:
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.configure(bg=BG)
    dialog.geometry("420x230" if confirm else "420x165")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.lift()

    result = [None]

    tk.Label(dialog, text=prompt, bg=BG, fg="#ccc",
             font=("Helvetica Neue", 13), wraplength=380).pack(pady=(18, 6), padx=20)

    e1 = tk.Entry(dialog, show="*", font=("Helvetica Neue", 13),
                  bg="#222", fg="white", insertbackground="white",
                  relief="flat", width=28)
    e1.pack(pady=4)
    e1.focus_set()

    e2 = None
    if confirm:
        tk.Label(dialog, text="Confirm password", bg=BG, fg="#666",
                 font=("Helvetica Neue", 11)).pack(pady=(8, 2))
        e2 = tk.Entry(dialog, show="*", font=("Helvetica Neue", 13),
                      bg="#222", fg="white", insertbackground="white",
                      relief="flat", width=28)
        e2.pack(pady=4)

    err_lbl = tk.Label(dialog, text="", bg=BG, fg="#e05555",
                       font=("Helvetica Neue", 11))
    err_lbl.pack()

    def ok(e=None):
        pw = e1.get()
        if not pw:
            return
        if e2 is not None and pw != e2.get():
            err_lbl.config(text="Passwords do not match")
            return
        result[0] = pw
        dialog.destroy()

    e1.bind("<Return>", ok)
    if e2:
        e2.bind("<Return>", ok)
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    tk.Label(dialog, text="  OK  ", bg="#333", fg="#ccc",
             font=("Helvetica Neue", 12), padx=16, pady=6,
             cursor="hand2").pack(pady=6)
    dialog.children[list(dialog.children)[-1]].bind("<Button-1>", ok)

    dialog.wait_window()
    return result[0]
