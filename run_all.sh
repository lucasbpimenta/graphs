#!/bin/bash
# Runs the whole pipeline from the repository root.
set -e
PY=${PYTHON:-.venv/bin/python}
cd "$(dirname "$0")"
$PY scripts/00_setores_opc.py data/raw/anp_opc
for s in 01_base_harmonizada 02_redes_regime 03_centralidades 04_modelo_nulo 07_persistencia \
         08_camadas 09_arremate_atual 10_grafo_dirigido 11_remocao 12_figuras \
         13_sobreposicao_nucleo 14_suplementar; do
  echo "== $s"
  $PY scripts/$s.py
done
