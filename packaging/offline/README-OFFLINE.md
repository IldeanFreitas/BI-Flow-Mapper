# BI Flow Mapper — pacote offline para VS Code

Este pacote permite preparar e executar o projeto **sem acesso a internet**.
Ele inclui todas as dependencias Python em `wheels/` e nao instala nada fora da
pasta extraida.

## Requisito

- Windows x64 com **CPython 3.12** ja instalado. Nao use Python 3.14.
- Para a janela desktop nativa, Microsoft Edge WebView2 habilitado. O modo de
  navegador funciona sem ele.

## Primeiro uso

Abra o PowerShell na pasta extraida e execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Setup-Offline.ps1
```

O comando cria `.venv` e instala somente a partir de `wheels/`; nenhuma
conexao de rede e feita. Se o Python nao estiver no `PATH`, informe o caminho:

```powershell
.\Setup-Offline.ps1 -PythonExe 'C:\Python312\python.exe'
```

## Executar no VS Code

Abra a pasta no VS Code, selecione o interpretador `.venv\Scripts\python.exe`
e execute `backend.py`; ou rode:

```powershell
.\Executar.ps1
```

O navegador abre em um endereco local (`127.0.0.1`). Dados e arquivos PBIX nao
sao enviados pela aplicacao.

## Integridade

Compare o SHA-256 do arquivo ZIP recebido com o arquivo `.sha256` fornecido.
Se a politica corporativa bloquear scripts ou executaveis, solicite a liberacao
para a pasta do pacote; esta distribuicao nao tenta contornar controles da TI.
