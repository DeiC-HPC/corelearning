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
import functools

client = docker.from_env()

config = dict()
with open("config.yaml") as f:
    config = yaml.load(f, Loader=yaml.Loader)
homedirlen = len(config["homedir"])
textdir = os.listdir("text")
textdir.sort()
text = []
for file in textdir:
    filename = f"text/{file}"
    if os.path.isfile(filename):
        with open(filename) as f:
            text.append(misaka.html(f.read(), extensions=("fenced-code",)))

class CoreContainer:
    def __init__(self, dockerimage, hostname, path, user, homedir):
        self.__container = client.containers.run(dockerimage, hostname=hostname, detach=True)
        self.__path = path
        self.__user = user
        self.__homedir = homedir
        self.__exec_cmd = functools.partial(self.__container.exec_run, user=self.__user)

    async def run_command_in_container(self, cmd):
        loop = asyncio.get_running_loop()
        (_, output) = await loop.run_in_executor(None, self.__exec_cmd, f"term {self.__path} {cmd}")

        response = output.decode("utf-8")
        self.__path = json.loads(response)["path"]

        return response

    async def put_file_in_container(self, name, content):
        if self.__path.startswith(self.__homedir):
            loop = asyncio.get_running_loop()
            with tempfile.TemporaryDirectory() as tmp:
                filepath = os.path.join(tmp, name)
                tarpath = os.path.join(tmp, "upload.tar")
                with open(filepath, "w+") as f:
                    f.write(content)

                with tarfile.open(name=tarpath, mode="x") as tar:
                    tar.add(filepath, arcname=name)

                with open(tarpath) as f:
                    tarbytes = f.read()

                await loop.run_in_executor(None, self.__container.put_archive, self.__path, tarbytes)
            return json.dumps({"status": "ok"})
        else:
            return json.dumps({"status": "error", "message": "Can only upload in the users home"})

    async def kill_and_remove(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None,self.__container.kill)
        await loop.run_in_executor(None,self.__container.remove)

    async def get_commands(self):
        loop = asyncio.get_running_loop()
        (_, output) = await loop.run_in_executor(None, self.__exec_cmd, "/bin/bash -c 'compgen -c'")
        return json.dumps({ "commands": output.decode("utf-8").split() })

    async def get_files(self):
        loop = asyncio.get_running_loop()
        (_, output) = await loop.run_in_executor(None, self.__exec_cmd, f"/bin/bash -c 'ls -a {self.__path}'")
        return json.dumps({ "commands": output.decode("utf-8").split() })

async def handle_command(message, container):
    response = ""
    if message["type"] == "command":
        if message["content"]:
            response = await container.run_command_in_container(message["content"])
        else:
            response = json.dumps({"status": "no command"})
    elif message["type"] == "file":
        response = await container.put_file_in_container(message["name"], message["content"])
    elif message["type"] == "completion":
        parts = message["content"].split()
        if len(parts) == 1 and message["content"][-1] != " ":
            response = await container.get_commands()
        else:
            response = await container.get_files()
    elif message["type"] == "reconnection":
        for command in message["commands"]:
            await handle_command(command, container)
        response = json.dumps({"status": "ok"})
    else:
        response = json.dumps({"status": "error", "message": "An unexpected error happened"})

    return response

async def command(websocket, path):
    (host, port) = (websocket.remote_address[0], websocket.remote_address[1])
    containerkey = f"{host}:{port}"
    corecontainer = CoreContainer(config["docker-image"], config["docker-hostname"], config["homedir"], config["user"], config["homedir"])
    try:
        await websocket.send(json.dumps({"text": text}))
        while True:
            message = json.loads(await websocket.recv())
            response = await handle_command(message, corecontainer)
            await websocket.send(response)
    except websockets.ConnectionClosed:
        await corecontainer.kill_and_remove()
        print(f"Connection closed - time to clean up - {websocket.remote_address}")

start_server = websockets.serve(command, config["websocket-host"], 1337, max_size=2**25)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()