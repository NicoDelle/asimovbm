# Nicolo delle Piane, per te con affetto

Abbiamo fatto il lavoro principale per collegare benchmark, survey e website:

- Il server web locale legge gli artifact del benchmark e i dati della survey.
- La survey mostra i video nel browser, assegna automaticamente un gruppo, raccoglie le quattro domande Likert e salva le risposte.
- La pagina di confronto mostra predizione del benchmark, risultati reali degli utenti e differenze.
- La pagina dei run permette di cliccare un episodio e vedere i video collegati accanto agli score.
- I video vengono scoperti dalla struttura:
  - `artifacts/survey/videos/<policy>/<view>/<episode>.mp4`
  - `artifacts/survey/json/<policy>/<view>/<episode>.json`
- Abbiamo sistemato il path di playback nel browser e il server ora supporta byte ranges per gli MP4.
- Le esportazioni future devono usare MP4 H.264, `yuv420p`, `1280x720`, `24fps`, così il browser li legge meglio.

Le cose importanti che restano da fare:

1. Rendere i video molto più belli.
   - Devono essere meno blurry, più fluidi, con camera migliori.
   - Le prospettive devono essere giuste per la survey: first person / arrival e bystander devono mostrare davvero quello che promettono.
   - Serve controllare episodio per episodio che il nome corrisponda a quello che si vede nel video.

2. Capire dove sono gli episodi che Luis ha pushato.
   - Forse li ha pushati su un branch diverso, forse non li ha pushati.
   - Bisogna controllare se mancano nel repo, se sono in un branch remoto, oppure se non sono mai arrivati.
   - Questo va risolto perche quei dati sono la ground truth corretta della simulazione.

3. Rendere il website piu intuitivo.
   - La parte researcher deve essere piu facile da capire: episodio, video, predizione, survey e errore devono stare insieme in modo chiaro.
   - La persona che fa la survey deve avere un percorso semplice, senza dover capire la struttura dei file.
   - La persona researcher deve poter cliccare un episodio e capire subito cosa sta guardando.

4. Aggiungere un bottone nel website per lanciare la simulazione.
   - Il bottone deve avviare il comando che genera benchmark data, MP4 e JSON sidecar.
   - Dopo il run, il website dovrebbe aggiornarsi e mostrare i nuovi file nella cartella survey.
   - Idealmente il researcher non dovrebbe dover copiare comandi nel terminale.

5. Aggiungere un bottone per cancellare i dati generati.
   - Deve pulire la cartella survey/artifacts in modo controllato.
   - Deve essere chiarissimo cosa viene cancellato: video, JSON sidecar, risposte survey, oppure tutto.
   - Probabilmente serve una conferma prima di cancellare.

La priorita vera: video migliori, prospettive corrette, e capire dove sono gli episodi di Luis. Senza questo, il website funziona tecnicamente, ma la survey rischia di mostrare evidenza sbagliata o poco leggibile.
