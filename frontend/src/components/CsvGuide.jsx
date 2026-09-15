/**
 * Instructions for filling the CSV file, open by default so the expert reads them before uploading.
 * Families and phases come from the database, so the names to type are always the current ones.
 *
 * @param {{ families: Array<{ id: number, family_name: string }>, phasesByFamily: Record<number, Array<object>> }} props
 */
export default function CsvGuide({ families, phasesByFamily }) {
  return (
    <details className="csv-guide" open>
      <summary>Come compilare il file CSV</summary>

      <h4>Procedura consigliata</h4>
      <ol>
        <li>
          Scarica il <strong>modello</strong> (contiene righe di esempio) oppure <strong>esporta i dati attuali</strong> se
          vuoi modificarli.
        </li>
        <li>Apri il file con Excel e scrivi una riga per ogni diagnosi. Le righe di esempio vanno cancellate.</li>
        <li>
          Salva con <em>File → Salva con nome → CSV UTF-8</em>.
        </li>
        <li>
          Carica il file e premi <strong>Controlla file</strong>: non viene salvato nulla, vedi solo quante righe verranno
          aggiunte o modificate ed eventuali errori.
        </li>
        <li>
          Se non ci sono errori, premi <strong>Importa</strong>.
        </li>
      </ol>

      <h4>Colonne</h4>
      <div className="table-wrapper">
        <table className="guide-table">
          <thead>
            <tr>
              <th>Colonna</th>
              <th>Obbligatoria</th>
              <th>Cosa scrivere</th>
              <th>Esempio</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <code>id</code>
              </td>
              <td>No</td>
              <td>
                Vuota per una <strong>nuova</strong> diagnosi. Un numero <strong>modifica</strong> la diagnosi con quell'id
                (lo trovi nell'export). Non inventare numeri.
              </td>
              <td>12</td>
            </tr>
            <tr>
              <td>
                <code>family_name</code>
              </td>
              <td>No</td>
              <td>
                Vuota = diagnosi valida per <strong>tutte le famiglie</strong>. Altrimenti il nome di una famiglia esistente
                (maiuscole e minuscole non contano).
              </td>
              <td>Cella di saldatura robotizzata</td>
            </tr>
            <tr>
              <td>
                <code>phase_number</code>
              </td>
              <td>No</td>
              <td>
                Vuota = valida per <strong>tutta la famiglia</strong>. Altrimenti il numero della fase: in quel caso serve
                anche <code>family_name</code>.
              </td>
              <td>3</td>
            </tr>
            <tr>
              <td>
                <code>phase_name</code>
              </td>
              <td>No</td>
              <td>
                Solo informativa: l'export la riempie, l'import la <strong>ignora</strong>. La fase si sceglie con{" "}
                <code>phase_number</code>.
              </td>
              <td>Saldatura</td>
            </tr>
            <tr>
              <td>
                <code>symptom_description</code>
              </td>
              <td>Sì</td>
              <td>Il sintomo, descritto come lo racconterebbe un operatore. Massimo 500 caratteri.</td>
              <td>Il pallet non arriva in posizione di lavoro</td>
            </tr>
            <tr>
              <td>
                <code>affected_component</code>
              </td>
              <td>Sì</td>
              <td>Il componente coinvolto. Massimo 150 caratteri.</td>
              <td>Sensore presenza pallet</td>
            </tr>
            <tr>
              <td>
                <code>probable_cause</code>
              </td>
              <td>Sì</td>
              <td>La causa probabile.</td>
              <td>Sensore di ingresso sporco o spostato</td>
            </tr>
            <tr>
              <td>
                <code>recommended_solution</code>
              </td>
              <td>Sì</td>
              <td>La procedura da seguire.</td>
              <td>Pulire il sensore e riposizionarlo secondo la dima</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h4>Regole</h4>
      <ul>
        <li>
          Le diagnosi che <strong>non compaiono nel file restano come sono</strong>: il CSV non cancella mai nulla. Per
          eliminare una diagnosi usa la tabella.
        </li>
        <li>
          Basta <strong>un errore</strong> in una riga perché <strong>non venga salvato nulla</strong>: correggi il file e
          ricaricalo.
        </li>
        <li>
          Lo stesso sintomo su più righe indica <strong>cause alternative</strong>. Usa sempre la stessa dicitura per lo
          stesso sintomo.
        </li>
        <li>La prima riga deve contenere i nomi delle colonne, come nel modello.</li>
      </ul>

      <h4>Consigli per Excel</h4>
      <ul>
        <li>
          Come separatore vanno bene sia <code>;</code> sia <code>,</code>.
        </li>
        <li>
          Codifica consigliata <strong>UTF-8</strong>. È accettato anche il CSV normale di Excel per Windows.
        </li>
        <li>Non unire celle. Un testo su più righe nella stessa cella è ammesso.</li>
        <li>
          Un testo che inizia con <code>=</code>, <code>+</code>, <code>-</code> o <code>@</code> viene esportato con un
          apostrofo davanti, così Excel non lo esegue come formula: lascialo, l'import lo toglie.
        </li>
      </ul>

      <h4>Famiglie e fasi disponibili</h4>
      {families.length === 0 ? (
        <p className="hint">Nessuna famiglia nel database.</p>
      ) : (
        <ul className="families-list">
          {families.map((family) => (
            <li key={family.id}>
              <strong>{family.family_name}</strong>:{" "}
              {(phasesByFamily[family.id] ?? []).map((phase) => `${phase.phase_number} ${phase.phase_name}`).join(" · ") ||
                "nessuna fase"}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
