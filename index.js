const API_BASE = "/api";

// Estado global do modal de restauração
let selectedBackupFilename = null;
let restoreCountdownInterval = null;

// Estado global do modal de exclusão
let selectedDeleteFilename = null;
let deleteCountdownInterval = null;

// Inicializa a aplicação
document.addEventListener("DOMContentLoaded", () => {
    addLog("Verificando conexão com o servidor local...", "system");
    refreshAll();
    
    // Configura o evento do botão de confirmação da restauração
    const btnConfirmRestore = document.getElementById("btn-confirm-restore");
    if (btnConfirmRestore) {
        btnConfirmRestore.addEventListener("click", executeRestore);
    }

    // Configura o evento do botão de confirmação da exclusão
    const btnConfirmDelete = document.getElementById("btn-confirm-delete");
    if (btnConfirmDelete) {
        btnConfirmDelete.addEventListener("click", executeDelete);
    }
});

// Adiciona uma mensagem ao terminal de logs no frontend
function addLog(text, type = "info") {
    const terminal = document.getElementById("terminal-output");
    if (!terminal) return;

    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    
    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];
    
    line.textContent = `[${timeStr}] ${text}`;
    terminal.appendChild(line);
    
    // Auto-scroll para o final do terminal
    terminal.scrollTop = terminal.scrollHeight;
}

// Atualiza todas as informações (status das pastas e lista de backups)
async function refreshAll() {
    await updateStatus();
    await loadBackupsList();
}

// Busca o status das pastas no backend
async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        if (!response.ok) throw new Error("Erro de status do servidor");
        
        const data = await response.json();
        
        // Atualiza a seção de Saves Locais
        const saves = data.saves;
        const saveDirInput = document.getElementById("save-dir-input");
        if (saveDirInput && document.activeElement !== saveDirInput) {
            saveDirInput.value = saves.path || "";
        }
        document.getElementById("save-files-count").textContent = `${saves.fileCount} arquivos`;
        document.getElementById("save-total-size").textContent = saves.totalSize;
        
        const saveStatus = document.getElementById("save-status");
        if (saves.exists) {
            saveStatus.textContent = "ONLINE";
            saveStatus.className = "status-indicator online";
        } else {
            saveStatus.textContent = "NÃO DETECTADO";
            saveStatus.className = "status-indicator offline";
        }
        
        // Atualiza a seção de OneDrive Backups
        const backups = data.backups;
        const backupDirInput = document.getElementById("backup-dir-input");
        if (backupDirInput && document.activeElement !== backupDirInput) {
            backupDirInput.value = backups.path || "";
        }
        document.getElementById("backup-count").textContent = `${backups.count} backups`;
        document.getElementById("backup-total-size").textContent = backups.totalSize;
        
        const backupStatus = document.getElementById("backup-status");
        if (backups.exists) {
            backupStatus.textContent = "ONLINE";
            backupStatus.className = "status-indicator online";
        } else {
            backupStatus.textContent = "NÃO DETECTADO";
            backupStatus.className = "status-indicator offline";
        }
        
        // Badge do inventário
        document.getElementById("inventory-count-badge").textContent = `${backups.count} DISPONÍVEIS`;
        
    } catch (error) {
        addLog(`Erro ao atualizar status do sistema: ${error.message}`, "error");
        
        // Ajusta indicadores para offline
        document.getElementById("save-status").textContent = "OFFLINE";
        document.getElementById("save-status").className = "status-indicator offline";
        document.getElementById("backup-status").textContent = "OFFLINE";
        document.getElementById("backup-status").className = "status-indicator offline";
    }
}

