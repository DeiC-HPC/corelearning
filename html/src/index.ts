import './style.css';
import { Terminal } from 'xterm';
import { AttachAddon } from 'xterm-addon-attach';
import { FitAddon } from 'xterm-addon-fit';
import { ReconnectAddon } from './reconnect-addon';
declare var process: {
    env: {
        WEBSOCKETURL: string,
        MOTD: string,
    }
};

console.log(process.env);

const connectionAddr = "ws://" + process.env.WEBSOCKETURL + ":1337";
const proxyAddr = connectionAddr + "/proxy";
const textAddr = connectionAddr + "/text";
const storageKey = "commands";
let storedCommands = window.localStorage.getItem(storageKey);
let commands: string[] = [];
// TODO: Fix stored commands so they are sent to the server in case the user wants the same session again
// This works in cooporation with the reconnect addon
if (storedCommands != null) {
    // document.getElementById("welcome-back").classList.remove("hidden");
} else {
    commands = JSON.parse(storedCommands);
}

let socket = new WebSocket(proxyAddr);
let term = new Terminal();
let attachAddon = new AttachAddon(socket);
let fitAddon = new FitAddon();
let reconnectAddon = new ReconnectAddon(storageKey, commands);
term.loadAddon(reconnectAddon);
term.loadAddon(fitAddon);
term.open(document.getElementById("main"));
fitAddon.fit();
term.loadAddon(attachAddon);

window.onresize = function () {
    fitAddon.fit();
};

let maxpages = 1;

function updatePagecount() {
    document.getElementById("indicator").innerText = curpage + "/" + maxpages;
}

function updateMaxPages(num) {
    maxpages = num;
}

let curpage = 1;
function changePage(ev: MouseEvent, updateCounter: (value: number) => number, compare: (value: number) => boolean) {
    ev.preventDefault();
    ev.stopPropagation();
    if (compare(curpage)) {
        let elm = document.querySelector("[data-page-index='" + curpage + "']");
        if (elm) {
            elm.classList.add("hidden");
        }
        curpage = updateCounter(curpage);
        let newelm = document.querySelector("[data-page-index='" + curpage + "']");
        if (newelm) {
            newelm.classList.remove("hidden");
        }
    }
    updatePagecount();
}
document.getElementById("prev").addEventListener("click", function (ev: MouseEvent) {
    changePage(ev, (value: number) => value - 1, (value: number) => value > 1);
});
document.getElementById("next").addEventListener("click", function (ev: MouseEvent) {
    changePage(ev, (value: number) => value + 1, (value: number) => value < maxpages);
});

document.getElementById("yes").addEventListener("click", function (ev: MouseEvent) {
    commands = JSON.parse(storedCommands);
    commands.forEach(c => socket.send(c));
    document.getElementById("welcome-back").classList.add("hidden");
});
document.getElementById("no").addEventListener("click", function (ev: MouseEvent) {
    window.localStorage.removeItem("commands");
    document.getElementById("welcome-back").classList.add("hidden");
});

let textsocket = new WebSocket(textAddr);
textsocket.onmessage = function (ev: MessageEvent) {
    let data = JSON.parse(ev.data);
    if (data.text) {
        let learn = document.getElementById("learn");
        data.text.forEach((text, index) => {
            let element = document.createElement("div");
            element.innerHTML = text;
            element.classList.add("bottom-fix");
            if (index != 0) {
                element.classList.add("hidden")
            }
            element.dataset.pageIndex = index + 1;
            learn.appendChild(element);
        });
        updateMaxPages(data.text.length);
        updatePagecount();
    }
}

