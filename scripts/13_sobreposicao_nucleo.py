"""Duas verificacoes pedidas pela revisao de literatura (blocos B, C e D).

  1. Sobreposicao de camadas contra o modelo nulo. O grafo bipartido grupo x contrato de cada
     camada e embaralhado separadamente, com as mesmas trocas ((a,x),(b,y)) -> ((a,y),(b,x)) do
     04_modelo_nulo.py, que preservam o numero de contratos de cada grupo em cada camada e o
     tamanho de cada consorcio (modelo de sequencia de graus fixa, FDSM). Cada camada simulada e
     projetada, e as arestas em comum entre pares de camadas sao comparadas com as observadas.
     Sem esse teste, a sobreposicao poderia refletir so o grau alto da Petrobras e das grandes
     petroleiras em todas as camadas. Repete-se a conta excluindo os pares com a Petrobras.
  2. Permanencia do nucleo entre o arremate e hoje (grupo atual dos dois lados): membros do k-core
     maximo nas duas redes e fracao das arestas do arremate mantidas hoje, separando nucleo-nucleo,
     nucleo-periferia e periferia-periferia (nucleo definido no arremate).
Saidas em data/processed: sobreposicao_nula.csv, nucleo_permanencia.csv
"""
import random
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd

from redes_mar import PROC, arestas, arremate, atual, grafo

N_SIM = 1000
TROCAS_POR_ARESTA = 10
SEMENTE = 20261026


def embaralha(lig, rng):
    lig = list(lig)
    presentes = set(lig)
    if len(lig) < 2:
        return lig
    for _ in range(TROCAS_POR_ARESTA * len(lig)):
        i, j = rng.sample(range(len(lig)), 2)
        (a, x), (b, y) = lig[i], lig[j]
        if a == b or x == y or (a, y) in presentes or (b, x) in presentes:
            continue
        presentes -= {(a, x), (b, y)}
        presentes |= {(a, y), (b, x)}
        lig[i], lig[j] = (a, y), (b, x)
    return lig


def pares(lig):
    membros = {}
    for g, c in lig:
        membros.setdefault(c, set()).add(g)
    return {(u, v) for gs in membros.values() for u, v in combinations(sorted(gs), 2)}


def sobreposicao(p1, p2, sem_pb):
    if sem_pb:
        p1 = {e for e in p1 if "Petrobras" not in e}
        p2 = {e for e in p2 if "Petrobras" not in e}
    uniao = p1 | p2
    return len(p1 & p2), (len(p1 & p2) / len(uniao) if uniao else np.nan)


pd.set_option("display.width", 250, "display.max_columns", 20, "display.precision", 3)
rng = random.Random(SEMENTE)

# ---------------------------------------------------------------- 1. sobreposicao x modelo nulo
linhas = []
for rede, comp in {"atual": atual(), "arremate": arremate("hoje")}.items():
    lig = {cam: list(zip(g.grupo, g.contrato)) for cam, g in comp.groupby("camada")}
    obs = {cam: pares(l) for cam, l in lig.items()}
    camadas = sorted(c for c in obs if obs[c])
    sims = [{cam: pares(embaralha(lig[cam], rng)) for cam in camadas} for _ in range(N_SIM)]
    for c1, c2 in combinations(camadas, 2):
        for sem_pb in (False, True):
            n_obs, j_obs = sobreposicao(obs[c1], obs[c2], sem_pb)
            nulos = np.array([sobreposicao(s[c1], s[c2], sem_pb) for s in sims])
            linhas.append({"rede": rede, "camada_1": c1, "camada_2": c2,
                           "pares": "sem Petrobras" if sem_pb else "todos",
                           "comum_obs": n_obs, "comum_nulo": nulos[:, 0].mean(),
                           "comum_p95": np.percentile(nulos[:, 0], 95),
                           "jaccard_obs": j_obs, "jaccard_nulo": np.nanmean(nulos[:, 1]),
                           "p_maior_igual": (nulos[:, 0] >= n_obs).mean()})
    print(f"{rede}: {N_SIM} simulacoes por camada concluidas", flush=True)
sob = pd.DataFrame(linhas)
sob.to_csv(PROC / "sobreposicao_nula.csv", index=False)
print("\n1. SOBREPOSICAO DE ARESTAS ENTRE CAMADAS x MODELO NULO POR CAMADA")
print("   (p = fracao das simulacoes com tantas ou mais arestas em comum que o observado)")
print(sob.to_string(index=False), "\n")

# ---------------------------------------------------------------- 2. permanencia do nucleo
G_ini, G_fim = grafo(arestas(arremate("hoje"))), grafo(arestas(atual()))
nuc = {}
for nome, G in (("arremate", G_ini), ("atual", G_fim)):
    core = nx.core_number(G)
    k = max(core.values())
    nuc[nome] = {g for g, c in core.items() if c == k}
    print(f"2. {nome}: {k}-core com {len(nuc[nome])} grupos: {sorted(nuc[nome])}")
fica = nuc["arremate"] & nuc["atual"]
ambos = set(G_ini) & set(G_fim)
print(f"   no nucleo nas duas redes: {len(fica)} de {len(nuc['arremate'])} "
      f"(permanencia {len(fica) / len(nuc['arremate']):.2f})")
print(f"   sairam do nucleo: {sorted(nuc['arremate'] - nuc['atual'])}; "
      f"entraram: {sorted(nuc['atual'] - nuc['arremate'])}")
print(f"   grupos do nucleo do arremate que sairam da rede: {sorted(nuc['arremate'] - set(G_fim))}")
print(f"   grupos fora do nucleo no arremate que sairam da rede: "
      f"{len((set(G_ini) - nuc['arremate']) - set(G_fim))} de {len(set(G_ini) - nuc['arremate'])}")

tipos = []
for u, v, d in G_ini.edges(data=True):
    n_core = (u in nuc["arremate"]) + (v in nuc["arremate"])
    tipo = {2: "nucleo-nucleo", 1: "nucleo-periferia", 0: "periferia-periferia"}[n_core]
    tipos.append({"u": u, "v": v, "tipo": tipo, "peso_arremate": d["weight"],
                  "mantida": G_fim.has_edge(u, v),
                  "peso_atual": G_fim[u][v]["weight"] if G_fim.has_edge(u, v) else 0})
t = pd.DataFrame(tipos)
t.to_csv(PROC / "nucleo_permanencia.csv", index=False)
res = t.groupby("tipo").agg(arestas=("mantida", "size"), mantidas=("mantida", "sum"),
                            peso_arremate=("peso_arremate", "sum"), peso_atual=("peso_atual", "sum"))
res["%mantidas"] = 100 * res.mantidas / res.arestas
print("\n   arestas do arremate por posicao em relacao ao nucleo do arremate:")
print(res.to_string())
novas = [(u, v) for u, v in G_fim.edges() if not G_ini.has_edge(u, v)]
n_core_novas = pd.Series([(u in nuc["arremate"]) + (v in nuc["arremate"]) for u, v in novas]).value_counts()
print(f"\n   arestas criadas ({len(novas)}) pelo numero de pontas no nucleo do arremate: "
      f"{n_core_novas.sort_index(ascending=False).to_dict()}")
