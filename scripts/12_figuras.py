"""Figuras do main_novo.tex (mar, grupo atual). Saidas em figures/:
  fig1_rede_atual.png       grafo simples da rede atual, vertice proporcional a intermediacao
  fig2_nucleo_ponderado.png 4-core da rede atual, espessura da aresta proporcional ao peso
  fig3_antes_depois.png     uniao das redes no arremate e atual: arestas mantidas, perdidas, criadas
  fig4_robustez.png         curvas de robustez (remocao_curvas.csv, de 11_remocao.py)
Cores: tres primeiras posicoes da paleta categorica validada (azul, laranja, verde-agua), com
tipo de linha como segunda codificacao.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from matplotlib.lines import Line2D

from redes_mar import PROC, RAIZ, arestas, arremate, atual, grafo

FIG = RAIZ / "figures"
FIG.mkdir(exist_ok=True)
AZUL, LARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA2, CINZA, FUNDO = "#0b0b0b", "#52514e", "#b9b8b3", "#ffffff"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": TINTA2,
                     "axes.labelcolor": TINTA, "xtick.color": TINTA2, "ytick.color": TINTA2,
                     "savefig.dpi": 300, "savefig.facecolor": FUNDO})

CURTO = {"Coplex Petróleo do Brasil Ltda.": "Coplex", "Petroserv S/A": "Petroserv",
         "Starfish Oil & Gás S/A": "Starfish", "BS-3 S/A": "BS-3", "Westlawn Energia": "Westlawn",
         "Panoro Energy": "Panoro", "Brava Energia": "Brava", "TotalEnergies": "Total",
         "QatarEnergy": "Qatar", "ExxonMobil": "Exxon", "Pacific Brasil": "Pacific",
         "Premier Oil": "Premier"}


def nome(n):
    return CURTO.get(n, n)


G_fim, G_ini = grafo(arestas(atual())), grafo(arestas(arremate("hoje")))
U = nx.compose(G_ini, G_fim)


def layout(G, semente=7):
    # componentes pequenos ao lado do principal
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    pos = nx.spring_layout(G.subgraph(comps[0]), k=1.6 / len(comps[0]) ** 0.5, iterations=800,
                           seed=semente, weight=None)
    x0 = max(x for x, _ in pos.values()) + 0.25
    y0 = min(y for _, y in pos.values())
    for i, c in enumerate(comps[1:]):
        for j, n in enumerate(sorted(c)):
            pos[n] = (x0, y0 + 0.3 * i + 0.18 * j)
    return pos


def rotulos(ax, pos, nos, dy=0.04, fs=7):
    for n in nos:
        x, y = pos[n]
        ax.text(x, y + dy, nome(n), ha="center", va="bottom", fontsize=fs, color=TINTA,
                bbox=dict(boxstyle="round,pad=0.1", fc=FUNDO, ec="none", alpha=0.8))


# ---------------------------------------------------------------- fig 1
b = nx.betweenness_centrality(G_fim)
pos = layout(G_fim)
fig, ax = plt.subplots(figsize=(7, 5.6))
nx.draw_networkx_edges(G_fim, pos, ax=ax, edge_color=CINZA, width=0.8)
nx.draw_networkx_nodes(G_fim, pos, ax=ax, node_color=AZUL, edgecolors=FUNDO, linewidths=1.5,
                       node_size=[40 + 1600 * b[n] for n in G_fim])
rotulos(ax, pos, list(G_fim))
ax.axis("off")
fig.tight_layout()
fig.savefig(FIG / "fig1_rede_atual.png")
plt.close(fig)

# ---------------------------------------------------------------- fig 2
core = nx.k_core(G_fim, 4)
w = nx.get_edge_attributes(core, "weight")
fig, ax = plt.subplots(figsize=(6.5, 5))
pc = nx.kamada_kawai_layout(core)
nx.draw_networkx_edges(core, pc, ax=ax, edge_color=TINTA2, alpha=0.7,
                       width=[0.6 + 0.18 * w[e] for e in core.edges])
nx.draw_networkx_nodes(core, pc, ax=ax, node_color=AZUL, edgecolors=FUNDO, linewidths=1.5,
                       node_size=[60 + 6 * core.degree(n, weight="weight") for n in core])
for n, (x, y) in pc.items():
    ax.text(x, y + 0.08, nome(n), ha="center", va="bottom", fontsize=8, color=TINTA,
            bbox=dict(boxstyle="round,pad=0.1", fc=FUNDO, ec="none", alpha=0.8))
for (u, v), peso in w.items():
    if peso >= 10:
        (x1, y1), (x2, y2) = pc[u], pc[v]
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, str(peso), fontsize=7, color=TINTA2, ha="center",
                va="center", bbox=dict(boxstyle="round,pad=0.15", fc=FUNDO, ec="none"))
ax.axis("off")
fig.tight_layout()
fig.savefig(FIG / "fig2_nucleo_ponderado.png")
plt.close(fig)

# ---------------------------------------------------------------- fig 3
e_ini, e_fim = set(map(frozenset, G_ini.edges)), set(map(frozenset, G_fim.edges))
tipos = {"Kept": (e_ini & e_fim, AZUL, "solid"), "Lost": (e_ini - e_fim, LARANJA, "dashed"),
         "Created": (e_fim - e_ini, AQUA, "solid")}
pos = layout(U, semente=3)
fig, ax = plt.subplots(figsize=(7.5, 6.5))
for tipo, (es, cor, estilo) in tipos.items():
    nx.draw_networkx_edges(U, pos, ax=ax, edgelist=[tuple(e) for e in es], edge_color=cor, style=estilo,
                           width=1.6 if tipo != "Kept" else 1.0)
so_ini, so_fim = set(G_ini) - set(G_fim), set(G_fim) - set(G_ini)
cor_no = [LARANJA if n in so_ini else AQUA if n in so_fim else TINTA2 for n in U]
nx.draw_networkx_nodes(U, pos, ax=ax, node_color=cor_no, edgecolors=FUNDO, linewidths=1.5, node_size=70)
rotulos(ax, pos, list(U), dy=0.03, fs=6.5)
ax.legend(handles=[Line2D([], [], color=AZUL, lw=1.4, label=f"Kept ({len(tipos['Kept'][0])})"),
                   Line2D([], [], color=LARANJA, lw=1.6, ls="--", label=f"Lost ({len(tipos['Lost'][0])})"),
                   Line2D([], [], color=AQUA, lw=1.6, label=f"Created ({len(tipos['Created'][0])})"),
                   Line2D([], [], marker="o", ls="", color=LARANJA, label="Group only at award"),
                   Line2D([], [], marker="o", ls="", color=AQUA, label="Group only today")],
          loc="lower left", frameon=False, fontsize=8)
ax.axis("off")
fig.tight_layout()
fig.savefig(FIG / "fig3_antes_depois.png")
plt.close(fig)

# ---------------------------------------------------------------- fig 4
cv = pd.read_csv(PROC / "remocao_curvas.csv")
EST = {"grau": ("By initial degree", AZUL, "solid"),
       "intermediacao_adaptativa": ("By recalculated betweenness", LARANJA, "dashed"),
       "aleatoria": ("Random (mean of 500)", AQUA, "dotted")}
fig, axs = plt.subplots(1, 2, figsize=(7.5, 3.2), sharey=True)
for ax, (rede, titulo) in zip(axs, (("arremate", "Award network"), ("atual", "Current network"))):
    for est, (rot, cor, estilo) in EST.items():
        d = cv[(cv.rede == rede) & (cv.estrategia == est)]
        ax.plot(d.q, d.S, color=cor, ls=estilo, lw=2, label=rot)
    ax.set_title(titulo, fontsize=9, color=TINTA, loc="left")
    ax.set_xlabel("Fraction of groups removed")
    ax.grid(axis="y", color="#e6e5e1", lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
axs[0].set_ylabel("Largest component / initial groups")
axs[1].legend(frameon=False, fontsize=8, loc="upper right")
fig.tight_layout()
fig.savefig(FIG / "fig4_robustez.png")
plt.close(fig)
print("figuras em", FIG)
