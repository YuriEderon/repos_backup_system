import os
import sys
import json
import zipfile
import shutil
import stat
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse

# Configurações de diretórios
SOURCE_DIR = r"C:\Users\edero\AppData\LocalLow\semiwork\Repo\saves"
BACKUP_DIR = r"C:\Users\edero\OneDrive\Saved Games\Repo"
PORT = 8080
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    global SOURCE_DIR, BACKUP_DIR
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        if isinstance(config.get("sourceDir"), str) and config["sourceDir"].strip():
            SOURCE_DIR = config["sourceDir"].strip()
        if isinstance(config.get("backupDir"), str) and config["backupDir"].strip():
            BACKUP_DIR = config["backupDir"].strip()
    except (OSError, ValueError):
        pass

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"sourceDir": SOURCE_DIR, "backupDir": BACKUP_DIR}, f, indent=2)
        return True, None
    except OSError as e:
        return False, str(e)

def get_dir_size(path):
    total_size = 0
    if not os.path.exists(path):
        return 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # Ignora links simbólicos corrompidos
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def get_file_count(path):
    if not os.path.exists(path):
        return 0
    count = 0
    for _, _, filenames in os.walk(path):
        count += len(filenames)
    return count

def format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB")
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {size_name[i]}"

def clear_directory(path):
    if not os.path.exists(path):
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                os.chmod(file_path, stat.S_IWRITE)
                os.remove(file_path)
            except Exception:
                pass
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                os.chmod(dir_path, stat.S_IWRITE)
                os.rmdir(dir_path)
            except Exception:
                pass

class BackupSystemHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Sobrescreve para não poluir o console com logs padrão de requisições,
        # a menos que queiramos debugar.
        sys.stdout.write("%s - - [%s] %s\n" %
                         (self.client_address[0],
                          self.log_date_time_string(),
                          format%args))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        # Habilita CORS
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/":
            self.serve_file("index.html", "text/html")
        elif path == "/index.css":
            self.serve_file("index.css", "text/css")
        elif path == "/index.js":
            self.serve_file("index.js", "application/javascript")
        elif path == "/logo.png":
            self.serve_file("logo.png", "image/png")
        elif path == "/api/status":
            self.handle_api_status()
        elif path == "/api/backups":
            self.handle_api_list_backups()
        else:
            self.send_error(404, "Recurso não encontrado")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # Lê os dados da requisição
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        req_payload = {}
        if post_data:
            try:
                req_payload = json.loads(post_data.decode('utf-8'))
            except Exception:
                pass

        if path == "/api/backup":
            self.handle_api_backup()
        elif path == "/api/restore":
            self.handle_api_restore(req_payload)
        elif path == "/api/delete":
            self.handle_api_delete(req_payload)
        elif path == "/api/open-folder":
            self.handle_api_open_folder(req_payload)
        elif path == "/api/settings":
            self.handle_api_settings(req_payload)
        else:
            self.send_error(404, "Endpoint não encontrado")

    def serve_file(self, filename, content_type):
        try:
            # Assume que os arquivos estáticos estão na mesma pasta que o script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, filename)
            
            with open(file_path, 'rb') as f:
                content = f.read()
                
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Erro interno do servidor: {str(e)}".encode('utf-8'))

    def send_json(self, data, status_code=200):
        response_bytes = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response_bytes))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response_bytes)

    def handle_api_status(self):
        saves_exists = os.path.exists(SOURCE_DIR)
        backup_exists = os.path.exists(BACKUP_DIR)
        
        # Cria a pasta de backup caso não exista
        if not backup_exists:
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                backup_exists = True
            except Exception:
                pass

        status_data = {
            "saves": {
                "exists": saves_exists,
                "path": SOURCE_DIR,
                "fileCount": get_file_count(SOURCE_DIR) if saves_exists else 0,
                "totalSize": format_size(get_dir_size(SOURCE_DIR)) if saves_exists else "0 B",
                "rawSize": get_dir_size(SOURCE_DIR) if saves_exists else 0
            },
            "backups": {
                "exists": backup_exists,
                "path": BACKUP_DIR,
                "count": len([f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')]) if backup_exists else 0,
                "totalSize": format_size(get_dir_size(BACKUP_DIR)) if backup_exists else "0 B"
            }
        }
        self.send_json(status_data)

    def handle_api_list_backups(self):
        if not os.path.exists(BACKUP_DIR):
            self.send_json([])
            return

        backups = []
        try:
            for filename in os.listdir(BACKUP_DIR):
                if filename.endswith('.zip'):
                    filepath = os.path.join(BACKUP_DIR, filename)
                    stat_info = os.stat(filepath)
                    mtime = stat_info.st_mtime
                    dt_object = datetime.fromtimestamp(mtime)
                    
                    backups.append({
                        "filename": filename,
                        "size": format_size(stat_info.st_size),
                        "rawSize": stat_info.st_size,
                        "date": dt_object.strftime("%Y-%m-%d %H:%M:%S"),
                        "rawTime": mtime
                    })
            
            # Ordena do mais novo para o mais antigo
            backups.sort(key=lambda x: x["rawTime"], reverse=True)
        except Exception as e:
            self.send_json({"error": f"Falha ao listar backups: {str(e)}"}, 500)
            return

        self.send_json(backups)

    def handle_api_backup(self):
        if not os.path.exists(SOURCE_DIR):
            self.send_json({
                "success": False,
                "message": "A pasta de saves de origem não foi encontrada! O jogo já foi instalado/executado?"
            }, 400)
            return

        # Garante que a pasta de destino exista
        if not os.path.exists(BACKUP_DIR):
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
            except Exception as e:
                self.send_json({
                    "success": False,
                    "message": f"Não foi possível criar a pasta de destino dos backups: {str(e)}"
                }, 500)
                return

        # Gera o nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_filename = f"REPO_Backup_{timestamp}.zip"
        zip_filepath = os.path.join(BACKUP_DIR, zip_filename)

        try:
            # Cria o zip file
            skipped_files = []
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(SOURCE_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, SOURCE_DIR)
                        try:
                            zipf.write(file_path, arcname)
                        except (PermissionError, OSError) as fe:
                            skipped_files.append(arcname)

            if skipped_files:
                msg = (f"Backup '{zip_filename}' criado com avisos: "
                       f"{len(skipped_files)} arquivo(s) ignorados por permissão/travamento: "
                       f"{', '.join(skipped_files[:5])}")
            else:
                msg = f"Backup '{zip_filename}' criado com sucesso!"

            self.send_json({
                "success": True,
                "message": msg,
                "filename": zip_filename,
                "size": format_size(os.path.getsize(zip_filepath)),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "skipped": skipped_files
            })
        except Exception as e:
            # Em caso de erro, limpa o arquivo corrompido que possa ter sido criado
            if os.path.exists(zip_filepath):
                try:
                    os.remove(zip_filepath)
                except Exception:
                    pass
            self.send_json({
                "success": False,
                "message": f"Falha ao criar backup comprimido: {str(e)}"
            }, 500)

    def handle_api_restore(self, req_payload):
        filename = req_payload.get("filename")
        if not filename:
            self.send_json({
                "success": False,
                "message": "Nenhum arquivo de backup especificado para restauração."
            }, 400)
            return

        # Previne ataques de travessia de diretório simples
        filename = os.path.basename(filename)
        zip_filepath = os.path.join(BACKUP_DIR, filename)

        if not os.path.exists(zip_filepath):
            self.send_json({
                "success": False,
                "message": f"O backup '{filename}' não foi encontrado na pasta de destino."
            }, 404)
            return

        try:
            # 1. Limpa a pasta de origem atual para evitar conflitos de arquivos órfãos
            if os.path.exists(SOURCE_DIR):
                clear_directory(SOURCE_DIR)
            else:
                os.makedirs(SOURCE_DIR, exist_ok=True)

            # 2. Descompacta o zip na pasta de origem
            with zipfile.ZipFile(zip_filepath, 'r') as zipf:
                zipf.extractall(SOURCE_DIR)

            self.send_json({
                "success": True,
                "message": f"Backup '{filename}' restaurado com sucesso no diretório de saves original!"
            })
        except Exception as e:
            self.send_json({
                "success": False,
                "message": f"Erro durante a restauração do save: {str(e)}"
            }, 500)

    def handle_api_delete(self, req_payload):
        filename = req_payload.get("filename")
        if not filename:
            self.send_json({
                "success": False,
                "message": "Nenhum arquivo de backup especificado para exclusão."
            }, 400)
            return

        # Previne ataques de travessia de diretório simples
        filename = os.path.basename(filename)
        zip_filepath = os.path.join(BACKUP_DIR, filename)

        if not os.path.exists(zip_filepath):
            self.send_json({
                "success": False,
                "message": f"O backup '{filename}' não foi encontrado na pasta de destino."
            }, 404)
            return

        try:
            os.remove(zip_filepath)
            self.send_json({
                "success": True,
                "message": f"Backup '{filename}' excluído com sucesso do seu OneDrive!"
            })
        except Exception as e:
            self.send_json({
                "success": False,
                "message": f"Erro ao excluir o backup: {str(e)}"
            }, 500)

    def handle_api_open_folder(self, req_payload):
        folder_type = req_payload.get("type")
        target_path = ""
        
        if folder_type == "saves":
            target_path = SOURCE_DIR
        elif folder_type == "backups":
            target_path = BACKUP_DIR
        else:
            self.send_json({
                "success": False,
                "message": "Tipo de pasta inválido especificado."
            }, 400)
            return

        if not os.path.exists(target_path):
            try:
                os.makedirs(target_path, exist_ok=True)
            except Exception as e:
                self.send_json({
                    "success": False,
                    "message": f"Não foi possível criar o diretório para abrir: {str(e)}"
                }, 500)
                return

        try:
            # Abre o Explorer no Windows
            os.startfile(target_path)
            self.send_json({
                "success": True,
                "message": f"Pasta aberta com sucesso no Explorador de Arquivos."
            })
        except Exception as e:
            self.send_json({
                "success": False,
                "message": f"Falha ao abrir a pasta no Explorer: {str(e)}"
            }, 500)

    def handle_api_settings(self, payload):
        global SOURCE_DIR, BACKUP_DIR

        source_dir = str(payload.get("sourceDir", "")).strip()
        backup_dir = str(payload.get("backupDir", "")).strip()

        if not source_dir or not backup_dir:
            self.send_json({
                "success": False,
                "message": "Os caminhos de saves e de backups não podem ficar vazios."
            }, 400)
            return

        old_source, old_backup = SOURCE_DIR, BACKUP_DIR
        SOURCE_DIR, BACKUP_DIR = source_dir, backup_dir

        # Garante que a pasta de destino dos backups exista
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
        except Exception:
            pass

        ok, err = save_config()
        if not ok:
            SOURCE_DIR, BACKUP_DIR = old_source, old_backup
            self.send_json({
                "success": False,
                "message": f"Não foi possível persistir a configuração: {err}"
            }, 500)
            return

        self.send_json({
            "success": True,
            "message": "Diretórios atualizados com sucesso!"
        })

def run():
    load_config()
    print("=" * 60)
    print("  R.E.P.O's Bestos Backup Stardalhaços Blaster Ultimate")
    print("  Iniciando servidor local...")
    print("=" * 60)
    print(f"  Diretório de Saves: {SOURCE_DIR}")
    print(f"  Diretório de Backups: {BACKUP_DIR}")
    
    port = PORT
    httpd = None
    for p in range(PORT, PORT + 100):
        try:
            server_address = ('127.0.0.1', p)
            httpd = HTTPServer(server_address, BackupSystemHandler)
            port = p
            break
        except Exception:
            continue
            
    if not httpd:
        print("  Erro: Não foi possível ligar o servidor a nenhuma porta de 8080 a 8180.")
        return

    print(f"\n  Sistema de backup rodando em: http://127.0.0.1:{port}")
    print("  Pressione Ctrl+C para encerrar o servidor.")
    print("=" * 60)
    
    webbrowser.open(f"http://127.0.0.1:{port}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Encerrando servidor...")
        httpd.server_close()
        print("  Servidor finalizado com sucesso.")

if __name__ == "__main__":
    run()
