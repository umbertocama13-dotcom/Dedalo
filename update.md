# Update da eseguire dopo la versione finita di dedalo.v1
Questo è un PoC e testandolo nella sua v1 ne ho riconosciuto il limite più grande: non fa quello che deve fare per quello che è stato pensato: deve semplificare la ricerca guasti e fornire la soluzione adeguata, ma ad oggi l'operatore deve sapere praticamente a memoria la colonna dei sintomi per poter risalire alla soluzione e non gli è permesso scrivere qualcosa che si avvicina alla descrizione del sintomo (altrimenti esce fuori il "not found")


# Inserimento di un vector store index e ricerca con llama index

DOBBIAMO portare al livello successivo la ricerca per dargli la funzione MINIMA del concept ideato.

Serve fare almeno uno step in più e pensavo di strutturare la ricerca con una cos similarity (vector index e llama index) che poi si ritorna il risultato della tabella;
A questa ricerca si può integrare anche un modello di LLM per la generazione di domande e risposte per guidare effettivamente l'utente. 

CONSIDERAZIONE:Se si decide di aggiungere LLM, optare per lo sviluppo completo di una chat con LLM che porta alla risoluzione

NOTA: Gli esempi qui sotto NON rispettano i nostri standard di codifica, il codice rimane comunque da adattare

## esempio store index / llama index
In questo esempio si trattava di chunkerizzare i documenti, direi che possiamo saltare quella fase in quanto le stringhe contenute nel database non sono così lunghe e trattare ciascuna riga di sintomo come se fosse un chunk.

### Embedding, indicizzazione e ricerca con LlamaIndex

def build_llama_index(chunks: List[DocumentChunk]) -> VectorStoreIndex:
    """Costruisce un indice LlamaIndex dai chunks già estratti"""

    # Convertiamo i nostri DocumentChunk nel formato che LlamaIndex capisce (LlamaDocument)
    # LlamaIndex non conosce la nostra dataclass, quindi traduciamo
    documenti = [
        LlamaDocument(text=chunk.text, metadata=chunk.metadata)
        for chunk in chunks
    ]


    # SentenceSplitter ri-chunkerizza i documenti internamente a LlamaIndex; usiamo gli stessi parametri del nostro splitter per coerenza
    parser = SentenceSplitter(chunk_size=set_chunk_size, chunk_overlap=set_chunk_overlap)

    # VectorStoreIndex costruisce l'indice vettoriale: per ogni documento calcola l'embedding e lo salva in memoria
    indice = VectorStoreIndex.from_documents(documenti, transformations=[parser])

    print(f"Indice costruito: {len(documenti)} documenti indicizzati")
    return indice


def search_llamaindex(indice: VectorStoreIndex, query: str, n_risultati: int = 3) -> List[Dict]:
    """Cerca i chunks più rilevanti per una query"""
    query_engine = indice.as_query_engine(similarity_top_k=n_risultati)
    risposta = query_engine.query(query)

    return [
        {
            "testo": nodo.node.text,
            "source": nodo.node.metadata.get("source", ""),
            "type": nodo.node.metadata.get("type", ""),
        }
        for nodo in risposta.source_nodes
    ]

### TEST
indice = build_llama_index(all_chunks)
risultati = search_llamaindex(indice, "requisiti normativi conformità")
for r in risultati:
     print(f"\n[{r['source']}]\n{r['testo']}")

## Esempio LLM invoke
Se vector e llaman index non dovesse bastare per il PoC, inserisco una chiave API di open AI e possiamo procedere con la creazione di un llm.


esempio invoke di LLM
def llm_invoke(prompt: str, temperature: float = 0.0) -> str:
    """Chiamata singola al provider scelto, usando i client già istanziati."""
    if LLM_PROVIDER == "openai":
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature = temperature
        )
        return response.choices[0].message.content



# interfaccia di inserimento per utente esperto 
Serve aggiungere un'interfaccia dedicata all'utente esperto, in modo che questo possa popolare le tabelle di sintomo, causa, soluzione ed associate; inoltre deve avere la possibilità di visualizzare i vecchi inserimenti e di modificarli qualora lo ritiene necessario


# Unificazione delle tabelle nel database(proposta da valutare)
Ho riguardato la struttura delel tabelle e sono tutte divise, credo che sia stato fatto per non avere enormi ripetizioni all'interno della stessa tabella che porterebbe ad avere un rallentamento generale delle query quando il database inizierà a popolarsi massicciamente. 
Se ho ragione su questa ipotesi manteniamo così le tabelle, ma se non c'è reale motivo tecnico di averle separate è meglio unificare tutto su una singola tabella

## Gestione eccezioni
La tabella diagnostic_exception non credo abbia davvero senso di esistere, tutti i sintomi devono rimanere raggruppati in un'unica tabella. 

## Valuatare l'utilità delle fasi
Noi abbiamo messo anche le fasi di lavorazione che credo essere concettualmente giusto, MA ha un limite: le celle produttive con sistemi integrati spesso si fermano nei processi perché un componente ha un problema e manda in allarme tutta la cella. Ha quindi senso separare le fasi del processo se la cella si ferma anche per un motivo che non è strettamente collegato alla fase stessa che ha riscontarto il problema?

esempio pratico: 
    "sintomo":  La cella di saldatura non completa il ciclo ed entra in allarme
    "causa":    Il nastro trasportatore pallet è guasto e manda in allarme tutta la cella 
    "soluzione": ricercare il guasto nel nastro trasportatore e nella sua logica


# Estrazione/immissione tabella sql in file CSV
Essendo un database che non salva dati produttivi, ma è uno storage di conoscenza, è utile avere la possibilità di poter estrarre le tabelle dal database sotto forma di csv e poter caricare i dati sempre da un csv;
Immagina il primo inserimento dove le voci dei sintomi sono ripetuti un sacco di volte: l'operatore esperto sarebbe molto veloce a fare una tabella excel (che facilita anche l'inseriemnto del sintomo sempre con la stessa dicitura esatta) che poi esporta in cvs e carica nel DB; la stessa cosa accade per una modifica strutturale della linea che prevede l'aggiunta massiccia di voci.

