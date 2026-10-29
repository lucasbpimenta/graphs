"""Remocao de vertices e contrafactual do direito de preferencia (mar, grupo atual).

  1. Rede sem a Petrobras, no arremate e hoje: metricas globais (redes_mar.estrutura).
  2. Curvas de robustez: remocao sequencial por grau inicial, por intermediacao recalculada a cada
     passo e aleatoria (N_SIM sorteios). S(q) = maior componente / vertices iniciais apos remover a
     fracao q; indice R = media de S sobre todos os passos (Schneider et al., 2011). Eficiencia
     global acompanhada da mesma forma.
  3. Contrafactual do direito de preferencia (Lei 13.365/2016, Decreto 9.041/2017), com a lista
     de data/raw/preferencia_petrobras.csv (resolucoes do CNPE e atas da ANP; pesquisa de
     24/10/2026). A Petrobras sai dos contratos e os
     demais socios ficam:
       estrito  contratos em que ela entrou so pela preferencia, depois de perder a disputa com o
                proprio consorcio (entrada_petrobras == "so_preferencia");
       amplo    todos os contratos em que ela exerceu a preferencia, mesmo os que venceu com
                consorcio proprio (limite superior: ali ela teria entrado de qualquer forma).
     Libra (participacao obrigatoria de 30% na lei original) fica fora dos dois: a Petrobras
     ofertou 10% no consorcio vencedor e estaria no contrato mesmo sem a regra.
Saidas em data/processed: remocao_petrobras.csv, remocao_curvas.csv, remocao_contrafactual.csv
"""
import random

import networkx as nx
import numpy as np
import pandas as pd

from redes_mar import PROC, RAW, arestas, arremate, atual, estrutura, grafo

N_SIM = 500
SEMENTE = 20261024
pd.set_option("display.width", 250, "display.max_columns", 30, "display.precision", 3)
COMP = {"arremate": arremate("hoje"), "atual": atual()}
REDES = {k: grafo(arestas(c)) for k, c in COMP.items()}

# ---------------------------------------------------------------- 1. sem a Petrobras
linhas = {}
for nome, G in REDES.items():
    H = G.copy()
    H.remove_node("Petrobras")
    isolados = list(nx.isolates(H))
    H.remove_nodes_from(isolados)
    linhas[(nome, "completa")] = estrutura(G)
    linhas[(nome, "sem Petrobras")] = {**estrutura(H), "isolados": len(isolados),
                                       "isolados_quais": "; ".join(sorted(isolados))}
sem = pd.DataFrame(linhas)
sem.to_csv(PROC / "remocao_petrobras.csv")
print("1. REDE SEM A PETROBRAS (vertices que ficam isolados saem da rede)")
print(sem.drop(index="isolados_quais").to_string())
for nome in REDES:
    print(f"   isolados ({nome}):", sem.loc["isolados_quais", (nome, "sem Petrobras")])
print()


# ---------------------------------------------------------------- 2. curvas
def curva(G, ordem=None, adaptativa=False):
    H, n0 = G.copy(), G.number_of_nodes()
    S, E = [1.0], [nx.global_efficiency(G)]
    seq = list(ordem) if ordem is not None else None
    while H.number_of_nodes() > 1:
        if adaptativa:
            b = nx.betweenness_centrality(H)
            alvo = max(b, key=lambda n: (b[n], H.degree(n), n))
        else:
            alvo = seq.pop(0)
        H.remove_node(alvo)
        S.append(len(max(nx.connected_components(H), key=len)) / n0 if H.number_of_nodes() else 0)
        E.append(nx.global_efficiency(H))
    return np.array(S), np.array(E)


rng = random.Random(SEMENTE)
curvas, resumo = [], []
for nome, G in REDES.items():
    grau = sorted(G, key=lambda n: (-G.degree(n), n))
    estrategias = {"grau": curva(G, grau), "intermediacao_adaptativa": curva(G, adaptativa=True)}
    sims = [curva(G, rng.sample(list(G), G.number_of_nodes())) for _ in range(N_SIM)]
    estrategias["aleatoria"] = (np.mean([s for s, _ in sims], axis=0), np.mean([e for _, e in sims], axis=0))
    for est, (S, E) in estrategias.items():
        q = np.arange(len(S)) / G.number_of_nodes()
        curvas.append(pd.DataFrame({"rede": nome, "estrategia": est, "q": q, "S": S, "eficiencia": E}))
        meia = next((i for i, s in enumerate(S) if s <= 0.5), None)
        resumo.append({"rede": nome, "estrategia": est, "R": S[1:].mean(), "R_eficiencia": E[1:].mean(),
                       "S_apos_1": S[1], "S_apos_3": S[3], "E_apos_1": E[1], "E_apos_3": E[3],
                       "remocoes_ate_S<=0.5": meia})
    print(f"   [{nome}] ordem por grau: {', '.join(grau[:6])}")
pd.concat(curvas).to_csv(PROC / "remocao_curvas.csv", index=False)
print("2. ROBUSTEZ (R = media do maior componente relativo ao longo da remocao)")
print(pd.DataFrame(resumo).to_string(index=False), "\n")

# ---------------------------------------------------------------- 3. contrafactual
c = COMP["atual"]
pref = pd.read_csv(RAW / "preferencia_petrobras.csv")
faltam = set(pref.area) - set(c.area)
assert not faltam, f"areas da lista fora da carteira offshore: {faltam}"
LISTAS = {"estrito": pref[pref.entrada_petrobras == "so_preferencia"].area,
          "amplo": pref[pref.preferencia_exercida == "sim"].area}
pb = c[c.grupo == "Petrobras"]
cenarios = {"observada": c}
print("3. CONTRAFACTUAL DO DIREITO DE PREFERENCIA (a Petrobras sai dos contratos; os socios ficam)")
for nome, areas in LISTAS.items():
    alvo = pb[pb.area.isin(areas)]
    socios = c[c.contrato.isin(alvo.contrato)].groupby("contrato").grupo.nunique()
    print(f"   {nome}: {len(alvo)} contratos, {(socios > 1).sum()} com socios: "
          + ", ".join(f"{a} ({p:g}%)" for a, p in zip(alvo.area, alvo.participacao)))
    cenarios[nome] = c[~(c.contrato.isin(alvo.contrato) & (c.grupo == "Petrobras"))]
cf = {}
for nome, comp in cenarios.items():
    ar = arestas(comp)
    G = grafo(ar)
    pb = ar[(ar.u == "Petrobras") | (ar.v == "Petrobras")]
    cf[nome] = {**estrutura(G), "grau_Petrobras": nx.degree_centrality(G).get("Petrobras", 0),
                "intermediacao_Petrobras": nx.betweenness_centrality(G).get("Petrobras", 0),
                "forca_Petrobras": int(pb.peso.sum()), "%peso_Petrobras": 100 * pb.peso.sum() / ar.peso.sum()}
cf = pd.DataFrame(cf)
cf.to_csv(PROC / "remocao_contrafactual.csv")
print(cf.round(3).to_string())
