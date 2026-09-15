#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VALIDACAO TEMPORARIA — mede o efeito da correcao de atribuicao.
Compara o build ANTES (logica antiga, reimplementada aqui) com o DEPOIS
(build.py atual). SOMENTE LEITURA das planilhas."""
from __future__ import annotations

import json, re, subprocess, sys, pathlib

subprocess.run([sys.executable, "build/build.py", "--template",
                "build/template.html", "--out", "dist/index.html"], check=True)

html = pathlib.Path("dist/index.html").read_text(encoding="utf-8")
m = re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
data = json.loads(m.group(1))
sales, meta = data["sales"], data["meta"]

gasto = sum(r["sp"] for r in meta)
pagas = [s for s in sales if s["meta"]]
unid = [s for s in pagas if "nao identificada" in s["camp"].replace("ã", "a").replace("ç", "c")]

print("=" * 78)
print("DEPOIS DA CORRECAO")
print("=" * 78)
print(f"  vendas totais na dash ........ {len(sales)}")
print(f"  vendas do trafego pago ....... {len(pagas)}")
print(f"    das quais sem identidade ... {len(unid)}")
print(f"  gasto ........................ R$ {gasto:,.2f}")
fat_pago = sum(s['val'] for s in pagas)
print(f"  faturamento do trafego pago .. R$ {fat_pago:,.2f}")
print(f"  CAC  (gasto / vendas pagas) .. R$ {gasto/len(pagas):,.2f}")
print(f"  ROAS (fat pago / gasto) ...... {fat_pago/gasto:,.2f}x")

antes_n = len(pagas) - len(unid)
fat_antes = sum(s["val"] for s in pagas if s not in unid)
print("\n" + "=" * 78)
print("ANTES (para comparar)")
print("=" * 78)
print(f"  vendas do trafego pago ....... {antes_n}")
print(f"  faturamento do trafego pago .. R$ {fat_antes:,.2f}")
print(f"  CAC .......................... R$ {gasto/antes_n:,.2f}")
print(f"  ROAS ......................... {fat_antes/gasto:,.2f}x")

print("\n" + "=" * 78)
print("LINHAS 'campanha nao identificada' (as que a correcao passou a contar)")
print("=" * 78)
for s in unid:
    print(f"  [{s['d']}] {s['prod']!r} R$ {s['val']:.2f}  camp={s['camp']!r}")
if not unid:
    print("  (nenhuma)")

print("\n" + "=" * 78)
print("CHECAGEM: nenhuma venda foi colada numa campanha REAL por engano?")
print("=" * 78)
camps_meta = {r["camp"] for r in meta}
suspeitas = [s for s in pagas if s["camp"] not in camps_meta and s not in unid]
if suspeitas:
    print(f"  !! {len(suspeitas)} venda(s) marcada(s) como paga com campanha fora do Meta:")
    for s in suspeitas:
        print(f"     {s['camp']!r}")
else:
    print("  OK: toda venda paga ou casa com campanha real do Meta, ou esta na")
    print("      linha '(Meta — campanha não identificada)'. Nenhuma atribuicao chutada.")
