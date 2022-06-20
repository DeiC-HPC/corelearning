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
import requests

logger = logging.getLogger("corelearning")
handler = logging.FileHandler("corelearning.log")
formatter = logging.Formatter("[%(asctime)s %(levelname)s] %(message)s")
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

config = dict()
with open("config.yaml") as f:
    config = yaml.load(f, Loader=yaml.Loader)
url = config["docker-url"]
client = docker.DockerClient(base_url=url)
cpu_quota = int(config["cpu-quota"]*100000)
homedirlen = len(config["homedir"])
textdir = os.listdir("text")
textdir.sort()
text = []
for file in textdir:
    filename = f"text/{file}"
    if os.path.isfile(filename):
        with open(filename) as f:
            text.append(misaka.html(f.read(), extensions=("fenced-code", "tables")))

class CoreContainer:
    def __init__(self, dockerimage: str, hostname: str, path, user, homedir):
        self.__container = client.containers.run(dockerimage, command="/bin/bash", hostname=hostname, tty=True, stdin_open=True, detach=True, cpu_period=100000, cpu_quota=cpu_quota, environment=["TERM=xterm-256color"])
        self.__path = path
        self.__homedir = homedir
        self.__exec_cmd_root = functools.partial(self.__container.exec_run, user="root")

    async def run_term(self, webclient) -> None:
        loop = asyncio.get_running_loop()
        if config["docker-startup-root-cmds"] and len(config["docker-startup-root-cmds"]) > 0:
            for cmd in config["docker-startup-root-cmds"]:
                await loop.run_in_executor(None, self.__exec_cmd_root, cmd)

        # detachKeys needs to be set to something the user will most likely not type in sequence
        # Dockers default is ctrl-p,q, which then blocks ctrl-p functionality in the browser
        async with websockets.connect(f"ws://{url}/containers/{self.__container.id}/attach/ws?detachKeys=ctrl-@,[&stream=true&stdin=true&stdout=true&stderr=true") as server:
            await server.send(b'\x0c')
            while True:
                try:
                    message = await asyncio.wait_for(webclient.recv(), 0.01)
                    command = await self.__get_json(message)
                    if (message.startswith("{'") or message.startswith('{"')) and command != None:
                        print(command)
                        if command["type"] == "resize":
                            await self.__resize_term(command["cols"], command["rows"])
                        elif command["type"] == "file":
                            await self.__put_file_in_container(command["name"], command["content"])
                    else:
                        await server.send(message)
                except asyncio.TimeoutError:
                    pass
                try:
                    message = await asyncio.wait_for(server.recv(), 0.01)
                    await webclient.send(message)
                except asyncio.TimeoutError:
                    pass

    async def __resize_term(self, width: int, height: int) -> None:
        requests.post(f"http://{url}/containers/{self.__container.id}/resize", params={"w": width, "h": height})

    async def __put_file_in_container(self, name: str, content):
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

    async def __get_json(self, text):
        try:
            return json.loads(text)
        except:
            return None

#async def handle_command(message, container):
#    response = ""
#    if message["type"] == "command":
#        if message["content"]:
#            response = await container.run_command_in_container(message["content"])
#        else:
#            response = json.dumps({"status": "no command"})
#    elif message["type"] == "file":
#        response = await container.put_file_in_container(message["name"], message["content"])
#    elif message["type"] == "completion":
#        parts = message["content"].split()
#        if len(parts) == 1 and message["content"][-1] != " ":
#            response = await container.get_commands()
#        else:
#            response = await container.get_files()
#    elif message["type"] == "reconnection":
#        for command in message["commands"]:
#            await handle_command(command, container)
#        response = json.dumps({"status": "ok"})
#    else:
#        response = json.dumps({"status": "error", "message": "An unexpected error happened"})
#
#    return response

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
        logger.info(f"User {containerkey} connected")
        await corecontainer.run_term(websocket)
    except websockets.ConnectionClosed:
        await corecontainer.kill_and_remove()
        logger.info(f"User {containerkey} disconnected")


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