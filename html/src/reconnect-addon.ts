import { Terminal, IDisposable } from 'xterm';

export class ReconnectAddon {
  private _disposables: IDisposable[] = [];
  private _commands: string[];
  private _storageKey: string;

  constructor(storageKey: string, commands: string[]) {
    this._commands = commands;
    this._storageKey = storageKey;
  }

  activate(terminal: Terminal): void {
    console.log("test");
    this._disposables.push(terminal.onData(d => {
      window.localStorage.setItem(this._storageKey, JSON.stringify(this._commands));
    }));
  }

  dispose(): void {
    this._disposables.forEach(d => d.dispose());
    this._disposables.length = 0;
  }
}