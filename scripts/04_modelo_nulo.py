"""Modelo nulo de configuracao bipartido para a rede de consorcios.

A rede observada e a projecao de um grafo bipartido grupo x contrato. O modelo nulo embaralha
as ligacoes desse grafo por trocas de arestas ((a,x),(b,y)) -> ((a,y),(b,x)), que preservam o
numero de contratos de cada grupo e o tamanho de cada consorcio. A projecao de cada rede
simulada passa pelo mesmo procedimento da observada, de modo que os cliques gerados pela
projecao estao presentes nos dois lados da comparacao.

Duas versoes:
  livre   trocas entre quaisquer contratos;
  regime  trocas so entre contratos do mesmo regime de origem (preserva tambem a presenca de
          cada grupo em cada regime).

Redes testadas (nivel de grupo economico): atual e adjudicacao, no total e no recorte offshore (_mar).
Saida: data/processed/modelo_nulo.csv
"""
import random
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
N_SIM = 1000
TROCAS_POR_ARESTA = 10
SEMENTE = 20261016


def bipartido(part):
    """(grupo, contrato) unicos e regime de cada contrato."""
    b = part[["grupo", "contrato", "regime"]].drop_duplicates(["grupo", "contrato"])
    return list(zip(b.grupo, b.contrato)), dict(zip(b.contrato, b.regime))


def embaralha(arestas, regime_de, por_regime, rng):
    arestas = list(arestas)
    presentes = set(arestas)
    if por_regime:
        idx = {}
        for i, (_, c) in enumerate(arestas):
            idx.setdefault(regime_de[c], []).append(i)
        blocos = [v for v in idx.values() if len(v) > 1]
        pesos = [len(v) for v in blocos]
    for _ in range(TROCAS_POR_ARESTA * len(arestas)):
        if por_regime:
            i, j = rng.sample(rng.choices(blocos, weights=pesos)[0], 2)
        else:
            i, j = rng.sample(range(len(arestas)), 2)
        (a, x), (b, y) = arestas[i], arestas[j]
        if a == b or x == y or (a, y) in presentes or (b, x) in presentes:
            continue
        presentes -= {(a, x), (b, y)}
        presentes |= {(a, y), (b, x)}
        arestas[i], arestas[j] = (a, y), (b, x)
    return arestas


def projeta(arestas):
    membros = {}
    for g, c in arestas:
        membros.setdefault(c, []).append(g)
    G = nx.Graph()
    for gs in membros.values():
        for u, v in combinations(sorted(gs), 2):
            w = G[u][v]["weight"] + 1 if G.has_edge(u, v) else 1
            G.add_edge(u, v, weight=w)
    return G


def estatisticas(G):
    comps = [len(c) for c in nx.connected_components(G)]
    pesos = [d["weight"] for _, _, d in G.edges(data=True)]
    return {
        "vertices": G.number_of_nodes(),
        "arestas": G.number_of_edges(),
        "peso_medio_aresta": np.mean(pesos),
        "peso_maximo_aresta": max(pesos),
        "grau_maximo": max(nx.degree_centrality(G).values()),
        "intermediacao_maxima": max(nx.betweenness_centrality(G).values()),
        "proximidade_maxima": max(nx.closeness_centrality(G).values()),
        "clustering_medio": nx.average_clustering(G),
        "componentes": len(comps),
        "%maior_componente": 100 * max(comps) / G.number_of_nodes(),
    }


base = {
    "atual": pd.read_csv(PROC / "participacoes_atuais.csv"),
    "adjudicacao": pd.read_csv(PROC / "composicao_adjudicacao.csv"),
}
redes = {}
for nome, d in base.items():
    redes[nome] = d
    redes[f"{nome}_mar"] = d[d.ambiente == "Mar"]
rng = random.Random(SEMENTE)
linhas = []
for nome, part in redes.items():
    arestas, regime_de = bipartido(part)
    obs = estatisticas(projeta(arestas))
    for versao, por_regime in (("livre", False), ("regime", True)):
        sims = pd.DataFrame([estatisticas(projeta(embaralha(arestas, regime_de, por_regime, rng)))
                             for _ in range(N_SIM)])
        for m, v in obs.items():
            linhas.append({"rede": nome, "modelo": versao, "medida": m, "observado": v,
                           "media_nula": sims[m].mean(), "dp_nulo": sims[m].std(),
                           "p_maior_igual": (sims[m] >= v).mean(), "p_menor_igual": (sims[m] <= v).mean()})
        print(f"{nome} / {versao}: {N_SIM} simulacoes concluidas", flush=True)

res = pd.DataFrame(linhas)
res.to_csv(PROC / "modelo_nulo.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 20)
for nome in redes:
    t = res[res.rede == nome].pivot_table(index="medida", columns="modelo",
                                          values=["media_nula", "p_maior_igual", "p_menor_igual"], sort=False)
    t.insert(0, "observado", res[(res.rede == nome) & (res.modelo == "livre")].set_index("medida").observado)
    print(f"\nREDE {nome.upper()} (nivel grupo; p = fracao das simulacoes >= ou <= observado)")
    print(t.round(4))
