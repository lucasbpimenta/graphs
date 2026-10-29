"""Tabelas do material suplementar (sup_novo.tex), nivel de grupo economico.

  1. Modelos de referencia do grafo projetado, nas redes offshore atual e no arremate (grupo atual):
     Erdos-Renyi G(n, m) com o mesmo numero de vertices e arestas, e modelo de configuracao do
     grafo projetado (trocas duplas de arestas que preservam o grau de cada vertice). Os dois
     ignoram a estrutura bipartida e servem de contraste com o modelo nulo do 04.
  2. Contraste mar x terra x carteira completa (rede atual): metricas globais e maiores
     intermediacoes.
  3. Centralidades dos grupos da rede offshore atual.
  4. Composicao dos grupos economicos com mais de uma empresa na carteira offshore.
Saidas em data/processed: sup_referencias.csv, sup_ambiente.csv, sup_centralidades.csv,
sup_grupos.csv
"""
import random

import networkx as nx
import numpy as np
import pandas as pd

from redes_mar import COLS, PROC, _consolida, arestas, arremate, atual, centralidades, estrutura, grafo

N_SIM = 1000
SEMENTE = 20261026
pd.set_option("display.width", 250, "display.max_columns", 30, "display.precision", 3)


def medidas(G):
    comps = [len(c) for c in nx.connected_components(G)]
    return {"clustering": nx.average_clustering(G), "componentes": len(comps),
            "%maior_componente": 100 * max(comps) / G.number_of_nodes(),
            "eficiencia": nx.global_efficiency(G),
            "grau_maximo": max(nx.degree_centrality(G).values()),
            "intermediacao_maxima": max(nx.betweenness_centrality(G).values()),
            "proximidade_maxima": max(nx.closeness_centrality(G).values())}


# ---------------------------------------------------------------- 1. ER e configuracao projetada
rng = random.Random(SEMENTE)
linhas = []
for rede, comp in {"atual": atual(), "arremate": arremate("hoje")}.items():
    G = nx.Graph(grafo(arestas(comp)))
    n, m = G.number_of_nodes(), G.number_of_edges()
    obs = medidas(G)
    sims = {"erdos_renyi": [], "configuracao_projetada": []}
    for _ in range(N_SIM):
        sims["erdos_renyi"].append(medidas(nx.gnm_random_graph(n, m, seed=rng.randrange(2**31))))
        H = nx.Graph(G.edges())
        nx.double_edge_swap(H, nswap=10 * m, max_tries=1000 * m, seed=rng.randrange(2**31))
        sims["configuracao_projetada"].append(medidas(H))
    for modelo, s in sims.items():
        s = pd.DataFrame(s)
        for med, v in obs.items():
            linhas.append({"rede": rede, "modelo": modelo, "medida": med, "observado": v,
                           "media_nula": s[med].mean(), "dp_nulo": s[med].std(),
                           "p_maior_igual": (s[med] >= v - 1e-12).mean(),
                           "p_menor_igual": (s[med] <= v + 1e-12).mean()})
    print(f"{rede}: n={n}, m={m}, {N_SIM} simulacoes por modelo", flush=True)
ref = pd.DataFrame(linhas)
ref.to_csv(PROC / "sup_referencias.csv", index=False)
print("\n1. MODELOS DE REFERENCIA DO GRAFO PROJETADO")
print(ref.round(3).to_string(index=False), "\n")

# ---------------------------------------------------------------- 2. mar x terra x total
part = pd.read_csv(PROC / "participacoes_atuais.csv")
amb = []
for nome, d in {"mar": part[part.ambiente == "Mar"], "terra": part[part.ambiente != "Mar"], "total": part}.items():
    comp = _consolida(d[COLS])
    # acumulacoes marginais (so em terra) nao estao em redes_mar.CAMADA; sem isto sairiam das arestas
    comp["camada"] = comp.camada.fillna("outros")
    G = grafo(arestas(comp))
    c = centralidades(G).sort_values("intermediacao", ascending=False)
    n_contr = comp.contrato.nunique()
    consorcios = (comp.groupby("contrato").grupo.nunique() > 1).sum()
    amb.append({"rede": nome, "contratos": n_contr, "consorcios": consorcios,
                "grupos_na_carteira": comp.grupo.nunique(), **estrutura(G),
                "maiores_intermediacoes": "; ".join(f"{g} ({v:.3f})" for g, v in c.intermediacao.head(5).items())})
amb = pd.DataFrame(amb)
amb.to_csv(PROC / "sup_ambiente.csv", index=False)
print("2. MAR x TERRA x CARTEIRA COMPLETA (rede atual)")
print(amb.drop(columns=["conectividade_algebrica", "raio_espectral", "raio_espectral_ponderado"]).T.to_string(), "\n")

# ---------------------------------------------------------------- 3. centralidades
cen = centralidades(grafo(arestas(atual()))).sort_values("intermediacao", ascending=False)
cen.to_csv(PROC / "sup_centralidades.csv")
print("3. CENTRALIDADES, REDE OFFSHORE ATUAL")
print(cen.round(3).to_string(), "\n")

# ---------------------------------------------------------------- 4. grupos
mar = part[part.ambiente == "Mar"]
g = mar.groupby("grupo").empresa.apply(lambda s: sorted(set(s)))
g = g[g.apply(len) > 1]
g.apply("; ".join).rename("empresas").to_csv(PROC / "sup_grupos.csv")
print("4. GRUPOS COM MAIS DE UMA EMPRESA NA CARTEIRA OFFSHORE")
for grupo_, emp in g.items():
    print(f"   {grupo_}: {'; '.join(emp)}")
