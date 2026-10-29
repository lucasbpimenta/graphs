"""Grafo dirigido operadora -> nao operadora: a operadora como canal de transferencia de know-how.

Em cada contrato (ou bloco arrematado) com uma unica operadora, um arco sai da operadora para cada
outro grupo do consorcio; peso = numero de contratos. O arco e um canal potencial de transferencia
(a operadora conduz as operacoes pelo JOA), nao uma transferencia observada.

Redes (mar, grupo economico):
  atual      carteira vigente, grupo atual
  arremate   mesmos contratos na adjudicacao, grupo atual
  historico  todos os blocos arrematados no mar em R1-R17 (ofertas_vencedoras, grupo no ano do
             leilao), mais OPC e partilha na adjudicacao (grupo no ano do leilao)

  1. Por grupo: grau e forca de saida (para quantos parceiros opera) e de entrada (sob quantas
     operadoras participa), fracao como operadora, PageRank no grafo invertido (nao operadora ->
     operadora: operadoras escolhidas por parceiros bem conectados).
  2. Reciprocidade: pares em que cada um ja operou para o outro.
  3. Trajetoria na rede historica: grupos que entraram no mar como nao operadores em consorcio e
     depois passaram a operar consorcios (qualquer lamina: R1-R4 nao tem lamina classificada);
     com quais operadoras estiveram antes; se operam consorcios hoje. A Petrobras fica de fora
     (operadora incumbente desde a Rodada Zero).
Saidas em data/processed: dirigido_<rede>.csv (arcos), dirigido_papeis.csv, dirigido_trajetorias.csv
"""
import networkx as nx
import pandas as pd

from redes_mar import PROC, CAMADA, arremate, atual

pd.set_option("display.width", 250, "display.max_columns", 20, "display.precision", 3)


def eventos_historicos():
    """Unidade arrematada no mar x grupo, com ano, papel e lamina."""
    of = pd.read_csv(PROC / "ofertas_vencedoras.csv")
    of = of[of.ambiente == "Mar"].assign(unidade=lambda d: "R" + d.rodada.astype(str) + "|" + d.bloco,
                                         camada="concessao")
    of = of.groupby(["unidade", "grupo"], as_index=False).agg(
        operador=("operador", "max"), ano=("ano_leilao", "first"), lamina=("lamina", "first"),
        camada=("camada", "first"))
    ad = arremate("leilao")
    ad = ad[ad.camada.isin(["OPC", "partilha"])].rename(columns={"contrato": "unidade", "ano_leilao": "ano"})
    return pd.concat([of, ad[["unidade", "grupo", "operador", "ano", "lamina", "camada"]]], ignore_index=True)


def arcos(comp, unidade):
    linhas = []
    for un, g in comp.groupby(unidade):
        ops = g[g.operador.astype(bool)].grupo.unique()
        if len(ops) != 1:
            continue
        for p in g.grupo.unique():
            if p != ops[0]:
                linhas.append((ops[0], p, un))
    a = pd.DataFrame(linhas, columns=["operadora", "parceira", unidade])
    return a.groupby(["operadora", "parceira"], as_index=False).agg(peso=(unidade, "nunique"))


hist = eventos_historicos()
REDES = {"atual": arcos(atual(), "contrato"), "arremate": arcos(arremate("hoje"), "contrato"),
         "historico": arcos(hist, "unidade")}