// Most of the old code
// TODO: contains code for uploading files to the server via drag and drop, we need that feature again
/*$(function () {
    let commands = [];
    function saveCommand(command: any) {
        commands.push(command);
        window.localStorage.setItem("commands", JSON.stringify(commands));
    }

    const connectionAddr = "ws://" + process.env.WEBSOCKETURL + ":1337";

    let path = "/home/user";
    let connection = {
        "socket": new WebSocket(connectionAddr)
    }
    let term = $("#main").terminal(
        function (command: any) {
            let message = {
                "type": "command",
                "content": command
            };
            connection.socket.send(JSON.stringify(message));
            saveCommand(message);
            this.pause();
        },
        {
            autocompleteMenu: true,
            greetings: process.env.MOTD ? process.env.MOTD : "",
            prompt: function (callback) {
                callback("user@slurm-tutorial:" + path + "$ ");
            },
            completion: function (string, callback) {
                let message = {
                    "type": "completion",
                    "content": term.get_command()
                }
                connection.socket.send(JSON.stringify(message));
            }
        });


    function setupSocket(socket: WebSocket) {
        socket.onmessage = function (ev: MessageEvent) {
            let data = JSON.parse(ev.data);
            if (data.status) {
                console.log(data)
                if (data.status == "error") {
                    alert(data.message);
                }
            } else if (data.text) {
                let learn = document.getElementById("learn");
                data.text.forEach((text, index) => {
                    let element = document.createElement("div");
                    element.innerHTML = text;
                    element.classList.add("bottom-fix");
                    if (index != 0) {
                        element.classList.add("hidden")
                    }
                    element.dataset.pageIndex = index + 1;
                    learn.appendChild(element);
                });
                updateMaxPages(data.text.length);
                updatePagecount();
            } else if (data.commands) {
                console.log(data.commands);
                term.complete(
                    data.commands,
                    {
                        echo: true,
                        echoCommand: true,

                    }
                );
            } else {
                path = data.path;
                term.echo(data.output);
                term.resume();
            }
        }
        socket.onerror = function (ev: Event) {
            console.log(ev);
        }
        socket.onclose = function (ev: CloseEvent) {
            // code 1006 is abnormal shutdown, if that happens we want to reconnect the user in the same state
            if (ev.code == 1006) {
                term.pause();
                addBlur();
                document.getElementById("connection-problems").classList.remove("hidden");
                connection.socket = new WebSocket(connectionAddr);
                setupSocket(connection.socket);
            }
        }
        socket.onopen = function (ev: Event) {
            if (commands.length > 0) {
                connection.socket.send(
                    JSON.stringify(
                        {
                            "type": "reconnection",
                            "commands": commands
                        }
                    )
                );
            }
            document.getElementById("connection-problems").classList.add("hidden");
            removeBlur();
            term.resume();
        }
    }
    setupSocket(connection.socket);

    function addBlur() {
        document.getElementById("main").classList.add("blur");
        document.getElementById("learn").classList.add("blur");
        document.getElementById("hover").classList.remove("hidden");
        document.getElementById("dropbox").classList.remove("hidden");
    }

    function removeBlur() {
        document.getElementById("main").classList.remove("blur");
        document.getElementById("learn").classList.remove("blur");
        document.getElementById("hover").classList.add("hidden");
        document.getElementById("dropbox").classList.add("hidden");
    }

    function dragstart(this: HTMLElement, ev: DragEvent) {
        if (ev.dataTransfer.types.includes("Files")) {
            ev.preventDefault();
            ev.stopPropagation();
            addBlur();
        }
    }

    function dragstop(this: HTMLElement, ev: DragEvent) {
        ev.preventDefault();
        ev.stopPropagation();
        removeBlur();
    }

    function dragstopanddrop(this: HTMLElement, ev: DragEvent) {
        ev.preventDefault();
        ev.stopPropagation();
        removeBlur();
        for (let i = 0; i < ev.dataTransfer.files.length; i++) {
            let file = ev.dataTransfer.files[i];
            let reader = new FileReader()
            if (file.size < 1024 * 1024) {
                reader.readAsBinaryString(file);
                reader.onloadend = function (ev: ProgressEvent<FileReader>) {
                    let bin = reader.result;
                    let message = {
                        "type": "file",
                        "name": file.name,
                        "content": bin
                    }
                    connection.socket.send(JSON.stringify(message));
                    saveCommand(message);
                }
            } else {
                alert("Max. allowed file size 1MB")
            }
        }
    }

    let body = document.body;
    let hover = document.getElementById("hover");
    body.addEventListener("dragenter", dragstart);
    hover.addEventListener("drop", dragstopanddrop);
    hover.addEventListener("dragover", function (ev: DragEvent) { ev.preventDefault(); });
    hover.addEventListener("dragleave", dragstop);

    let storedCommands = window.localStorage.getItem("commands");
    if (storedCommands != null) {
        document.getElementById("welcome-back").classList.remove("hidden");
    }

});*/