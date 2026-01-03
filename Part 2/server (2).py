import socket
import threading

HOST = "127.0.0.1"
PORT = 65432

clients = {}          # user_id -> socket
client_modes = {}     # user_id -> "MENU" | "CHAT" | "COMMON" | "CONFIRM" | "REQUESTING" | "WAIT_CONFIRM"
chat_partner = {}     # user_id -> other_user
common_room = set()   # user_ids currently in the common room
lock = threading.Lock()


# ------------------------
# Helper functions
# ------------------------

def send_to(uid, msg):
    """Send message to a specific user."""
    try:
        clients[uid].sendall(msg.encode())
    except:
        pass


def broadcast(msg, exclude=None):
    """Send a message to all users except the one excluded."""
    for uid in clients:
        if uid != exclude:
            send_to(uid, f"\n{msg}")


def start_chat(u1, u2):
    """Put two users into CHAT mode."""
    with lock:
        client_modes[u1] = "CHAT"
        client_modes[u2] = "CHAT"
        chat_partner[u1] = u2
        chat_partner[u2] = u1

    send_to(u1, f"Server: Chat started with {u2}. Type exit() to leave.\n")
    send_to(u2, f"Server: Chat started with {u1}. Type exit() to leave.\n")


def end_chat(uid):
    """End chat safely for uid and its partner."""
    partner = chat_partner.get(uid)

    chat_partner[uid] = None
    client_modes[uid] = "MENU"

    if partner and partner in clients:
        chat_partner[partner] = None
        client_modes[partner] = "MENU"
        send_to(partner, f"Server: {uid} left the chat.\nMenu:\n1) Connect\n2) Quit\n")

    send_to(uid, "Server: You left the chat.\nMenu:\n1) Connect to user\n2) Quit\n3) Common room\n")


def join_common_room(uid):
    """Move user into the common room."""
    with lock:
        client_modes[uid] = "COMMON"
        common_room.add(uid)
    send_to(uid, "Server: Joined common room. Type exit() to leave.\n")
    broadcast(f"{uid} joined the common room.\n", exclude=uid)


def leave_common_room(uid):
    """Remove user from the common room and return to menu."""
    with lock:
        common_room.discard(uid)
        client_modes[uid] = "MENU"
    send_to(uid, "Server: You left the common room.\nMenu:\n1) Connect to user\n2) Quit\n3) Common room\n")
    broadcast(f"{uid} left the common room.\n", exclude=uid)


def broadcast_common(sender, msg):
    """Broadcast a message within the common room."""
    for uid in list(common_room):
        if uid != sender:
            send_to(uid, msg)


# ------------------------
# Main client loop
# ------------------------

def client_loop(uid):
    conn = clients[uid]
    send_to(uid, "Menu:\n1) Connect to user\n2) Quit\n3) Common room\n\n")

    while True:
        try:
            msg = conn.recv(1024).decode().strip()
        except:
            break

        if not msg:
            break

        mode = client_modes[uid]

        # -------------------------
        # MENU MODE
        # -------------------------
        if mode == "MENU":
            if msg == "1":
                send_to(uid, "Server: Enter user ID:\n")
                client_modes[uid] = "REQUESTING"
                continue

            elif msg == "2":
                break

            elif msg == "3":
                join_common_room(uid)
                continue

            else:
                send_to(uid, "Server: Invalid option.\n1) Connect to user\n2) Quit\n3) Common room\n")

        # -------------------------
        # REQUESTING A USER
        # -------------------------
        elif mode == "REQUESTING":
            target = msg

            with lock:
                if target not in clients:
                    send_to(uid, "Server: User not found.\nMenu:\n1) Connect to user\n2) Quit\n3) Common room\n")
                    client_modes[uid] = "MENU"
                    continue

                if client_modes[target] != "MENU":
                    send_to(uid, "Server: User busy.\nMenu:\n1) Connect to user\n2) Quit\n3) Common room\n")
                    client_modes[uid] = "MENU"
                    continue

                # Ask the target for confirmation
                client_modes[target] = "CONFIRM"
                chat_partner[target] = uid
                send_to(target, f"Server: {uid} wants to chat with you. Accept? (y/n):\n")

            client_modes[uid] = "WAIT_CONFIRM"

        # -------------------------
        # WAITING FOR CONFIRMATION
        # -------------------------
        elif mode == "WAIT_CONFIRM":
            send_to(uid, "Server: Waiting for response...\n")

        # -------------------------
        # CONFIRMING (Target answers y/n)
        # -------------------------
        elif mode == "CONFIRM":
            partner = chat_partner.get(uid)

            if msg.lower() == "y":
                start_chat(uid, partner)
            else:
                send_to(partner, "Server: Request denied.\nMenu:\n1) Connect to user\n2) Quit\n3) Common room\n")
                send_to(uid, "Server: Request denied.\nMenu:\n1) Connect to user\n2) Quit\n3) Common room\n")

                with lock:
                    client_modes[uid] = "MENU"
                    client_modes[partner] = "MENU"
                    chat_partner[uid] = None
                    chat_partner[partner] = None

        # -------------------------
        # CHAT MODE
        # -------------------------
        elif mode == "CHAT":
            if msg == "exit()":
                end_chat(uid)
                continue

            partner = chat_partner.get(uid)
            if partner:
                send_to(partner, f"{uid}: {msg}\n")

        # -------------------------
        # COMMON ROOM MODE
        # -------------------------
        elif mode == "COMMON":
            if msg == "exit()":
                leave_common_room(uid)
                continue
            broadcast_common(uid, f"{uid}: {msg}\n")

    # -------------------------
    # CLEANUP
    # -------------------------
    with lock:
        partner = chat_partner.get(uid)
        if partner:
            end_chat(uid)

        if uid in common_room:
            common_room.discard(uid)
            broadcast(f"{uid} left the common room.\n", exclude=uid)

        del clients[uid]
        del client_modes[uid]
        chat_partner.pop(uid, None)

    conn.close()
    broadcast(f"{uid} disconnected.\n")


# ------------------------
# MAIN SERVER
# ------------------------

def register_and_start(conn):
    """Register a new connection with a unique user ID."""
    try:
        conn.sendall(b"Server: Enter your user ID:\n")
        uid = conn.recv(1024).decode().strip()
        if not uid:
            conn.close()
            return
        while uid in clients:
            conn.sendall(b"Server: User ID taken. Choose another user ID:\n")
            uid = conn.recv(1024).decode().strip()
            if not uid:
                conn.close()
                return
    except:
        conn.close()
        return
    with lock:
        clients[uid] = conn
        client_modes[uid] = "MENU"
        chat_partner[uid] = None

    broadcast(f"{uid} joined the server.\n", exclude=uid)
    threading.Thread(target=client_loop, args=(uid,), daemon=True).start()


def main():
    print("Server running...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(5)

        while True:
            conn, addr = s.accept()
            threading.Thread(target=register_and_start, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