papeis = []
for nome, a in REDES.items():
    a.to_csv(PROC / f"dirigido_{nome}.csv", index=False)
    D = nx.DiGraph()
    D.add_weighted_edges_from(a.itertuples(index=False, name=None))
    pr = nx.pagerank(D.reverse(), weight="weight")
    p = pd.DataFrame({"grau_saida": dict(D.out_degree()), "grau_entrada": dict(D.in_degree()),
                      "forca_saida": dict(D.out_degree(weight="weight")),
                      "forca_entrada": dict(D.in_degree(weight="weight")), "pagerank_operadora": pr})
    p["frac_operadora"] = p.forca_saida / (p.forca_saida + p.forca_entrada)
    papeis.append(p.rename_axis("grupo").reset_index().assign(rede=nome))
    rec = [(u, v) for u, v in D.edges if u < v and D.has_edge(v, u)]
    tot = a.peso.sum()
    pb_out = a[a.operadora == "Petrobras"].peso.sum()
    print(f"[{nome}] {D.number_of_nodes()} grupos, {D.number_of_edges()} arcos, peso {tot}; "
          f"Petrobras origem de {100 * pb_out / tot:.0f}% do peso; "
          f"so operadoras: {int(((p.forca_entrada == 0) & (p.forca_saida > 0)).sum())}, "
          f"so nao operadoras: {int(((p.forca_saida == 0) & (p.forca_entrada > 0)).sum())}, "
          f"pares reciprocos: {len(rec)}")
    print("   reciprocos:", "; ".join(f"{u}<->{v}" for u, v in rec))
    print(p.sort_values("forca_saida", ascending=False).head(12).to_string(), "\n")
papeis = pd.concat(papeis)
papeis.to_csv(PROC / "dirigido_papeis.csv", index=False)

# ---------------------------------------------------------------- trajetorias
n_grupos = hist.groupby("unidade").grupo.nunique()
hist["consorcio"] = hist.unidade.map(n_grupos) > 1
opera_hoje = REDES["atual"].groupby("operadora").peso.sum()
traj = []
for g, e in hist[hist.grupo != "Petrobras"].groupby("grupo"):
    nao_op = e[~e.operador.astype(bool) & e.consorcio]
    op = e[e.operador.astype(bool) & e.consorcio]
    if nao_op.empty:
        continue
    ano_nao_op = nao_op.ano.min()
    ano_op = op.ano.min() if not op.empty else None
    antes = nao_op[nao_op.ano < ano_op] if ano_op else nao_op
    mestres = hist[hist.unidade.isin(antes.unidade) & hist.operador.astype(bool) & (hist.grupo != g)]
    traj.append({"grupo": g, "primeiro_ano_mar": e.ano.min(), "primeiro_ano_nao_operadora": ano_nao_op,
                 "primeiro_ano_operadora_consorcio": ano_op,
                 "unidades_nao_operadora": nao_op.unidade.nunique(),
                 "unidades_operadora_consorcio": op.unidade.nunique(),
                 "unidades_operadora_profunda": op[op.lamina == "profunda"].unidade.nunique(),
                 "trajetoria": ("graduou" if ano_op and ano_op > ano_nao_op else
                                "operou antes ou junto" if ano_op else "so nao operadora"),
                 "contratos_operando_parceiros_hoje": int(opera_hoje.get(g, 0)),
                 "operadoras_antes": "; ".join(f"{k} ({v})" for k, v in
                                              mestres.grupo.value_counts().items())})
traj = pd.DataFrame(traj).sort_values(["trajetoria", "primeiro_ano_nao_operadora"])
traj.to_csv(PROC / "dirigido_trajetorias.csv", index=False)
print("TRAJETORIAS (rede historica, sem a Petrobras): grupos que foram nao operadores em consorcio no mar")
print(traj.trajetoria.value_counts().to_string())
print("\nGraduados: nao operadora em consorcio antes de operar um consorcio")
print(traj[traj.trajetoria == "graduou"].drop(columns="trajetoria").to_string(index=False))
print("\nOperaram consorcio no mesmo ano ou antes de entrar como nao operadora:")
print(traj[traj.trajetoria == "operou antes ou junto"]
      [["grupo", "primeiro_ano_nao_operadora", "primeiro_ano_operadora_consorcio"]].to_string(index=False))
so = traj[traj.trajetoria == "so nao operadora"]
print(f"\nSo nao operadoras ({len(so)}); operadoras com quem estiveram, somadas:")
print(pd.Series([m.split(" (")[0] for s in so.operadoras_antes for m in s.split("; ") if m])
      .value_counts().head(8).to_string())
