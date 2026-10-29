"""Redes de consorcios por regime de origem: carteira atual x composicao na adjudicacao.

Para cada contrato vigente (participacoes_atuais.csv), a composicao na adjudicacao e, nesta ordem:
  - a composicao oficial do leilao (ofertas_vencedoras, R1-R17), se o bloco for localizado;
  - a composicao "antes" da primeira cessao aprovada, se o contrato teve cessao;
  - a composicao atual, se nunca teve cessao;
  - Petrobras 100% na Rodada Zero: os 397 contratos de 06/08/1998 foram assinados so com a
    Petrobras (ANP; Anuario ANP 2001). As parcerias de out/1998-dez/1999 (23, segundo o BNDES,
    Informe Infra-Estrutura 41) sao posteriores e o arquivo de cessoes so comeca em 2001.

Saidas em data/processed:
  composicao_adjudicacao.csv   contrato x empresa na adjudicacao, com a fonte da reconstrucao
  arestas_atual.csv            par de empresas x regime, numero de contratos em comum hoje
  arestas_adjudicacao.csv      idem, na adjudicacao
  arestas_leilao_historico.csv par de empresas x rodada, blocos arrematados juntos em R1-R17
                               (inclui blocos ja devolvidos)
  arestas_*_grupo.csv          idem, entre grupos economicos: grupo atual na rede atual, grupo no
                               ano do leilao nas redes de adjudicacao e historica
  arestas_*_mar.csv            recorte offshore (contratos e blocos no mar) de cada arquivo acima
"""
import re
from itertools import combinations
from pathlib import Path

import networkx as nx
import pandas as pd

from empresas import grupo

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"

atual = pd.read_csv(PROC / "participacoes_atuais.csv", dtype={"chave": str})
cess = pd.read_csv(PROC / "cessoes.csv", dtype={"chave": str}, parse_dates=["data_aprovacao"])
ofertas = pd.read_csv(PROC / "ofertas_vencedoras.csv")
contratos = atual.drop_duplicates("contrato")[["contrato", "chave", "bid", "regime", "ano_leilao", "area",
                                                "ambiente", "lamina"]]


def nome_bloco(s):
    """'BM-S-9A' / 'FZA-M-539_R11' / ' bt-pot-10 ' -> forma comparavel."""
    return re.sub(r"_(R\d+|OPP?\d|EXC|AM\d?)$", "", str(s).strip().upper()).replace(" ", "")


def consolida(comp):
    # a mesma empresa pode aparecer com duas grafias que viraram um so nome canonico
    return comp.groupby("empresa", as_index=False).agg(participacao=("participacao", "sum"),
                                                       operador=("operador", "max"))


# ---------------------------------------------------------------- composicao na adjudicacao
# Primeira cessao de cada contrato: menor data de aprovacao; empate (ou data ausente) pela ordem do arquivo.
primeira = (cess[cess.situacao == "antes"]
            .sort_values(["data_aprovacao", "registro"], na_position="last")
            .drop_duplicates("chave")[["chave", "registro"]])
antes = cess[cess.situacao == "antes"].merge(primeira, on=["chave", "registro"])

# Nomes de bloco de cada contrato: o da carteira atual e os que aparecem nas cessoes do mesmo contrato
# (o bloco pode ter virado campo e mudado de nome).
nomes = (pd.concat([contratos[["chave", "area"]], cess[["chave", "area"]]]).dropna()
         .assign(bloco=lambda d: d.area.map(nome_bloco)).groupby("chave").bloco.agg(set))
ofertas["bloco_n"] = ofertas.bloco.map(nome_bloco)
oficial = {k: g for k, g in ofertas.groupby(["rodada", "bloco_n"])}

linhas, validacao = [], []
for c in contratos.itertuples():
    if c.bid == "BID0":
        linhas.append({"contrato": c.contrato, "empresa": "Petrobras", "participacao": 100.0,
                       "operador": True, "fonte": "rodada_zero", "bloco_leilao": None})
        continue
    comp, fonte = antes[antes.chave == c.chave], "cessao_antes"
    if comp.empty:
        comp, fonte = atual[atual.contrato == c.contrato], "atual_sem_cessao"
    comp, bloco = consolida(comp), None
    m = re.fullmatch(r"BID(\d+)", c.bid)
    if m:
        # contratos desmembrados (BM-S-9A, BT-POT-10B) herdam a composicao do bloco de origem
        cand = nomes.get(c.chave, set())
        cand = cand | {re.sub(r"(?<=\d)[A-Z]$", "", b) for b in cand}
        achados = sorted(b for b in cand if (int(m.group(1)), b) in oficial)
        if achados:
            bloco = achados[0]
            of = consolida(oficial[(int(m.group(1)), bloco)])
            validacao.append({"contrato": c.contrato, "rodada": int(m.group(1)), "fonte_rec": fonte,
                              "mesmas_empresas": set(of.empresa) == set(comp.empresa),
                              "identica": sorted(zip(of.empresa, of.participacao.round())) ==
                                          sorted(zip(comp.empresa, comp.participacao.round()))})
            comp, fonte = of, "leilao_oficial"
    for e in comp.itertuples():
        linhas.append({"contrato": c.contrato, "empresa": e.empresa, "participacao": e.participacao,
                       "operador": bool(e.operador), "fonte": fonte, "bloco_leilao": bloco})
