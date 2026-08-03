# Animarium

Visualizzazione delle popolazioni sintetiche generate da
[GSP](https://github.com/mirko-degli-esposti/gsp). Observable Framework +
DuckDB-WASM, deploy statico.

## Requisito di build

Gli script in `build/` importano `gsp.common` per il registro dei comuni,
i nomi delle zone e il set AVQ — che **non è cablato qui**: `gsp.common`
è la sola fonte. Serve quindi il pacchetto installato:

```bash
pip install -e ~/progetti/gsp
```

Otto script lo usano: `build_bundle`, `build_riferimenti`, `manifest_min`,
`to_parquet`, `medie_nazionali`, `verifica_donor`, `ispeziona_cs`,
`diag_quinq`, `diag_istruzione_eta`.

Senza il pacchetto escono con un messaggio esplicito; tre di essi
accettano `--pop-file` come ripiego.

## Dati

`bundle/` e `deploy/` sono **generati**, ricostruibili con `to_parquet.py`
e non versionati. La sorgente sta in `~/progetti/gsp/data/`.

`build_riferimenti.py:51` cabla quel percorso
(`GSP = ~/progetti/gsp/data/comuni`): è l'unico punto che assume dove viva
GSP sul disco. Gli altri script arrivano ai dati tramite le primitive di
`gsp.common`, che costruiscono i percorsi da sole.
