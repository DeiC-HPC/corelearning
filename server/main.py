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


config = dict()
with open("config.yaml") as f:
    config = yaml.load(f, Loader=yaml.Loader)
url = config["docker-url"]
client = docker.DockerClient(base_url=url)
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
        self.__container = client.containers.run(dockerimage, command="/bin/bash", hostname=hostname, tty=True, stdin_open=True, detach=True, cpu_period=100000, cpu_quota=25000)
        self.__path = path
        self.__user = user
        self.__homedir = homedir
        self.__exec_cmd = functools.partial(self.__container.exec_run, user=self.__user)
        self.__exec_cmd_root = functools.partial(self.__container.exec_run, user="root")

    async def run_command_in_container(self, cmd):
        loop = asyncio.get_running_loop()
        (_, output) = await loop.run_in_executor(None, self.__exec_cmd, f"term {self.__path} {cmd}")

        response = output.decode("utf-8")
        self.__path = json.loads(response)["path"]

        return response

    async def run_term(self, webclient):
        loop = asyncio.get_running_loop()
        if config["docker-startup-root-cmds"] and len(config["docker-startup-root-cmds"]) > 0:
            for cmd in config["docker-startup-root-cmds"]:
                await loop.run_in_executor(None, self.__exec_cmd_root, cmd)

        async with websockets.connect(f"ws://{url}/containers/{self.__container.id}/attach/ws?stream=true&stdin=true&stdout=true&stderr=true") as server:
            await server.send("clear\r")
            while True:
                try:
                    message = await asyncio.wait_for(webclient.recv(), 0.01)
                    await server.send(message)
                except asyncio.TimeoutError:
                    pass
                try:
                    message = await asyncio.wait_for(server.recv(), 0.01)
                    await webclient.send(message)
                except asyncio.TimeoutError:
                    pass

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

async def gettext(websocket):
    try:
        await websocket.send(json.dumps({"text": text}))
    except websockets.ConnectionClosed:
        pass

async def proxy(websocket):
    (host, port) = (websocket.remote_address[0], websocket.remote_address[1])
    containerkey = f"{host}:{port}"
    corecontainer = CoreContainer(config["docker-image"], config["docker-hostname"], config["homedir"], config["user"], config["homedir"])
    try:
        await corecontainer.run_term(websocket)
    except websockets.ConnectionClosed:
        await corecontainer.kill_and_remove()
        print(f"Connection closed - time to clean up - {websocket.remote_address}")

# TODO: after changing to the new terminal, it is no longer possible to upload files to the container
# The code is still there, but is not active
# TODO: it is also no longer possible to get your session back after reconnecting
async def router(websocket, path):
    if path == "/proxy":
        await proxy(websocket)
    elif path == "/text":
        await gettext(websocket)

async def main():
    async with websockets.serve(router, config["websocket-host"], 1337, max_size=2**25):
        await asyncio.Future()

asyncio.run(main())
# asyncio.get_event_loop().run_until_complete(start_server)
# asyncio.get_event_loop().run_forever()
