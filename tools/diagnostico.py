#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIAGNOSTICO TEMPORARIO — por que uma venda com UTM nao foi atribuida ao trafego.

Roda no runner (o sandbox do agente nao alcanca docs.google.com).
Mostra, para cada venda recente: as UTMs CRUAS, se casou com o Meta pelo match
EXATO de hoje, e se casaria por um match TOLERANTE a UTM quebrada. SOMENTE LEITURA.
"""
from __future__ import annotations

import csv, io, re, sys, unicodedata, urllib.request
from collections import Counter
from urllib.parse import unquote_plus

sys.path.insert(0, "build")
import config as cfg   # usa a MESMA config da dashboard

UA = {"User-Agent": "Mozilla/5.0 (compatible; dash-diag/1.0)"}
EXPORT = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"


def rows(sid, gid):
    req = urllib.request.Request(EXPORT.format(sid=sid, gid=gid), headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return list(csv.reader(io.StringIO(r.read().decode("utf-8", "replace"))))


def norm(s):
    """A normalizacao que a dashboard usa HOJE."""
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s or "").strip().lower())
                if not unicodedata.combining(c))
    return s


def loose(s):
    """Normalizacao TOLERANTE proposta: decodifica %20/+, joga fora tudo que nao
    for letra/numero. 'AUTO | H | 18 a 65 | BR | Aberto ADV' e
    'AUTO-H-18-a-65-BR-Aberto-ADV' viram a mesma coisa."""
    return re.sub(r"[^a-z0-9]+", "", norm(unquote_plus(str(s or ""))))


m = rows(cfg.SPREADSHEET_ID, cfg.GID_META)
s = rows(cfg.SPREADSHEET_ID_SALES, cfg.GID_SALES)
mh, sh = m[0], s[0]

def idx(hdr, name):
    for i, h in enumerate(hdr):
        if norm(h) == norm(name):
            return i
    return None

I_CAMP, I_ADSET, I_AD = idx(mh, "Campaign Name"), idx(mh, "Ad Set Name"), idx(mh, "Ad Name")
C = {n: idx(sh, n) for n in ("Data", "Produto", "Status", "Valor", "Faturamento",
                             "Canal", "utm_source", "utm_medium", "utm_term",
                             "utm_campaign", "utm_content")}

# mapas do Meta: exato (como hoje) e tolerante (proposto)
exato, tolerante = {}, {}
for r in m[1:]:
    if len(r) <= I_AD or not (r[I_CAMP] or "").strip():
        continue
    camp, adset, ad = r[I_CAMP].strip(), r[I_ADSET].strip(), r[I_AD].strip()
    exato.setdefault((norm(camp), norm(ad)), (camp, adset))
    tolerante.setdefault((loose(camp), loose(ad)), (camp, adset))

print(f"Meta: {len(m)-1} linhas · {len(exato)} pares (campanha, anuncio) distintos")
print(f"Vendas (aba gid {cfg.GID_SALES}): {len(s)-1} linhas\n")

def get(r, k):
    i = C[k]
    return (r[i] if i is not None and i < len(r) else "").strip()

# ---------- todas as vendas que tem QUALQUER UTM ----------
print("=" * 100)
print("VENDAS COM ALGUMA UTM PREENCHIDA — por que casou ou nao")
print("=" * 100)
ganhos, ja_ok, sem_jeito = [], [], []
for r in s[1:]:
    utms = {k: get(r, k) for k in ("utm_source", "utm_medium", "utm_term",
                                   "utm_campaign", "utm_content")}
    if not any(utms.values()):
        continue
    camp_v, ad_v = get(r, "utm_campaign"), get(r, cfg.AD_UTM_COLUMN)
    hit_e = exato.get((norm(camp_v), norm(ad_v)))
    hit_t = tolerante.get((loose(camp_v), loose(ad_v)))
    prod = get(r, "Produto")
    main = norm(prod).startswith(cfg.MAIN_PRODUCT_PREFIX)
    estado = "CASA HOJE" if hit_e else ("CASARIA (tolerante)" if hit_t else "NAO CASA")
    # o que acontece com a linha hoje
    if hit_e:
        destino = "aba Meta Ads + Vendas"
    elif main:
        destino = "so Vendas (meta=0) — some da aba Meta Ads"
    else:
        destino = ">>> DESCARTADA: some da dashboard inteira <<<"
    print(f"\n[{get(r,'Data')}] {prod!r} · {get(r,'Status')} · R$ {get(r,'Faturamento')} · Canal={get(r,'Canal')}")
    print(f"   {estado}  ->  hoje cai em: {destino}")
    for k, v in utms.items():
        if v:
            print(f"     {k:<13} = {v!r}")
    if hit_t and not hit_e:
        print(f"   >>> casaria com o Meta: campanha={hit_t[0]!r}")
        print(f"                            conjunto={hit_t[1]!r}")
        ganhos.append((get(r, "Data"), prod, camp_v, ad_v, hit_t, main))
    elif hit_e:
        ja_ok.append(r)
    else:
        sem_jeito.append((get(r, "Data"), prod, camp_v, ad_v, main))

print("\n" + "=" * 100)
print(f"RESUMO: casam hoje = {len(ja_ok)} · passariam a casar = {len(ganhos)} · "
      f"continuam sem casar = {len(sem_jeito)}")
print("=" * 100)
if sem_jeito:
    print("\nAs que continuam sem casar (UTM de campanha que nao existe no Meta exportado):")
    for d, p, c, a, mn in sem_jeito:
        print(f"  [{d}] {p!r} main={mn}")
        print(f"        utm_campaign={c!r}")
        print(f"        {cfg.AD_UTM_COLUMN}={a!r}")

# ---------- checagem de falso positivo ----------
print("\n" + "=" * 100)
print("CHECAGEM DE SEGURANCA: o match tolerante colapsa pares distintos do Meta?")
print("=" * 100)
col = Counter(loose(c) + "||" + loose(a) for (c, a) in exato)
conflitos = {k: n for k, n in col.items() if n > 1}
if conflitos:
    print(f"!! {len(conflitos)} colisoes — o match tolerante juntaria pares que hoje sao distintos:")
    for k in conflitos:
        print(f"   {k}")
else:
    print(f"OK: os {len(exato)} pares do Meta continuam {len(col)} pares distintos "
          f"sob a normalizacao tolerante. Nenhuma colisao, nenhum risco de atribuir "
          f"uma venda a campanha errada.")
