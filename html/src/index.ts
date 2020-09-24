import './style.css'
import * as $ from 'jquery';
import 'jquery.terminal';
declare var process : {
    env: {
      WEBSOCKETURL: string,
      MOTD: string,
    }
  };

  console.log(process.env);

$(function() {
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
    let term = $("#main").terminal(function(command: any) {
        let message = {
            "type": "command",
            "content": command
        }
        connection.socket.send(JSON.stringify(message));
        saveCommand(message);
        this.pause();
    },
    {
        greetings: process.env.MOTD ? process.env.MOTD : "",
        prompt: function(callback) {
            callback("user@slurm-tutorial:" + path + "$ ");
        }
    });

    let maxpages = 1;

    function updatePagecount() {
        document.getElementById("indicator").innerText = curpage + "/" + maxpages;
    }

    function updateMaxPages(num) {
        maxpages = num; //document.querySelectorAll("[data-page-index]").length;
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
        changePage(ev, (value: number) => value-1, (value: number) => value > 1);
    });
    document.getElementById("next").addEventListener("click", function (ev: MouseEvent) {
        changePage(ev, (value: number) => value+1, (value: number) => value < maxpages);
    });

    function setupSocket(socket: WebSocket) {
        socket.onmessage = function(ev: MessageEvent) {
            let data = JSON.parse(ev.data);
            if (data.status) {
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
                    element.dataset.pageIndex = index+1;
                    learn.appendChild(element);
                });
                updateMaxPages(data.text.length);
                updatePagecount();
            } else {
                path = data.path;
                term.echo(data.output);
                term.resume();
            }
        }
        socket.onerror = function(ev: Event) {
            console.log(ev);
        }
        socket.onclose = function(ev: CloseEvent) {
            // code 1006 is abnormal shutdown, if that happens we want to reconnect the user in the same state
            if (ev.code == 1006) {
                term.pause();
                addBlur();
                document.getElementById("connection-problems").classList.remove("hidden");
                connection.socket = new WebSocket(connectionAddr);
                setupSocket(connection.socket);
            }
        }
        socket.onopen = function(ev: Event) {
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
    }

    function removeBlur() {
        document.getElementById("main").classList.remove("blur");
        document.getElementById("learn").classList.remove("blur");
    }

    function dragstart(this: HTMLElement, ev: DragEvent)  {
        ev.preventDefault();
        ev.stopPropagation();
        addBlur();

        let dropbox = document.getElementById("dropbox");
        dropbox.classList.remove("hidden");
    }

    function stop(ev: DragEvent) {
        ev.preventDefault();
        ev.stopPropagation();
        removeBlur();

        let dropbox = document.getElementById("dropbox");
        dropbox.classList.add("hidden");
    }

    function dragstop(this: HTMLElement, ev: DragEvent) {
        stop(ev);
    }
    function dragstopanddrop(this: HTMLElement, ev: DragEvent) {
        stop(ev);
        for (let i = 0; i < ev.dataTransfer.files.length; i++) {
            let file = ev.dataTransfer.files[i];
            let reader = new FileReader()
            if (file.size < 1024*1024) {
                reader.readAsBinaryString(file);
                reader.onloadend = function(ev: ProgressEvent<FileReader>) {
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
    body.addEventListener("dragenter", dragstart);
    body.addEventListener("dragover", dragstart);
    body.addEventListener("dragleave", dragstop);
    body.addEventListener("drop", dragstopanddrop);

    let storedCommands = window.localStorage.getItem("commands");
    if (storedCommands != null) {
        document.getElementById("welcome-back").classList.remove("hidden");
    }
    
    document.getElementById("yes").addEventListener("click", function(ev: MouseEvent) {
        commands = JSON.parse(storedCommands);
        connection.socket.send(
            JSON.stringify(
                {
                    "type": "reconnection",
                    "commands": commands
                }
            )
        );
        document.getElementById("welcome-back").classList.add("hidden");
    });
    document.getElementById("no").addEventListener("click", function(ev: MouseEvent) {
        window.localStorage.removeItem("commands");
        document.getElementById("welcome-back").classList.add("hidden");
    });
});