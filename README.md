# Corelearning

Corelearning is framework to ease the learning of cli tools. It uses docker
containers, which are purged when the user disconnects, to make sure that
nothing from the user is saved on exit and information is only stored
client-side.

## Getting started

To use Corelearning, you simply add it to your project as a git submodule.

### Prerequisites

Before we get started you should have the following programs installed:

- Python3 (>=3.7 with pip and cffi)
- Nodejs
- docker

### Installing

To install the needed libraries for the project you will have to run a few
commands. Inside the html folder you run the command `npm install` and inside
the server folder you run `pip3 install -r requirements.txt`.

To compile the javascript for the webserver you will have to run `npm run build`
inside the html folder.

### Files and folders

In your root project you will have to create a folder call `text`. Inside this
folder you can create files for the learning text that will be shown in the
sidebar. The order of the files will be determined by filename.

Then you also need to create a config file called `config.yaml`, which could
look like this.

```yaml
docker-image: name-of-docker-image
docker-hostname: "the-hostname-you-want-the-container-to-have"
user: docker-container-user
homedir: /home/directory/of/the/docker/user
websocket-host: "websocket.host"
cpu-quota: 0.25
```

All fields are required. `docker-image` is the image name for the docker image
that you want to run. `docker-hostname` is the hostname you want the docker
container to have. `user` is the username of the user in the docker container.
`homedir` is the home directory of the user in the docker container.
`websocket-host` is the hostname you want the websocket to respondto. `motd` is
the message that will be shown in top of the terminal. `cpu-quota` is the
allocated cpu ressources for a container. Here 0.25 means 25% of a core.

### Docker image

When creating a dockerfile for Corelearning, it should copy `server/term` into
the container and make it executable. It should of course be placed somewhere in
in the path of the user, for example `/usr/bin`.

### Hosting the web

You will also need to host what is in the `html` folder. This can be done with
any webserver and does not require anything.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on the process for
submitting pull requests, bugs, and feature requests to us.

## License

This project is licensed under the EUPL License - see the [LICENSE](LICENSE)
file for details.
