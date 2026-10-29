"""Antes e depois: rede offshore no arremate x rede atual, nos mesmos contratos.

Grupo atual dos dois lados (redes_mar.arremate("hoje")), de modo que so as cessoes de direitos
mudam a rede; aquisicoes societarias (BG -> Shell) nao contam.

  1. Metricas globais das duas redes, inclusive k-core, conectividade algebrica e raio espectral.
  2. Arestas mantidas, perdidas e criadas; Jaccard simples e ponderado (soma dos minimos / soma
     dos maximos dos pesos).
  3. Vertices que entraram ou sairam da rede; mudanca de centralidade por grupo e correlacao de
     Spearman entre os rankings (grupos presentes nas duas redes).
  4. Por camada: peso no arremate e hoje.
Saidas em data/processed: antes_depois_metricas.csv, antes_depois_arestas.csv,
antes_depois_centralidades.csv
"""
import pandas as pd
from scipy.stats import spearmanr

from redes_mar import PROC, arestas, arremate, atual, centralidades, estrutura, grafo

pd.set_option("display.width", 250, "display.max_columns", 30, "display.precision", 3)
ar_ini, ar_fim = arestas(arremate("hoje")), arestas(atual())
G_ini, G_fim = grafo(ar_ini), grafo(ar_fim)

# ---------------------------------------------------------------- 1. metricas globais
met = pd.DataFrame({"arremate": estrutura(G_ini), "atual": estrutura(G_fim)})
met.to_csv(PROC / "antes_depois_metricas.csv")
print("1. METRICAS GLOBAIS (mar, grupo atual)")
print(met.round(3), "\n")

# ---------------------------------------------------------------- 2. arestas
p_ini = ar_ini.groupby(["u", "v"]).peso.sum().rename("arremate")
p_fim = ar_fim.groupby(["u", "v"]).peso.sum().rename("atual")
ed = pd.concat([p_ini, p_fim], axis=1).fillna(0).astype(int)
ed["situacao"] = "mantida"
ed.loc[ed.atual == 0, "situacao"] = "perdida"
ed.loc[ed.arremate == 0, "situacao"] = "criada"
ed["variacao"] = ed.atual - ed.arremate
ed.to_csv(PROC / "antes_depois_arestas.csv")
n = ed.situacao.value_counts()
print("2. ARESTAS")
print(n.to_string())
print(f"Jaccard simples {n.get('mantida', 0) / len(ed):.3f}; "
      f"Jaccard ponderado {ed[['arremate', 'atual']].min(axis=1).sum() / ed[['arremate', 'atual']].max(axis=1).sum():.3f}")
print("Peso:", ed.groupby("situacao")[["arremate", "atual"]].sum().to_dict("index"))
pb = ed.reset_index()
pb = pb[(pb.u == "Petrobras") | (pb.v == "Petrobras")]
print("Arestas da Petrobras:", pb.situacao.value_counts().to_dict(),
      f"peso {pb.arremate.sum()} -> {pb.atual.sum()}")
print("Peso fora da Petrobras:", ed.arremate.sum() - pb.arremate.sum(), "->", ed.atual.sum() - pb.atual.sum())
for s in ("perdida", "criada"):
    print(f"\n{s}s (maiores pesos):")
    print(ed[ed.situacao == s].sort_values(["arremate", "atual"], ascending=False).head(12).to_string())
print("\nmantidas com maior variacao de peso:")
m = ed[ed.situacao == "mantida"]
print(m.reindex(m.variacao.abs().sort_values(ascending=False).index).head(10).to_string(), "\n")

# ---------------------------------------------------------------- 3. vertices e centralidades
c_ini, c_fim = centralidades(G_ini), centralidades(G_fim)
print("3. VERTICES")
print("sairam:", sorted(set(G_ini) - set(G_fim)))
print("entraram:", sorted(set(G_fim) - set(G_ini)))
cc = c_ini.join(c_fim, how="outer", lsuffix="_arremate", rsuffix="_atual").fillna(0)
cc.to_csv(PROC / "antes_depois_centralidades.csv")
ambos = sorted(set(G_ini) & set(G_fim))
print(f"\nSpearman entre arremate e atual ({len(ambos)} grupos presentes nas duas redes):")
for m_ in ("grau", "intermediacao", "proximidade", "forca", "autovetor", "pagerank", "coreness"):
    r, p = spearmanr(c_ini.loc[ambos, m_], c_fim.loc[ambos, m_])
    print(f"  {m_:14s} rho = {r:.3f} (p = {p:.3g})")
cols = ["grau", "intermediacao", "forca", "autovetor", "coreness"]
top = cc.assign(soma=cc.forca_arremate + cc.forca_atual).sort_values("soma", ascending=False).head(15)
print("\nCentralidades dos 15 grupos de maior forca (arremate -> atual):")
print(top[[f"{c}_{r}" for c in cols for r in ("arremate", "atual")]].to_string(), "\n")

# ---------------------------------------------------------------- 4. por camada
print("4. PESO POR CAMADA")
cam = pd.DataFrame({"arremate": ar_ini.groupby("camada").peso.sum(), "atual": ar_fim.groupby("camada").peso.sum(),
                    "pares_arremate": ar_ini.groupby("camada").size(), "pares_atual": ar_fim.groupby("camada").size()})
print(cam.fillna(0).astype(int).to_string())
