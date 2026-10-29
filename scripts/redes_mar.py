"""Funcoes comuns aos scripts 08-11: rede offshore no nivel de grupo economico.

Composicoes (contrato x grupo, so contratos no mar):
  atual()            carteira vigente, grupo atual
  arremate(nivel)    mesmos contratos na adjudicacao (composicao_adjudicacao.csv);
                     nivel="hoje" usa o grupo atual (aquisicoes societarias, como BG -> Shell, nao
                     contam como mudanca; so as cessoes contam), nivel="leilao" o grupo no ano do leilao
Camadas: regime de origem agregado em CAMADA.
"""
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from empresas import grupo

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
RAW = RAIZ / "data" / "raw"

CAMADA = {"rodada_concessao": "concessao", "oferta_permanente_concessao": "OPC",
          "partilha_rodada": "partilha", "oferta_permanente_partilha": "partilha",
          "excedentes_cessao_onerosa": "partilha", "cessao_onerosa": "partilha",
          "rodada_zero": "rodada_zero", "outros": "outros"}
COLS = ["contrato", "grupo", "participacao", "operador", "regime", "bid", "ano_leilao", "area", "lamina"]


def _consolida(d):
    # empresas do mesmo grupo no mesmo contrato viram um so vertice
    g = d.groupby(["contrato", "grupo"], as_index=False).agg(
        participacao=("participacao", "sum"), operador=("operador", "max"),
        regime=("regime", "first"), bid=("bid", "first"), ano_leilao=("ano_leilao", "first"),
        area=("area", "first"), lamina=("lamina", "first"))
    g["camada"] = g.regime.map(CAMADA)
    return g


def atual():
    d = pd.read_csv(PROC / "participacoes_atuais.csv")
    return _consolida(d[d.ambiente == "Mar"][COLS])


def arremate(nivel="hoje"):
    d = pd.read_csv(PROC / "composicao_adjudicacao.csv")
    d = d[d.ambiente == "Mar"].copy()
    if nivel == "hoje":
        d["grupo"] = [grupo(e) for e in d.empresa]
    return _consolida(d[COLS])


def arestas(comp):
    """Par de grupos x camada, peso = contratos em comum."""
    pares = [(u, v, cam, c) for (c, cam), g in comp.groupby(["contrato", "camada"])
             for u, v in combinations(sorted(set(g.grupo)), 2)]
    df = pd.DataFrame(pares, columns=["u", "v", "camada", "contrato"])
    return df.groupby(["u", "v", "camada"], as_index=False).agg(peso=("contrato", "nunique"))


def grafo(ar):
    G = nx.Graph()
    G.add_weighted_edges_from((u, v, int(w)) for (u, v), w in ar.groupby(["u", "v"]).peso.sum().items())
    return G


def estrutura(G):
    """Metricas globais, inclusive espectrais. A conectividade algebrica e calculada no maior
    componente com o Laplaciano ponderado (padrao do networkx, weight="weight")."""
    if G.number_of_nodes() == 0:
        return {}
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    nucleo = G.subgraph(comps[0])
    A = nx.to_numpy_array(G, weight=None)
    Aw = nx.to_numpy_array(G, weight="weight")
    core = nx.core_number(G)
    kmax = max(core.values())
    return {
        "vertices": G.number_of_nodes(), "arestas": G.number_of_edges(),
        "peso_total": int(G.size(weight="weight")), "densidade": nx.density(G),
        "componentes": len(comps), "maior_componente": len(comps[0]),
        "clustering": nx.average_clustering(G), "eficiencia": nx.global_efficiency(G),
        "k_max": kmax, "nucleo_k_max": sum(1 for c in core.values() if c == kmax),
        "conectividade_algebrica": (nx.algebraic_connectivity(nucleo, method="tracemin_lu")
                                    if len(comps[0]) > 2 else np.nan),
        "raio_espectral": float(max(abs(np.linalg.eigvalsh(A)))),
        "raio_espectral_ponderado": float(max(abs(np.linalg.eigvalsh(Aw)))),
    }


def centralidades(G):
    """As mesmas medidas de 03_centralidades.py, mais coreness."""
    nucleo = G.subgraph(max(nx.connected_components(G), key=len))
    autovetor = {n: abs(x) for n, x in nx.eigenvector_centrality_numpy(nucleo, weight="weight").items()}
    return pd.DataFrame({
        "grau": nx.degree_centrality(G), "intermediacao": nx.betweenness_centrality(G),
        "proximidade": nx.closeness_centrality(G), "forca": dict(G.degree(weight="weight")),
        "autovetor": {n: autovetor.get(n, 0.0) for n in G}, "pagerank": nx.pagerank(G, weight="weight"),
        "coreness": nx.core_number(G),
    }).rename_axis("grupo")
