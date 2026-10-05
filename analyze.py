"""Generate auditable tables, paired contrasts and publication figures from DentDES CSV."""
from pathlib import Path
import argparse
import json
import hashlib
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

T49 = 2.009575
POLICIES = ("S0R0", "S1R0", "S0R1", "S1R1")
STYLE = {
    "S0R0": ("#454545", "o", "-", "none"),
    "S1R0": ("#21618C", "s", "--", "none"),
    "S0R1": ("#B66A18", "^", ":", "#B66A18"),
    "S1R1": ("#21618C", "D", "-.", "#21618C"),
}


def stats(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) != 50:
        raise ValueError("This locked analysis expects 50 nonmissing replication values")
    mean, sd = float(a.mean()), float(a.std(ddof=1))
    h = T49 * sd / math.sqrt(len(a))
    return dict(n=len(a), mean=mean, sd=sd, ci_low=mean-h, ci_high=mean+h)


def analyze(root: Path):
    x = pd.read_csv(root / "replication_results.csv")
    assert len(x)==2400
    assert not x.duplicated(["demand","kits","policy","replication"]).any()
    metrics = [c for c in x.select_dtypes("number") if c not in ("demand","kits","s","r","replication")]
    summaries, contrasts = [], []
    for (demand,kits,policy), g in x.groupby(["demand","kits","policy"]):
        for metric in metrics:
            summaries.append(dict(demand=demand,kits=kits,policy=policy,metric=metric,**stats(g[metric])))
    for (demand,kits), g in x.groupby(["demand","kits"]):
        for metric in metrics:
            p = g.pivot(index="replication",columns="policy",values=metric)
            effects = {
                "S1R0-S0R0": p.S1R0-p.S0R0,
                "S0R1-S0R0": p.S0R1-p.S0R0,
                "S1R1-S0R0": p.S1R1-p.S0R0,
                "S_main": ((p.S1R0-p.S0R0)+(p.S1R1-p.S0R1))/2,
                "R_main": ((p.S0R1-p.S0R0)+(p.S1R1-p.S1R0))/2,
                "SxR": p.S1R1-p.S1R0-p.S0R1+p.S0R0,
            }
            for effect,v in effects.items():
                contrasts.append(dict(demand=demand,kits=kits,contrast=effect,metric=metric,**stats(v)))
    summary, effects = pd.DataFrame(summaries),pd.DataFrame(contrasts)
    summary.to_csv(root / "summary.csv",index=False)
    effects.to_csv(root / "paired_effects.csv",index=False)
    figdir = root.parent / "figures"
    figdir.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":8,
                         "axes.spines.top":False,"axes.spines.right":False,
                         "axes.labelcolor":"#252525","text.color":"#252525",
                         "pdf.fonttype":42,"ps.fonttype":42,"axes.linewidth":.65})
    # Contract: ordered demand sweep, not a temporal trend; 48 estimates with CIs.
    fig,axs = plt.subplots(1,3,figsize=(7.1,2.55),sharey=True)
    for ax,kits in zip(axs,(1,2,4)):
        for policy in POLICIES:
            g = summary.query("kits==@kits and policy==@policy and metric=='mean_wait'").sort_values("demand")
            color,marker,line,fill = STYLE[policy]
            ax.errorbar(g.demand,g["mean"],yerr=g["ci_high"]-g["mean"],
                        color=color,marker=marker,linestyle=line,markerfacecolor=fill,
                        markersize=6 if policy in ("S0R0","S0R1") else 3,
                        linewidth=1,capsize=2,label=policy)
        ax.set_title(f"{kits} kit{'s' if kits>1 else ''} per class",fontsize=9)
        ax.set_xticks([.8,1.,1.2,1.5])
        ax.set_xlabel("Demand multiplier")
        ax.grid(axis="y",color="#dedede",linewidth=.5)
        ax.set_ylim(bottom=0)
    axs[0].set_ylabel("Mean patient wait (min)")
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="lower center",ncol=4,frameon=False,bbox_to_anchor=(.52,-.02))
    fig.suptitle("Patient waiting across demand and kit capacity",fontsize=10,y=1.04)
    fig.text(.5,.94,"50 paired replications per policy; bars show marginal 95% confidence intervals",ha="center",fontsize=7)
    fig.tight_layout(rect=(0,.12,1,.91))
    for ext in ("pdf","png"):
        fig.savefig(figdir/f"demand_robustness.{ext}",dpi=240,bbox_inches="tight")
    plt.close(fig)
    # Contract: paired differences in minutes, 12 conditions x 2 outcomes; zero reference.
    fig,axs=plt.subplots(1,2,figsize=(7.1,3.25),sharey=True)
    condition_labels=[]
    selected=effects.query("contrast=='S1R1-S0R0'")
    for ax,metric,label in zip(axs,("mean_wait","overtime"),("Mean patient wait","Patient-discharge overtime")):
        g=selected.query("metric==@metric").sort_values(["kits","demand"])
        positions=np.arange(len(g))
        ax.errorbar(g["mean"],positions,xerr=g.ci_high-g["mean"],fmt="o",color="#21618C",capsize=2,markersize=3)
        ax.axvline(0,color="#454545",linewidth=.8)
        ax.set_title(label,fontsize=9)
        ax.set_xlabel("Combined policy minus baseline (min)")
        ax.grid(axis="x",color="#dedede",linewidth=.5)
        condition_labels=[f"{int(row.kits)} kit/class; {row.demand:.1f}×" for row in g.itertuples()]
    axs[0].set_yticks(np.arange(12),condition_labels,fontsize=7)
    axs[0].invert_yaxis()
    fig.suptitle("Paired changes in waiting and overtime",fontsize=10,y=1.02)
    fig.text(.5,.95,"S1R1 − S0R0; 50 paired replications; marginal 95% confidence intervals",ha="center",fontsize=7)
    fig.tight_layout(rect=(0,0,1,.91))
    for ext in ("pdf","png"):
        fig.savefig(figdir/f"paired_effects.{ext}",dpi=240,bbox_inches="tight")
    plt.close(fig)
    # Contract: model schematic, exact processes and resource dependencies; monochrome.
    fig,ax=plt.subplots(figsize=(7.1,1.95))
    ax.set(xlim=(-.2,10),ylim=(-.5,3)); ax.axis("off")
    nodes={"arrival":(.8,2.1,"Arrival +\nregistration"),"queue":(2.8,2.1,"Registered\npatient queue"),
           "care":(5.1,2.1,"Atomic dispatch\nTreatment + documentation"),
           "out":(8.1,2.1,"Checkout +\ndischarge"),
           "chair":(6.,.55,"Assistant:\nchair cleaning"),"kit":(8.25,.55,"Assistant: kit prep\nSterilizer: batch cycle"),
           "ready":(2.3,.55,"Clean kit + chair\nDentist + assistant")}
    for key,(cx,cy,label) in nodes.items():
        width=2.2 if key in ("care","kit") else 1.55
        ax.add_patch(FancyBboxPatch((cx-width/2,cy-.34),width,.68,boxstyle="round,pad=.04,rounding_size=.04",facecolor="white",edgecolor="#454545",linewidth=.8))
        ax.text(cx,cy,label,ha="center",va="center",fontsize=7)
    def arrow(xy1,xy2):
        ax.annotate("",xy=xy2,xytext=xy1,arrowprops=dict(arrowstyle="->",color="#454545",lw=.8))
    arrow((1.6,2.1),(1.97,2.1)); arrow((3.62,2.1),(3.96,2.1))
    arrow((6.24,2.1),(7.27,2.1));arrow((5.2,1.72),(5.6,.95))
    arrow((6.82,.55),(7.1,.55));arrow((2.7,.95),(4.1,1.73))
    arrow((5.15,.55),(3.15,.55))
    ax.text(4.15,.72,"chair ready",ha="center",fontsize=6)
    ax.plot([8.25,8.25,2.3],[.15,-.15,-.15],color="#454545",lw=.8)
    arrow((2.3,-.15),(2.3,.17))
    ax.text(5.2,-.38,"Clean chairs and reprocessed kits return independently",ha="center",fontsize=7)
    ax.text(4.7,2.78,"Patient flow and resource return",ha="center",fontsize=10)
    fig.tight_layout(pad=.2)
    for ext in ("pdf","png"):
        fig.savefig(figdir/f"model_flow.{ext}",dpi=240,bbox_inches="tight")
    plt.close(fig)
    # Generated LaTeX tables prevent manual transcription errors.
    texdir=root.parent/"generated";texdir.mkdir(exist_ok=True)
    def lookup(kits,demand,policy,metric):
        return summary.query("kits==@kits and demand==@demand and policy==@policy and metric==@metric").iloc[0]
    lines=[]
    for policy in POLICIES:
        cells=[policy]
        for metric in ("mean_wait","p90_wait","overtime","completed_by_close"):
            row=lookup(2,1.,policy,metric)
            cells.append(f"{row['mean']:.2f} ({row.sd:.2f})")
        lines.append(" & ".join(cells)+r" \\")
    (texdir/"reference_rows.tex").write_text("\n".join(lines)+"\n")
    (texdir/"reference_table.tex").write_text(
        "\\begin{tabular}{@{}lrrrr@{}}\n\\toprule\n"
        "Policy & Mean waiting (min) & Daily P90 waiting (min) & Discharge overtime (min) & Completions by minute 480 \\\\\n"
        "\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")
    lines=[]
    for kits in (1,2,4):
        for demand in (.8,1.,1.2,1.5):
            cells=[str(kits),f"{demand:.1f}"]
            for metric in ("mean_wait","overtime"):
                row=effects.query("kits==@kits and demand==@demand and metric==@metric and contrast=='S1R1-S0R0'").iloc[0]
                cells.append(f"{row['mean']:+.2f} [{row.ci_low:+.2f}, {row.ci_high:+.2f}]")
            lines.append(" & ".join(cells)+r" \\")
    (texdir/"robustness_rows.tex").write_text("\n".join(lines)+"\n")
    reference=effects.query("kits==2 and demand==1 and metric in ['mean_wait','overtime']")
    (root/"analysis_manifest.json").write_text(json.dumps(dict(
        replication_csv_sha256=hashlib.sha256((root/"replication_results.csv").read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ci="paired replication t, df=49, critical=2.009575; marginal not multiplicity adjusted"),indent=2))
    print(summary.query("kits==2 and demand==1 and metric in ['mean_wait','p90_wait','overtime','completed_by_close']")[["policy","metric","mean","sd","ci_low","ci_high"]].round(4).to_string(index=False))
    print(reference[["contrast","metric","mean","ci_low","ci_high"]].round(4).to_string(index=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--results",type=Path,default=Path(__file__).parent/"results")
    analyze(parser.parse_args().results)
