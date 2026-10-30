# R.E.P.O's Bestos Backup Stardalhaços Blaster Ultimate

Sistema de backup e restauração dos saves do jogo **[R.E.P.O.](https://store.steampowered.com/app/2949840/REPO/)** (Semiwork). É um servidor web local que compacta a pasta de saves em `.zip` com timestamp, envia para uma pasta sincronizada com o **OneDrive** e permite restaurar/excluir backups direto pela interface.

## Funcionalidades

- **Criar backup** — compacta a pasta de saves em `REPO_Backup_AAAA-MM-DD_HH-MM-SS.zip` e salva no OneDrive.
- **Listar backups** — exibe os zips existentes, do mais recente para o mais antigo, com tamanho e data.
- **Restaurar backup** — limpa a pasta de saves atual e extrai o zip escolhido (com modal de confirmação e contagem regressiva de 5s).
- **Excluir backup** — remove o zip do OneDrive (com confirmação de 3s).
- **Abrir pastas** — abre a pasta de saves ou a pasta de backups no Explorador do Windows.
- **Editar caminhos** — altera os diretórios de origem e destino pela própria UI; as configurações ficam salvas em `config.json`.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | **Python 3** (apenas biblioteca padrão — `http.server`, `zipfile`, `shutil`, etc.) — sem dependências externas |
| Frontend | **HTML + CSS + JavaScript** vanilla (sem build, sem framework) |
| Testes | `unittest` (biblioteca padrão do Python) |
| Persistência | Sistem de arquivos (`.zip` + `config.json`) — sem banco de dados |
| Armazenamento | Pasta local sincronizada com **OneDrive** |

> **Sem dependências para instalar.** O projeto roda apenas com a biblioteca padrão do Python.

## Requisitos

- **Windows** (usa `os.startfile` e caminhos `C:\...`)
- **Python 3.10+** (desenvolvido e testado no Python 3.13)
- Cliente do **OneDrive** instalado e a pasta de destino configurada (opcional, mas recomendado para backup em nuvem)

## Como rodar

### Opção 1 — Duplo clique (Windows)

1. Dê **duplo clique** em `iniciar.bat`.
2. O servidor sobe e o navegador abre automaticamente em `http://127.0.0.1:8080`.

### Opção 2 — Terminal

```bash
python server.py
```

O servidor inicia em `http://127.0.0.1:8080` e abre o navegador automaticamente.

> Se a porta 8080 estiver ocupada, o servidor tenta automaticamente as portas seguintes (até 8179).

### Configuração inicial

Por padrão, o sistema usa:

| Configuração | Valor padrão |
|---|---|
| Pasta de saves (origem) | `C:\Users\edero\AppData\LocalLow\semiwork\Repo\saves` |
| Pasta de backup (destino) | `C:\Users\edero\OneDrive\Saved Games\Repo` |
| Porta | `8080` (com fallback automático) |

Para alterar os caminhos, use a interface (botão de configurações) — as alterações são salvas no arquivo `config.json` criado ao lado do `server.py`.

> **Importante:** feche o jogo antes de restaurar um backup. A restauração apaga todos os arquivos da pasta de saves antes de extrair o zip.

## Testes

```bash
python -m unittest test_server
```

Ou:

```bash
python test_server.py
```

## Estrutura do projeto

```
repos_backup_system/
├── server.py        # Backend Python (servidor HTTP + API REST)
├── index.html       # Página única (SPA)
├── index.js         # Lógica do frontend (vanilla JS)
├── index.css        # Estilos (tema neon/CRT)
├── test_server.py   # Suite de testes (unittest)
├── iniciar.bat      # Atalho de inicialização (Windows)
├── logo.png         # Logo do jogo
└── config.json      # Criado em runtime ao salvar as configurações
```

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/status` | Status dos diretórios (existe, nº de arquivos, tamanho) |
| GET | `/api/backups` | Lista os backups existentes |
| POST | `/api/backup` | Cria um novo backup |
| POST | `/api/restore` | Restaura um backup (limpa a pasta de saves e extrai o zip) |
| POST | `/api/delete` | Exclui um backup |
| POST | `/api/open-folder` | Abre uma pasta no Explorador |
| POST | `/api/settings` | Salva os caminhos em `config.json` |

## Notas

- O servidor roda apenas em **localhost** (`127.0.0.1`) — não é exposto na rede.
- O backup é tolerante a erros: arquivos travados pelo jogo são pulados e reportados.
- O tema da UI é uma referência ao próprio jogo (estilo terminal CRT neon).

---

*V1.0.0 ULTIMATE — LICENÇA OPERACIONAL: REPO-BESTOS-998A*
