#!/usr/bin/env python3
import asyncio
import websockets
import docker
import json
import tempfile
import os
import tarfile
import logging
import yaml
import misaka

containers = dict()
containerpath = dict()
client = docker.from_env()

config = dict()
with open("config.yaml") as f:
    config = yaml.load(f, Loader=yaml.Loader)
print(config)
homedirlen = len(config["homedir"])
textdir = os.listdir("text")
textdir.sort()
text = []
for file in textdir:
    filename = f"text/{file}"
    if os.path.isfile(filename):
        with open(filename) as f:
            text.append(misaka.html(f.read(), extensions=("fenced-code",)))
print(text)
    
def handle_command(message, containerkey):
    container = containers[containerkey]

    response = ""
    if message["type"] == "command":
        cmd = message["content"]
        # TODO: maybe add logging?
        logging.info("")
        
        #print(f"< {cmd} {websocket.remote_address}")
        print(f"< {cmd} {containerpath[containerkey]}")
        (_, output) = container.exec_run(f"term {containerpath[containerkey]} {cmd}", user=config["user"])

        # TODO: Remove print
        print(output)

        response = output.decode("utf-8")

        containerpath[containerkey] = json.loads(response)["path"]
    elif message["type"] == "file":
        path = containerpath[containerkey]
        print(path)
        #TODO: figure out a better way to find the user home directory
        if path[:homedirlen] == config["homedir"]:
            with tempfile.TemporaryDirectory() as tmp:
                binstring = message["content"]
                filepath = os.path.join(tmp, message["name"])
                tarpath = os.path.join(tmp, "upload.tar")
                with open(filepath, "w+") as f:
                    f.write(binstring)

                with tarfile.open(name=tarpath, mode="x") as tar:
                    tar.addfile(tarfile.TarInfo(message["name"]), open(filepath))

                with open(tarpath) as f:
                    tarbytes = f.read()

                container.put_archive(path, tarbytes)
                response = json.dumps({"status": "ok"})
        else:
            response = json.dumps({"status": "error", "message": "Can only upload in the users home"})
    elif message["type"] == "reconnection":
        for command in message["commands"]:
            handle_command(command, containerkey)
        response = json.dumps({"status": "ok"})
    else:
        response = json.dumps({"status": "error", "message": "An unexpected error happened"})

    return response


async def command(websocket, path):
    (host, port) = websocket.remote_address
    containerkey = f"{host}:{port}"
    try:
        await websocket.send(json.dumps({"text": text}))
        while True:
            message = json.loads(await websocket.recv())
            if not containerkey in containers:
                print("creating container")
                container = client.containers.run(config["docker-image"], hostname=config["docker-hostname"], detach=True)
                containers[containerkey] = container
                containerpath[containerkey] = config["homedir"]

            response = handle_command(message, containerkey)

            await websocket.send(response)
    except websockets.ConnectionClosed:
        containers[containerkey].kill()
        containers[containerkey].remove()
        print(f"Connection closed - time to clean up - {websocket.remote_address}")

start_server = websockets.serve(command, config["websocket-host"], 1337, max_size=2**25)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()