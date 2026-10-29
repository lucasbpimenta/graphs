"""Metricas de rede e centralidades nas tres redes de consorcios.

Redes (projecao empresa x empresa; so empresas com ao menos uma parceria, como no artigo):
  atual        contratos vigentes, composicao atual          (arestas_atual.csv)
  adjudicacao  os mesmos contratos, composicao no arremate   (arestas_adjudicacao.csv)
  historico    blocos arrematados em R1-R17, inclusive devolvidos (arestas_leilao_historico.csv)

Grafo simples: grau, intermediacao e proximidade. Grafo ponderado (peso = contratos ou blocos em
comum): forca, autovetor e PageRank. Tudo nos niveis de empresa e de grupo economico
(sufixo _grupo) e nos recortes total e offshore (sufixo _mar). Saidas em data/processed:
  metricas_redes.csv                        uma coluna por (recorte, nivel, rede)
  centralidades_<rede>[_grupo][_mar].csv    uma linha por empresa ou grupo
  forca_por_regime[_grupo][_mar].csv        forca nas redes atual e de adjudicacao, por regime de origem
"""
from pathlib import Path

import networkx as nx
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"

REDES = {
    "atual": ("arestas_atual.csv", "regime"),
    "adjudicacao": ("arestas_adjudicacao.csv", "regime"),
    "historico": ("arestas_leilao_historico.csv", "rodada"),
}


def grafo(ar):
    pesos = ar.groupby(["u", "v"]).peso.sum()
    G = nx.Graph()
    G.add_weighted_edges_from((u, v, int(w)) for (u, v), w in pesos.items())
    return G


def metricas(G):
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    return {
        "vertices": G.number_of_nodes(), "arestas": G.number_of_edges(),
        "peso_total": int(G.size(weight="weight")),
        "densidade": round(nx.density(G), 4),
        "componentes": len(comps), "maior_componente": len(comps[0]),
        "%maior_componente": round(100 * len(comps[0]) / G.number_of_nodes(), 1),
        "clustering_simples": round(nx.average_clustering(G), 4),
        "clustering_ponderado": round(nx.average_clustering(G, weight="weight"), 4),
    }


def centralidades(G):
    # pesos sao intensidades (nao distancias): ficam fora de intermediacao e proximidade.
    # Autovetor so e definido sem ambiguidade num grafo conexo: calculado no maior componente,
    # 0 nos demais.
    nucleo = G.subgraph(max(nx.connected_components(G), key=len))
    autovetor = {n: abs(x) for n, x in nx.eigenvector_centrality_numpy(nucleo, weight="weight").items()}
    c = pd.DataFrame({
        "grau": nx.degree_centrality(G),
        "intermediacao": nx.betweenness_centrality(G),
        "proximidade": nx.closeness_centrality(G),
        "forca": dict(G.degree(weight="weight")),
        "autovetor": {n: autovetor.get(n, 0.0) for n in G},
        "pagerank": nx.pagerank(G, weight="weight"),
    })
    return c.sort_values("intermediacao", ascending=False).rename_axis("empresa")


NIVEIS = {"empresa": "", "grupo": "_grupo"}


def arestas(nome, suf):
    return pd.read_csv(PROC / REDES[nome][0].replace(".csv", f"{suf}.csv"))


RECORTES = {"total": "", "mar": "_mar"}

pd.set_option("display.width", 250, "display.max_columns", 20, "display.precision", 4)
resumo, cents = {}, {}
for recorte, suf_r in RECORTES.items():
    for nivel, suf_n in NIVEIS.items():
        for nome in REDES:
            G = grafo(arestas(nome, suf_n + suf_r))
            resumo[(recorte, nivel, nome)] = metricas(G)
            cents[(recorte, nivel, nome)] = centralidades(G).rename_axis(nivel)
            cents[(recorte, nivel, nome)].to_csv(PROC / f"centralidades_{nome}{suf_n}{suf_r}.csv")

resumo = pd.DataFrame(resumo)
resumo.to_csv(PROC / "metricas_redes.csv")
print("METRICAS DAS REDES, nivel grupo (versao do artigo: 43 vertices, 53 arestas, densidade 0.0587,"
      " 10 componentes, maior com 21 = 48.84%, clustering 0.3328 / 0.0245)")
print(resumo.xs("grupo", axis=1, level=1), "\n")

for nome in REDES:
    print(f"TOP 10 POR INTERMEDIACAO -- rede {nome}, nivel grupo, mar")
    print(cents[("mar", "grupo", nome)].head(10).round({"forca": 0}), "\n")

print("CORRELACAO DE SPEARMAN -- rede atual, nivel grupo, mar")
print(cents[("mar", "grupo", "atual")].corr(method="spearman").round(3), "\n")

# ---------------------------------------------------------------- forca por regime
for recorte, suf_r in RECORTES.items():
    for nivel, suf_n in NIVEIS.items():
        linhas = []
        for nome in ("atual", "adjudicacao"):
            ar = arestas(nome, suf_n + suf_r)
            for lado in ("u", "v"):
                linhas.append(ar.rename(columns={lado: nivel}).assign(rede=nome)[["rede", nivel, "regime", "peso"]])
        forca = (pd.concat(linhas).groupby(["rede", nivel, "regime"]).peso.sum()
                 .unstack("regime", fill_value=0))
        forca.insert(0, "total", forca.sum(axis=1))
        forca = forca.sort_values(["rede", "total"], ascending=[True, False])
        forca.to_csv(PROC / f"forca_por_regime{suf_n}{suf_r}.csv")
        if (recorte, nivel) == ("mar", "grupo"):
            for nome in ("atual", "adjudicacao"):
                print(f"FORCA POR REGIME DE ORIGEM -- rede {nome}, nivel grupo, mar (10 maiores)")
                print(forca.loc[nome].head(10).loc[:, lambda d: d.sum() > 0], "\n")