adj = pd.DataFrame(linhas).merge(contratos, on="contrato")
# grupo economico no ano do leilao (sem ano conhecido: situacao atual)
adj["grupo"] = [grupo(e, None if pd.isna(a) else int(a)) for e, a in zip(adj.empresa, adj.ano_leilao)]
validacao = pd.DataFrame(validacao)


# ---------------------------------------------------------------- arestas
def arestas(part, nivel, unidade="contrato", rotulo="regime"):
    """Pares de `nivel` (empresa ou grupo) que dividem uma unidade; empresas do mesmo grupo
    num mesmo contrato nao geram aresta no nivel de grupo."""
    pares = []
    for (un, rot), g in part.groupby([unidade, rotulo]):
        for u, v in combinations(sorted(set(g[nivel])), 2):
            pares.append((u, v, rot, un))
    df = pd.DataFrame(pares, columns=["u", "v", rotulo, unidade])
    return df.groupby(["u", "v", rotulo], as_index=False).agg(peso=(unidade, "nunique"))


ofertas["rb"] = ofertas.rodada.astype(str) + "|" + ofertas.bloco_n
adj.to_csv(PROC / "composicao_adjudicacao.csv", index=False)
ARESTAS = {}
for recorte, suf_r in (("total", ""), ("mar", "_mar")):
    filtra = (lambda d: d) if recorte == "total" else (lambda d: d[d.ambiente == "Mar"])
    for nivel, suf_n in (("empresa", ""), ("grupo", "_grupo")):
        ARESTAS[(recorte, nivel)] = (arestas(filtra(atual), nivel), arestas(filtra(adj), nivel),
                                     arestas(filtra(ofertas), nivel, unidade="rb", rotulo="rodada"))
        for nome, ar in zip(("atual", "adjudicacao", "leilao_historico"), ARESTAS[(recorte, nivel)]):
            ar.to_csv(PROC / f"arestas_{nome}{suf_n}{suf_r}.csv", index=False)
ar_atual, ar_adj, ar_hist = ARESTAS[("total", "empresa")]


# ---------------------------------------------------------------- resumo por regime
def resumo(part, ar):
    por_contrato = part.groupby(["contrato", "regime"]).empresa.nunique().reset_index()
    r = por_contrato.groupby("regime").agg(contratos=("contrato", "size"),
                                            consorcios=("empresa", lambda s: (s > 1).sum()))
    r["empresas"] = part.groupby("regime").empresa.nunique()
    r["pares"] = ar.groupby("regime").size()
    r["peso_total"] = ar.groupby("regime").peso.sum()
    pb = ar[(ar.u == "Petrobras") | (ar.v == "Petrobras")].groupby("regime").peso.sum()
    r["%peso_c_Petrobras"] = (100 * pb / r["peso_total"]).round(1)
    return r.fillna(0).astype({"pares": int, "peso_total": int})


pd.set_option("display.width", 250, "display.max_columns", 20)
print("Validacao da reconstrucao por cessoes contra o leilao oficial (contratos R1-R17 localizados):")
validacao["periodo"] = pd.cut(validacao.rodada, [0, 4, 8, 17], labels=["R1-R4 (1999-2002)", "R5-R7 (2003-05)",
                                                                       "R9-R17 (2007-21)"])
print(validacao.groupby(["periodo", "fonte_rec"], observed=True)[["mesmas_empresas", "identica"]]
      .agg(["sum", "size"]), "\n")
r1_17 = adj[adj.bid.str.fullmatch(r"BID[1-9]\d*")].drop_duplicates("contrato")
print(f"Contratos R1-R17 vigentes sem bloco localizado no leilao: "
      f"{(r1_17.fonte != 'leilao_oficial').sum()} de {len(r1_17)}\n")

por_bloco = ofertas.groupby(["rodada", "bloco_n"]).agg(n=("empresa", "nunique"),
                                                       pb=("empresa", lambda s: "Petrobras" in set(s)))
hist = por_bloco.groupby("rodada").agg(blocos=("n", "size"), consorcios=("n", lambda s: (s > 1).sum()),
                                       com_Petrobras=("pb", "sum"))
hist["%consorcio"] = (100 * hist.consorcios / hist.blocos).round(0)
hist["empresas"] = ofertas.groupby("rodada").empresa.nunique()
hist["pares"] = ar_hist.groupby("rodada").size()
print("LEILOES R1-R17 (todos os blocos arrematados):")
print(hist.fillna(0).astype(int).T, "\n")

print("Fonte da composicao na adjudicacao (contratos):")
print(adj.drop_duplicates("contrato").groupby(["regime", "fonte"]).size().unstack(fill_value=0), "\n")
print("REDE ATUAL por regime de origem:")
print(resumo(atual, ar_atual), "\n")
print("REDE NA ADJUDICACAO por regime de origem:")
print(resumo(adj, ar_adj), "\n")

for nome, ar in (("atual", ar_atual), ("adjudicacao", ar_adj)):
    tot = ar.groupby(["u", "v"]).peso.sum()
    G = nx.Graph()
    G.add_weighted_edges_from((u, v, w) for (u, v), w in tot.items())
    print(f"[{nome}] {G.number_of_nodes()} nos com aresta, {G.number_of_edges()} arestas, "
          f"peso total {int(tot.sum())}; maiores pares:")
    top = ar.pivot_table(index=["u", "v"], columns="regime", values="peso", aggfunc="sum", fill_value=0)
    top["total"] = top.sum(axis=1)
    print(top.sort_values("total", ascending=False).head(8).loc[:, lambda d: d.sum() > 0], "\n")
