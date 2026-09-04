# MiniCrawler per Pixel 9 e WeChat 8

Questa versione di MiniCrawler raccoglie metadati di Mini Program usando la ricerca
nativa della versione di WeChat installata sul Pixel 9 collegato al Mac.

Il crawler salva ogni risultato usando l'`appID` come identificatore univoco. Il
database viene aggiornato dopo ogni pagina: se l'esecuzione viene fermata, il lavoro
può riprendere dallo stesso punto senza ricominciare da zero.

## Avvio rapido per domani

### 1. Prepara il telefono

1. Collega il Pixel 9 al Mac con il cavo USB.
2. Sblocca il telefono e accetta l'eventuale richiesta **Consenti debug USB**.
3. Verifica che il telefono abbia accesso a Internet senza VPN.
4. Apri WeChat.
5. Apri la pagina della ricerca globale di WeChat e lasciala visibile.

Non è necessario digitare manualmente le keyword: il crawler le cambia internamente.
La parola mostrata nella barra di ricerca può quindi restare ferma mentre il database
continua a crescere.

### 2. Avvia o riprendi con un solo comando

Apri Terminale e incolla:

```bash
cd /Users/lucaferrari/Desktop/MiniCrawler
./start_pixel_crawler.sh
```

Lo script esegue automaticamente queste operazioni:

- verifica il collegamento ADB e l'accesso root del Pixel;
- controlla che WeChat sia aperto sulla pagina di ricerca;
- prepara l'ambiente Python e Frida, se necessario;
- scarica e verifica Frida Server 17.17.0, se non è già nella cache locale;
- avvia temporaneamente Frida sul telefono;
- riprende `MetadataCrawler/data.db` dal checkpoint esistente;
- aggiorna i CSV e il file TXT delle keyword;
- rimuove l'instrumentazione temporanea quando il crawler viene fermato.

La prima esecuzione può richiedere qualche minuto per scaricare Frida. Le esecuzioni
successive usano la copia verificata nella cartella `.cache`.

## Cosa vedrai nel Terminale

Durante una raccolta normale appaiono righe simili a queste:

```text
'酒店' p1: 23 risultati; ricevuti batch=23
'酒店' p2: 20 risultati; ricevuti batch=43
PROGRESSO: 8500/200000; query in coda=77000
KEYWORD TXT: 78000 keyword
```

`p1`, `p2`, ecc. indicano le pagine della stessa keyword. Il valore dopo
`PROGRESSO` è il numero di Mini Program unici già salvati.

Se appare:

```text
PAUSA DI SICUREZZA ... Riprovo tra 900 secondi
```

WeChat sta temporaneamente restituendo `data=null`. Non chiudere e non riavviare il
crawler: attenderà 15 minuti, poi 30 minuti e infine al massimo un'ora tra i tentativi.
Il database rimane integro durante la pausa.

## Controllare lo stato

Apri un secondo Terminale e usa:

```bash
cd /Users/lucaferrari/Desktop/MiniCrawler
./crawler_status.sh
```

Il comando mostra se il crawler è attivo, il numero di Mini Program salvati, le
keyword completate e quelle ancora in coda.

## Fermare tutto correttamente

Nel Terminale in cui gira il crawler premi una sola volta:

```text
Ctrl+C
```

Attendi il ritorno del prompt. Lo script esporta l'ultimo checkpoint, arresta Frida
sul Pixel e ripristina il normale spegnimento dello schermo.

Non scollegare il cavo e non chiudere il Terminale prima che il prompt sia tornato.

## Riprendere in seguito

Per ripartire è sufficiente eseguire nuovamente:

```bash
cd /Users/lucaferrari/Desktop/MiniCrawler
./start_pixel_crawler.sh
```

Non cancellare `MetadataCrawler/data.db`: contiene risultati, pagine completate e
coda delle keyword. Le query già completate non vengono ripetute.

## File prodotti

- `wechat_miniapps_200k.csv`: formato compatibile con il CSV di esempio;
- `wechat_miniapps_200k_detailed.csv`: appID, nome, descrizione, icona, username,
  sviluppatore, versione, keyword di origine e data di verifica;
- `wechat_miniapps_keywords.txt`: tutte le keyword conosciute, una per riga;
- `MetadataCrawler/data.db`: database SQLite e checkpoint principale.

I campi `rating` e `url` del CSV compatibile rimangono vuoti perché la ricerca di
WeChat non li restituisce. Il crawler non genera valori inventati.

## Problemi comuni

### `adb: no devices/emulators found`

Controlla il cavo, sblocca il Pixel e accetta la finestra per il debug USB. Poi prova:

```bash
adb devices
```

Accanto al seriale del telefono deve comparire `device`, non `unauthorized`.

### WeChat non è sulla pagina di ricerca

Apri WeChat, entra nella ricerca globale e torna al Terminale. Lo script aspetterà la
conferma prima di proseguire.

### Il conteggio non aumenta

Controlla il Terminale principale. Se è indicata una pausa di sicurezza, significa che
WeChat sta limitando temporaneamente le richieste. Non usare una VPN per aggirare il
limite: può dipendere anche da account, dispositivo, sessione e cookie.

### Il telefono è stato scollegato

Ferma il comando con `Ctrl+C`, ricollega e sblocca il Pixel, riapri la ricerca di
WeChat e avvia nuovamente `./start_pixel_crawler.sh`.

## Configurazione usata

- Google Pixel 9, architettura `arm64-v8a`;
- Android 16;
- WeChat `com.tencent.mm`, versione 8.0.72 rilevata durante lo sviluppo;
- Frida e Frida Server 17.17.0;
- destinazione predefinita: 200.000 Mini Program unici;
- 8 keyword per batch, massimo 5 pagine per keyword e ritardo di 2 secondi.

Se WeChat viene aggiornato, il bridge potrebbe dover essere adattato prima di una
nuova raccolta.

## Uso responsabile

Una raccolta automatizzata ad alto volume può attivare limiti tecnici e può essere
soggetta ai termini di WeChat/Tencent. Prima di utilizzare o distribuire i dati,
verifica di avere le autorizzazioni necessarie e rispetta normativa, privacy e diritti
dei titolari dei Mini Program. Non usare VPN, account aggiuntivi o altri metodi per
aggirare limiti tecnici.

Politiche ufficiali: <https://www.tencent.com/policies/>

## Progetto originale e citazione

Questa cartella deriva dal progetto MiniCrawler del lavoro seguente:

```bibtex
@article{zhang2021measurement,
  title={A Measurement Study of Wechat Mini-Apps},
  author={Zhang, Yue and Turkistani, Bayan and Yang, Allen Yuqing and Zuo, Chaoshun and Lin, Zhiqiang},
  journal={Proceedings of the ACM on Measurement and Analysis of Computing Systems},
  volume={5},
  number={2},
  pages={1--25},
  year={2021},
  publisher={ACM New York, NY, USA}
}
```
