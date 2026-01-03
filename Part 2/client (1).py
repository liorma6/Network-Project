import socket
import threading
import tkinter as tk
from tkinter import ttk

HOST = "127.0.0.1"
PORT = 65432


class ChatClient:
    # Network-only client; GUI interacts through callbacks.
    def __init__(self, host, port, on_message, on_disconnect):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.sock = None
        self._receiver_thread = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def start(self):
        self._receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self._receiver_thread.start()

    def _receiver_loop(self):
        while True:
            try:
                msg = self.sock.recv(1024).decode()
                if not msg:
                    self.on_disconnect()
                    break
                self.on_message(msg)
            except:
                self.on_disconnect()
                break

    def send(self, text):
        try:
            self.sock.sendall(text.encode())
            return True
        except:
            return False

    def close(self):
        if self.sock:
            self.sock.close()


class ChatGUI:
    def __init__(self):
        self.client = ChatClient(
            HOST,
            PORT,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )
        self.awaiting_user_id = True
        self.mode = "LOGIN"
        self.root = tk.Tk()
        self.root.title("Private Chat")
        self.root.geometry("420x640")
        self.root.configure(bg="#f3f1ea")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#0b6e4f")
        header.pack(fill="x")
        tk.Label(
            header,
            text="Private Chat",
            fg="white",
            bg="#0b6e4f",
            font=("Helvetica", 14, "bold"),
            pady=10,
        ).pack()

        user_id_frame = tk.Frame(self.root, bg="#f3f1ea", padx=10, pady=8)
        user_id_frame.pack(fill="x")
        tk.Label(
            user_id_frame,
            text="User ID",
            bg="#f3f1ea",
            fg="#444",
            font=("Helvetica", 10, "bold"),
        ).pack(side="left")
        self.user_id_entry = tk.Entry(user_id_frame, font=("Helvetica", 11))
        self.user_id_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.user_id_entry.bind("<Return>", self.on_set_user_id)
        self.user_id_btn = tk.Button(
            user_id_frame,
            text="Set",
            command=self.on_set_user_id,
            bg="#0b6e4f",
            fg="white",
            activebackground="#0a5f44",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=4,
        )
        self.user_id_btn.pack(side="right")

        body = tk.Frame(self.root, bg="#f3f1ea")
        body.pack(fill="both", expand=True)

        self.chat_text = tk.Text(
            body,
            wrap="word",
            bg="#f3f1ea",
            fg="#222",
            font=("Helvetica", 11),
            state="disabled",
            padx=10,
            pady=10,
            borderwidth=0,
            highlightthickness=0,
        )
        self.chat_text.pack(fill="both", expand=True, side="left")
        self.chat_text.tag_configure(
            "self_msg",
            background="#cfeedd",
            foreground="#1f3d2b",
            borderwidth=1,
            relief="solid",
            lmargin1=10,
            lmargin2=10,
            rmargin=80,
            spacing1=4,
            spacing3=4,
            justify="left",
        )
        self.chat_text.tag_configure(
            "other_msg",
            background="#ffffff",
            foreground="#222",
            borderwidth=1,
            relief="solid",
            lmargin1=10,
            lmargin2=10,
            rmargin=80,
            spacing1=4,
            spacing3=4,
            justify="left",
        )
        self.chat_text.tag_configure(
            "server_msg",
            background="#e6e6e6",
            foreground="#333",
            lmargin1=10,
            lmargin2=10,
            rmargin=10,
            spacing1=6,
            spacing3=6,
            justify="left",
        )

        scrollbar = ttk.Scrollbar(body, command=self.chat_text.yview)
        scrollbar.pack(fill="y", side="right")
        self.chat_text.configure(yscrollcommand=scrollbar.set)

        composer = tk.Frame(self.root, bg="#e9e6dc", padx=8, pady=8)
        composer.pack(fill="x")

        self.entry = tk.Entry(composer, font=("Helvetica", 11))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.on_send)

        self.send_btn = tk.Button(
            composer,
            text="Send",
            command=self.on_send,
            bg="#0b6e4f",
            fg="white",
            activebackground="#0a5f44",
            activeforeground="white",
            relief="flat",
            padx=16,
            pady=6,
        )
        self.send_btn.pack(side="right")

        self._set_login_mode(True)

    def append_message(self, text, tag=None):
        self.chat_text.configure(state="normal")
        if tag:
            self.chat_text.insert("end", text, tag)
        else:
            self.chat_text.insert("end", text)
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def _handle_message(self, msg):
        self._update_mode_from_message(msg)
        # Ensure UI updates run on the Tk main thread.
        if "your user ID" in msg or "User ID taken" in msg:
            self.root.after(0, self._set_login_mode, True)
        if msg and not msg.endswith("\n"):
            msg = f"{msg}\n"
        tag = self._tag_for_message(msg)
        self.root.after(0, self.append_message, msg, tag)

    def _handle_disconnect(self):
        self.root.after(0, self.append_message, "\nDisconnected from server.\n")

    def _update_mode_from_message(self, msg):
        if "Chat started with" in msg:
            self.mode = "CHAT"
        elif "Joined common room" in msg:
            self.mode = "COMMON"
        elif "You left the common room" in msg or "You left the chat" in msg or msg.startswith("Menu:"):
            self.mode = "MENU"
        elif "your user ID" in msg or "User ID taken" in msg:
            self.mode = "LOGIN"

    def _tag_for_message(self, msg):
        if msg.startswith("Server:") or msg.startswith("Menu:"):
            return "server_msg"
        if "joined the server" in msg or "disconnected" in msg:
            return "server_msg"
        if "joined the common room" in msg or "left the common room" in msg:
            return "server_msg"
        return "other_msg"

    def _set_login_mode(self, enabled):
        # Toggle between user-id entry and chat input.
        self.awaiting_user_id = enabled
        if enabled:
            self.mode = "LOGIN"
            self.user_id_entry.configure(state="normal")
            self.user_id_btn.configure(state="normal")
            self.entry.configure(state="disabled")
            self.send_btn.configure(state="disabled")
            self.user_id_entry.focus_set()
        else:
            self.user_id_entry.configure(state="disabled")
            self.user_id_btn.configure(state="disabled")
            self.entry.configure(state="normal")
            self.send_btn.configure(state="normal")
            self.entry.focus_set()

    def on_set_user_id(self, event=None):
        text = self.user_id_entry.get().strip()
        if not text:
            return
        if not self.client.send(text):
            self.append_message("\nFailed to send user ID.\n")
            return
        self.user_id_entry.delete(0, "end")
        self._set_login_mode(False)

    def on_send(self, event=None):
        text = self.entry.get().strip()
        if not text:
            return
        if not self.client.send(text):
            self.append_message("\nFailed to send message.\n")
            return
        if self.mode in ("CHAT", "COMMON") and text != "exit()":
            self.append_message(f"You: {text}\n", "self_msg")
        self.entry.delete(0, "end")

    def on_close(self):
        try:
            self.client.close()
        finally:
            self.root.destroy()

    def run(self):
        self.client.connect()
        self.client.start()
        self.root.mainloop()


def main():
    app = ChatGUI()
    app.run()


if __name__ == "__main__":
    main()
