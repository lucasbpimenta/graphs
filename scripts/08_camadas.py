"""Rede offshore como multicamada: uma camada por regime de origem do contrato.

Camadas (redes_mar.CAMADA): concessao (rodadas R1-R17), OPC, partilha (rodadas de partilha, OPP,
excedentes e cessao onerosa), rodada_zero (so na rede atual: na adjudicacao a Petrobras estava
sozinha) e outros (areas BR(3)). Nivel de grupo economico, grupo atual, redes atual e no arremate.

  1. Estrutura de cada camada e participacao da Petrobras (grau na camada, % do peso da camada).
  2. Sobreposicao de arestas entre camadas (Jaccard dos pares de grupos).
  3. Por grupo: grau sobreposto (soma dos graus nas camadas), numero de camadas e coeficiente de
     participacao multiplex P = L/(L-1) * (1 - soma_l (k_l / o)^2) (Battiston et al., 2014),
     0 se o grupo esta numa so camada, 1 se distribui as parcerias igualmente entre as L camadas.
  4. Consorcios por lamina d'agua em cada camada (contratos com mais de um grupo).
Saidas em data/processed: camadas_estrutura.csv, camadas_sobreposicao.csv,
camadas_participacao.csv, camadas_lamina.csv
"""
from itertools import combinations

import networkx as nx
import pandas as pd

from redes_mar import PROC, arestas, arremate, atual, centralidades, estrutura, grafo

pd.set_option("display.width", 250, "display.max_columns", 20, "display.precision", 3)
COMPOSICOES = {"atual": atual(), "arremate": arremate("hoje")}

linhas, sobrep, partic, lamina = [], [], [], []
for rede, comp in COMPOSICOES.items():
    ar = arestas(comp)
    camadas = sorted(ar.camada.unique())
    G = grafo(ar)
    linhas.append({"rede": rede, "camada": "TODAS", **estrutura(G),
                   "grau_Petrobras": nx.degree_centrality(G).get("Petrobras", 0),
                   "%peso_Petrobras": 100 * ar[(ar.u == "Petrobras") | (ar.v == "Petrobras")].peso.sum()
                   / ar.peso.sum()})
    graus = {}
    for cam in camadas:
        a = ar[ar.camada == cam]
        Gc = grafo(a)
        c = centralidades(Gc)
        top = c.drop(index="Petrobras", errors="ignore").sort_values("intermediacao", ascending=False)
        linhas.append({"rede": rede, "camada": cam, **estrutura(Gc),
                       "grau_Petrobras": c.grau.get("Petrobras", 0),
                       "%peso_Petrobras": 100 * a[(a.u == "Petrobras") | (a.v == "Petrobras")].peso.sum()
                       / a.peso.sum(),
                       "maior_intermed_sem_Petrobras": f"{top.index[0]} ({top.intermediacao.iloc[0]:.3f})"})
        graus[cam] = dict(Gc.degree())
    # 2. sobreposicao
    pares = {cam: set(map(tuple, ar[ar.camada == cam][["u", "v"]].values)) for cam in camadas}
    for c1, c2 in combinations(camadas, 2):
        inter = pares[c1] & pares[c2]
        sobrep.append({"rede": rede, "camada_1": c1, "camada_2": c2, "pares_1": len(pares[c1]),
                       "pares_2": len(pares[c2]), "em_comum": len(inter),
                       "jaccard": len(inter) / len(pares[c1] | pares[c2]),
                       "pares_comuns": "; ".join(f"{u}-{v}" for u, v in sorted(inter))})
    # 3. participacao multiplex
    L = len(camadas)
    for g in G:
        k = [graus[cam].get(g, 0) for cam in camadas]
        o = sum(k)
        partic.append({"rede": rede, "grupo": g, "grau_sobreposto": o, "n_camadas": sum(x > 0 for x in k),
                       "participacao": L / (L - 1) * (1 - sum((x / o) ** 2 for x in k)),
                       **{f"grau_{cam}": x for cam, x in zip(camadas, k)}})
    # 4. lamina
    por_contrato = comp.groupby("contrato").agg(camada=("camada", "first"), lamina=("lamina", "first"),
                                                n=("grupo", "nunique"),
                                                pb=("grupo", lambda s: "Petrobras" in set(s)))
    por_contrato["lamina"] = por_contrato.lamina.fillna("sem_info")
    t = por_contrato.groupby(["camada", "lamina"]).agg(contratos=("n", "size"),
                                                       consorcios=("n", lambda s: (s > 1).sum()),
                                                       com_Petrobras=("pb", "sum"))
    t["%consorcio"] = 100 * t.consorcios / t.contratos
    lamina.append(t.reset_index().assign(rede=rede))

est = pd.DataFrame(linhas)
sob = pd.DataFrame(sobrep)
par = pd.DataFrame(partic).sort_values(["rede", "grau_sobreposto"], ascending=[True, False])
lam = pd.concat(lamina)
est.to_csv(PROC / "camadas_estrutura.csv", index=False)
sob.to_csv(PROC / "camadas_sobreposicao.csv", index=False)
par.to_csv(PROC / "camadas_participacao.csv", index=False)
lam.to_csv(PROC / "camadas_lamina.csv", index=False)

print("1. ESTRUTURA DAS CAMADAS (mar, grupo atual)")
print(est[["rede", "camada", "vertices", "arestas", "peso_total", "densidade", "componentes", "eficiencia",
           "grau_Petrobras", "%peso_Petrobras", "maior_intermed_sem_Petrobras"]].to_string(index=False), "\n")
print("2. SOBREPOSICAO DE ARESTAS ENTRE CAMADAS")
print(sob.drop(columns="pares_comuns").to_string(index=False), "\n")
print("   pares comuns, rede atual:")
for r in sob[(sob.rede == "atual") & (sob.em_comum > 0)].itertuples():
    print(f"   {r.camada_1} x {r.camada_2}: {r.pares_comuns}")
print("\n3. PARTICIPACAO MULTIPLEX, rede atual (grupos com grau sobreposto >= 4)")
print(par[(par.rede == "atual") & (par.grau_sobreposto >= 4)].drop(columns="rede").to_string(index=False), "\n")
print("4. CONSORCIOS POR LAMINA E CAMADA")
print(lam.pivot_table(index=["camada", "lamina"], columns="rede",
                      values=["contratos", "%consorcio"]).round(1).to_string())
