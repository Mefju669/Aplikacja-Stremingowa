import socket
import threading

HOST = "192.168.248.20"
PORT = 9090

name = input("Choose a name:")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.connect((HOST, PORT))

axis_positions = ["L3_X", "L3_Y", "L3_Z", "R3_X", "R3_Y", "R3_Z"]
button_states = ["Button L1", "Button R1", "Triangle", "Square", "Circle", "Cross", "Start", "Select", "UP/DOWN", "LEFT/RIGHT"]


def convert_mes_to_table(data):
    data = data.replace("data|", "").replace("|!", "")
    rows = data.split(';')

    table = []
    for row in rows:
        if row:
            columns = row.split('|')
            table.append(columns)

    return table


def translate_input(data):
    translated = []
    axis_data = data[0].split(',')
    button_data = data[1].split(',')

    for i in range(6):
        translated.append(f"{axis_positions[i]}: {axis_data[i]}")

    for i in range(10):
        translated.append(f"{button_states[i]}: {'Pressed' if button_data[i] != '0' else 'Released'}")

    return translated


def receive_messages():
    while True:
        try:
            reply = server.recv(4096).decode("ascii")
            if reply == "NAME":
                server.sendall(name.encode("ascii"))
            else:
                table = convert_mes_to_table(reply)
                for row in table:
                    translated_row = translate_input(row)
                    for item in translated_row:
                        print(item)
        except Exception as e:
            print(f"An error occurred: {e}")
            server.close()
            break


def send_message():
    while True:
        message = f"{input('napisz wiadomosc')}"
        server.send(message.encode("ascii"))


receive_thread = threading.Thread(target=receive_messages)
receive_thread.start()

send_thread = threading.Thread(target=send_message)
send_thread.start()