// Envia os diretórios editados para o servidor
async function saveDir(type) {
    const sourceDir = document.getElementById("save-dir-input").value.trim();
    const backupDir = document.getElementById("backup-dir-input").value.trim();

    if (!sourceDir || !backupDir) {
        addLog("[FALHA] Os caminhos de saves e de backups não podem ficar vazios.", "error");
        return;
    }

    const alvo = type === "saves" ? sourceDir : backupDir;
    addLog(`Salvando novo caminho (${type === "saves" ? "diretório de saves" : "pasta de backups"}): ${alvo}...`, "info");

    try {
        const response = await fetch(`${API_BASE}/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sourceDir, backupDir })
        });
        const data = await response.json();

        if (data.success) {
            addLog(`[SUCESSO] ${data.message}`, "success");
            await refreshAll();
        } else {
            addLog(`[FALHA] ${data.message}`, "error");
        }
    } catch (error) {
        addLog(`Erro ao salvar configurações: ${error.message}`, "error");
    }
}

// Carrega e renderiza a lista de backups
async function loadBackupsList() {
    const listContainer = document.getElementById("backups-list-container");
    if (!listContainer) return;
    
    try {
        const response = await fetch(`${API_BASE}/backups`);
        if (!response.ok) throw new Error("Erro ao obter lista de backups");
        
        const backups = await response.json();
        
        if (backups.length === 0) {
            listContainer.innerHTML = `
                <div class="empty-state">
                    <span class="empty-state-icon">📦</span>
                    <p>NENHUM BACKUP ENCONTRADO NO ONEDRIVE.</p>
                    <p style="font-size: 0.75rem; color: #475569; margin-top: 4px;">Clique em "INICIAR BACKUP BLASTER" para criar seu primeiro ponto de restauração.</p>
                </div>
            `;
            return;
        }
        
        listContainer.innerHTML = "";
        
        backups.forEach(backup => {
            const card = document.createElement("div");
            card.className = "backup-card";
            
            const dateParts = backup.date.split(" ")[0].split("-");
            const timeParts = backup.date.split(" ")[1];
            const formattedDate = `${dateParts[2]}/${dateParts[1]}/${dateParts[0]}`;
            const formattedTime = timeParts;
            
            card.innerHTML = `
                <img class="backup-icon" src="https://cdn2.steamgriddb.com/icon/8ddd389dc325faeb9e252d331df22b72/32/256x256.png" alt="REPO Icon" />
                <div class="backup-info">
                    <div class="backup-name" title="${backup.filename}">${backup.filename}</div>
                    <div class="backup-meta">
                        <span class="backup-meta-date">📅 ${formattedDate} ${formattedTime}</span>
                        <span class="backup-meta-size">${backup.size}</span>
                    </div>
                </div>
                <div class="backup-actions">
                    <button class="btn btn-restore btn-animated-small" onclick="openRestoreModal('${backup.filename}')">
                        RESTAURAR
                    </button>
                    <button class="btn btn-delete btn-animated-small" onclick="openDeleteModal('${backup.filename}')">
                        EXCLUIR
                    </button>
                </div>
            `;
            
            listContainer.appendChild(card);
        });
        
    } catch (error) {
        listContainer.innerHTML = `
            <div class="empty-state" style="border-color: var(--neon-pink);">
                <span class="empty-state-icon" style="color: var(--neon-pink);">⚠️</span>
                <p>ERRO DE COMUNICAÇÃO COM O SERVIDOR.</p>
                <p style="font-size: 0.75rem; color: var(--neon-pink); margin-top: 4px;">${error.message}</p>
            </div>
        `;
    }
}

// Dispara a criação do backup
async function triggerBackup() {
    const btnBackup = document.getElementById("btn-backup");
    btnBackup.disabled = true;
    btnBackup.style.opacity = 0.6;
    
    addLog("Iniciando varredura do diretório de saves...", "info");
    addLog(`Compactando conteúdo de '${document.getElementById("save-dir-input").value}'...`, "info");
    
    try {
        const response = await fetch(`${API_BASE}/backup`, { method: "POST" });
        const data = await response.json();
        
        if (data.success) {
            addLog(`[SUCESSO] ${data.message}`, "success");
            addLog(`Arquivo gerado: ${data.filename} (${data.size})`, "success");
            await refreshAll();
        } else {
            addLog(`[FALHA] ${data.message}`, "error");
        }
    } catch (error) {
        addLog(`Erro crítico durante compressão: ${error.message}`, "error");
    } finally {
        btnBackup.disabled = false;
        btnBackup.style.opacity = 1;
    }
}

// Abre a pasta correspondente no Explorer do Windows
async function openFolder(type) {
    addLog(`Solicitando abertura da pasta de ${type === "saves" ? "saves locais" : "backups no OneDrive"}...`, "info");
    try {
        const response = await fetch(`${API_BASE}/open-folder`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type })
        });
        const data = await response.json();
        if (data.success) {
            addLog(`Gerenciador de arquivos aberto para pasta de ${type}.`, "info");
        } else {
            addLog(`Não foi possível abrir a pasta: ${data.message}`, "warn");
        }
    } catch (error) {
        addLog(`Erro ao abrir pasta: ${error.message}`, "error");
    }
}

// Abre o modal de confirmação de restauração de save com contagem regressiva de segurança
function openRestoreModal(filename) {
    selectedBackupFilename = filename;
    
    const modal = document.getElementById("confirm-modal");
    const modalFilename = document.getElementById("modal-backup-filename");
    const btnConfirm = document.getElementById("btn-confirm-restore");
    const btnCancel = document.getElementById("btn-cancel-restore");
    
    modalFilename.textContent = filename;
    modal.classList.add("active");
    
    // Inicia contagem regressiva de 5 segundos para o botão de confirmação
    let secondsLeft = 5;
    btnConfirm.disabled = true;
    btnConfirm.textContent = `INJETAR SAVE (${secondsLeft}s)`;
    
    clearInterval(restoreCountdownInterval);
    restoreCountdownInterval = setInterval(() => {
        secondsLeft--;
        if (secondsLeft > 0) {
            btnConfirm.textContent = `INJETAR SAVE (${secondsLeft}s)`;
        } else {
            clearInterval(restoreCountdownInterval);
            btnConfirm.disabled = false;
            btnConfirm.textContent = "CONFIRMAR INJEÇÃO DE SAVE";
        }
    }, 1000);
    
    btnCancel.disabled = false;
}

// Fecha o modal de restauração
function closeRestoreModal() {
    clearInterval(restoreCountdownInterval);
    selectedBackupFilename = null;
    
    const modal = document.getElementById("confirm-modal");
    modal.classList.remove("active");
}

// Executa o restore propriamente dito enviando requisição ao backend
async function executeRestore() {
    if (!selectedBackupFilename) return;
    
    const btnConfirm = document.getElementById("btn-confirm-restore");
    const btnCancel = document.getElementById("btn-cancel-restore");
    
    btnConfirm.disabled = true;
    btnCancel.disabled = true;
    btnConfirm.textContent = "RESTAURANDO...";
    
    addLog(`[AVISO] Solicitando restauração do save: ${selectedBackupFilename}`, "warn");
    addLog("Limpando arquivos da pasta de save atual...", "warn");
    addLog("Extraindo arquivos compactados...", "info");
    
    try {
        const response = await fetch(`${API_BASE}/restore`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: selectedBackupFilename })
        });
        
        const data = await response.json();
        
        if (data.success) {
            addLog(`[SUCESSO] ${data.message}`, "success");
            addLog("Restauração concluída. Você já pode iniciar o jogo R.E.P.O.!", "success");
            await refreshAll();
            closeRestoreModal();
        } else {
            addLog(`[FALHA] Restauração malsucedida: ${data.message}`, "error");
            closeRestoreModal();
        }
    } catch (error) {
        addLog(`Erro crítico durante restauração: ${error.message}`, "error");
        closeRestoreModal();
    }
}

// Abre o modal de confirmação de exclusão com contagem regressiva de segurança de 3 segundos
function openDeleteModal(filename) {
    selectedDeleteFilename = filename;
    
    const modal = document.getElementById("delete-modal");
    const modalFilename = document.getElementById("modal-delete-filename");
    const btnConfirm = document.getElementById("btn-confirm-delete");
    const btnCancel = document.getElementById("btn-cancel-delete");
    
    modalFilename.textContent = filename;
    modal.classList.add("active");
    
    // Inicia contagem regressiva de 3 segundos para o botão de confirmação
    let secondsLeft = 3;
    btnConfirm.disabled = true;
    btnConfirm.textContent = `EXCLUIR BACKUP (${secondsLeft}s)`;
    
    clearInterval(deleteCountdownInterval);
    deleteCountdownInterval = setInterval(() => {
        secondsLeft--;
        if (secondsLeft > 0) {
            btnConfirm.textContent = `EXCLUIR BACKUP (${secondsLeft}s)`;
        } else {
            clearInterval(deleteCountdownInterval);
            btnConfirm.disabled = false;
            btnConfirm.textContent = "CONFIRMAR EXCLUSÃO";
        }
    }, 1000);
    
    btnCancel.disabled = false;
}

// Fecha o modal de exclusão
function closeDeleteModal() {
    clearInterval(deleteCountdownInterval);
    selectedDeleteFilename = null;
    
    const modal = document.getElementById("delete-modal");
    modal.classList.remove("active");
}

// Executa a exclusão enviando requisição ao backend
async function executeDelete() {
    if (!selectedDeleteFilename) return;
    
    const btnConfirm = document.getElementById("btn-confirm-delete");
    const btnCancel = document.getElementById("btn-cancel-delete");
    
    btnConfirm.disabled = true;
    btnCancel.disabled = true;
    btnConfirm.textContent = "EXCLUINDO...";
    
    addLog(`[AVISO] Solicitando exclusão do backup: ${selectedDeleteFilename}`, "warn");
    
    try {
        const response = await fetch(`${API_BASE}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: selectedDeleteFilename })
        });
        
        const data = await response.json();
        
        if (data.success) {
            addLog(`[SUCESSO] ${data.message}`, "success");
            await refreshAll();
            closeDeleteModal();
        } else {
            addLog(`[FALHA] Exclusão malsucedida: ${data.message}`, "error");
            closeDeleteModal();
        }
    } catch (error) {
        addLog(`Erro crítico durante exclusão: ${error.message}`, "error");
        closeDeleteModal();
    }
}
