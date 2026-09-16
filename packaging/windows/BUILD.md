# Costruire l'installer Windows di Dedalo

Guida passo passo per creare `Dedalo-Setup.exe` su una macchina (anche virtuale) con **Windows 10 o 11 a 64 bit**.
Tutti i comandi vanno copiati e incollati in **PowerShell**, un blocco alla volta.

> PyInstaller non può creare un eseguibile Windows lavorando da Linux: la build va fatta su Windows.

## Requisiti della macchina

- Windows 10/11 64 bit aggiornato
- almeno 8 GB di RAM e 15 GB di disco libero
- connessione a internet (solo durante la build)

---

## 1. Installare gli strumenti (una volta sola)

Apri **PowerShell** (menu Start → digita *PowerShell*) e incolla:

```powershell
winget install --id Python.Python.3.12 -e --source winget
winget install --id OpenJS.NodeJS.LTS -e --source winget
winget install --id JRSoftware.InnoSetup -e --source winget
winget install --id Git.Git -e --source winget
winget install --id Microsoft.VCRedist.2015+.x64 -e --source winget
```

L'ultimo, il *Visual C++ Redistributable*, serve a PyTorch durante l'export del modello: senza, la build si ferma perché non riesce a caricare le sue librerie (`c10.dll`).

Se `winget` non esiste, aggiorna *App Installer* dal Microsoft Store e riprova.

**Chiudi PowerShell e riaprilo**, così vede i programmi appena installati. Poi controlla:

```powershell
py -3.12 --version
node --version
git --version
Get-ChildItem "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe", "$env:LocalAppData\Programs\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
```

Devi vedere Python 3.12.x, Node v22 o superiore, una versione di Git e il percorso di `ISCC.exe`. L'ultimo comando controlla tutte le cartelle in cui `winget` può installare Inno Setup: senza privilegi di amministratore finisce nella cartella dell'utente, e va bene lo stesso. Se non stampa nulla, Inno Setup non è installato: ripeti il suo comando `winget`.

## 2. Scaricare il progetto

```powershell
cd $HOME
git clone https://github.com/umbertocama13-dotcom/Dedalo.git
cd Dedalo
git checkout feature/windows-desktop
```

Quando la branch sarà unita su `main`, l'ultimo comando non servirà più.

## 3. Costruire l'installer

```powershell
cd $HOME\Dedalo
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Version 2.0.0
```

La prima volta richiede **20-40 minuti**: scarica PyTorch e il modello (~1 GB) per esportarlo in ONNX, poi le dipendenze dell'app, costruisce il frontend e l'installer. Alla fine compare:

```
Done: C:\Users\...\Dedalo\packaging\windows\output\Dedalo-Setup.exe (... MB)
```

Per aprire la cartella dell'installer:

```powershell
explorer $HOME\Dedalo\packaging\windows\output
```

## 4. Installare e provare

1. Doppio clic su `Dedalo-Setup.exe`.
2. Windows SmartScreen può mostrare *"Windows ha protetto il PC"*: clic su **Ulteriori informazioni** → **Esegui comunque**. Succede perché l'eseguibile non è firmato con un certificato a pagamento.
3. Segui l'installazione (lascia spuntata *Crea un'icona sul desktop*).
4. Doppio clic sull'icona **Dedalo** sul desktop.

Checklist di prova:

- [ ] schermata di primo avvio → crea l'esperto con *Carica le diagnosi di esempio*
- [ ] famiglia *Cella di saldatura robotizzata*, fase *Non so*, testo `la cella si pianta e va in allarme a metà ciclo` → 3 ipotesi e domanda sul componente
- [ ] Knowledge base → **Esporta dati attuali** e **Scarica modello**: i file finiscono in *Download*
- [ ] Knowledge base → carica un CSV modificato → **Controlla file** → **Importa**
- [ ] Utenti → crea un operatore → Esci → accedi come operatore (non vede Knowledge base e Utenti)
- [ ] con Dedalo aperto, doppio clic di nuovo sull'icona → messaggio *"Dedalo è già aperto"*
- [ ] chiudi e riapri → i dati ci sono ancora
- [ ] disattiva la rete della VM, riapri Dedalo → funziona lo stesso
- [ ] *Impostazioni → App* → disinstalla Dedalo → la cartella dei dati resta (vedi sotto)

## 5. Dove sono dati e log

| Cosa | Percorso |
|---|---|
| Programma | `C:\Program Files\Dedalo` (oppure la cartella utente, se installato senza privilegi di amministratore) |
| Database (knowledge base, utenti) | `%LOCALAPPDATA%\Dedalo\dedalo.db` |
| Configurazione (es. OpenAI) | `%LOCALAPPDATA%\Dedalo\dedalo.env` |
| Log | `%LOCALAPPDATA%\Dedalo\logs\dedalo.log` |

Aprire il log:

```powershell
notepad $env:LOCALAPPDATA\Dedalo\logs\dedalo.log
```

Backup della knowledge base (con Dedalo chiuso):

```powershell
Copy-Item $env:LOCALAPPDATA\Dedalo\dedalo.db "$HOME\Desktop\dedalo-backup-$(Get-Date -Format yyyyMMdd).db"
```

Rifare la prova del **primo avvio** senza perdere i dati attuali (con Dedalo chiuso): la cartella viene rinominata, non cancellata.

```powershell
Rename-Item $env:LOCALAPPDATA\Dedalo "Dedalo-prova-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

## 6. Ricostruire dopo una modifica al codice

Il modello ONNX è già esportato: `-SkipModelExport` salta la parte più lunga.

```powershell
cd $HOME\Dedalo
git pull
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Version 2.0.1 -SkipModelExport
```

Installare la nuova versione sopra la vecchia la aggiorna: i dati restano.

## Problemi frequenti

| Problema | Soluzione |
|---|---|
| `build.ps1 cannot be loaded because running scripts is disabled` | usa il comando con `-ExecutionPolicy Bypass` come sopra |
| `py not found` o `npm not found` | chiudi e riapri PowerShell dopo le installazioni del passo 1 |
| `Inno Setup 6 not found` | l'errore elenca le cartelle controllate; se compare, Inno Setup non è installato davvero: ripeti `winget install --id JRSoftware.InnoSetup -e` |
| `Visual C++ Redistributable x64 is missing`, oppure `WinError 126` / `c10.dll` | installa il redistributable: `winget install --id Microsoft.VCRedist.2015+.x64 -e`, poi chiudi e riapri PowerShell |
| La build si ferma su `pip install` | problema di rete o proxy aziendale: riprova, oppure configura il proxy di pip |
| Finestra di Dedalo bianca o che non si apre | manca WebView2: installa *Microsoft Edge WebView2 Runtime* dal sito Microsoft e riprova; dettagli nel log |
| *"Dedalo non si è avviato"* nella finestra | leggi il motivo e il log (passo 5) |
| L'antivirus mette in quarantena `Dedalo.exe` | falso positivo frequente con PyInstaller: aggiungi un'eccezione per la cartella del programma |
