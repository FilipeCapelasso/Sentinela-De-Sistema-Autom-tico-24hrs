# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║        SentinelaNet Operations Center — SNOC v2.0                    ║
║        Sistema de Monitoramento de Infraestrutura Nacional           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import subprocess
import sys
import os
import logging

# ── Logging profissional ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("snoc.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("SNOC")

# ── Auto-instalação silenciosa ─────────────────────────────────────────
def _install(pkg):
    log.info(f"Instalando dependência: {pkg}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for _dep, _imp in [("pyTelegramBotAPI", "telebot"), ("python-dotenv", "dotenv"), ("requests", "requests")]:
    try:
        __import__(_imp)
    except ImportError:
        _install(_dep)

# ── Imports principais ─────────────────────────────────────────────────
import customtkinter as ctk
from tkinter import ttk, messagebox
import json, threading, requests, time, random, datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ── Configurações (env vars com fallback) ──────────────────────────────
BOT_TOKEN = os.getenv("SNOC_BOT_TOKEN", "SEU_TOKEN_AQUI")
CHAT_ID   = os.getenv("SNOC_CHAT_ID",   "SEU_CHAT_ID_AQUI")

# ── Paleta de cores SNOC ───────────────────────────────────────────────
COLORS = {
    "bg_deep":      "#04060A",
    "bg_panel":      "#080C12",
    "bg_card":      "#0B1018",
    "border":        "#0D3B2E",
    "accent":        "#00E676",
    "accent_dim":   "#00A854",
    "accent_dark":  "#003319",
    "warn":         "#FFB300",
    "danger":       "#FF1744",
    "danger_dark":  "#3D0010",
    "text_primary": "#E0FFE8",
    "text_dim":     "#4A7A5A",
    "text_muted":   "#1E3A28",
    "cyan":         "#00BCD4",
    "blue_dim":     "#0A1F30",
}

FONT_MONO  = ("Consolas", )
FONT_TITLE = ("Courier New", )


# ══════════════════════════════════════════════════════════════════════
class SNOC(ctk.CTk):
    """SentinelaNet Operations Center — Aplicação principal"""

    VERSION = "2.0.1"

    # ── Pasta de destino dos logs alterada conforme solicitação ──────
    LOG_DIR = r"C:\Users\Filipe\OneDrive\Documentos\RELATORIOS"

    def __init__(self):
        super().__init__()

        # ── Bot Telegram ───────────────────────────────────────────
        self.bot     = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN != "SEU_TOKEN_AQUI" else None
        self.chat_id = CHAT_ID

        # ── Estado interno ─────────────────────────────────────────
        self.status_cache: dict = {}
        self.lock_status:  set  = set()
        self.cidade_atual       = None
        self.running            = True
        self.total_alertas      = 0
        self.total_estavel      = 0
        self.total_manutencao   = 0
        self.uptime_start       = datetime.datetime.now()
        self._total_enviados    = 0

        # ── Arquivo de dados ───────────────────────────────────────
        self.base_path   = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.base_path, "SNOC_DATABASE.json")
        self.infra: dict = {}

        self._build_window()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Threads ────────────────────────────────────────────────
        threading.Thread(target=self._init_system,   daemon=True).start()
        threading.Thread(target=self._bot_watchdog,  daemon=True).start()
        threading.Thread(target=self._uptime_ticker, daemon=True).start()

    def _build_window(self):
        self.title("SentinelaNet Operations Center — SNOC")
        self.geometry("1680x960")
        self.minsize(1280, 720)
        self.configure(fg_color=COLORS["bg_deep"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_sidebar()
        self._build_main()
        self._build_statusbar()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=90, corner_radius=0,
                           fg_color=COLORS["bg_panel"],
                           border_width=1, border_color=COLORS["border"])
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        logo_frame = ctk.CTkFrame(bar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=25, pady=0, sticky="w")

        ctk.CTkLabel(
            logo_frame,
            text="SentinelaNet Operations Center",
            font=(*FONT_TITLE, 26, "bold"),
            text_color=COLORS["accent"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame,
            text="S N O C",
            font=(*FONT_MONO, 13, "bold"),
            text_color=COLORS["text_dim"],
            justify="center"
        ).pack(anchor="center")

        kpi_frame = ctk.CTkFrame(bar, fg_color="transparent")
        kpi_frame.grid(row=0, column=1, padx=10, pady=0)

        self.kpi_ok   = self._kpi_badge(kpi_frame, "OPERACIONAIS",   "0", COLORS["accent"])
        self.kpi_warn = self._kpi_badge(kpi_frame, "EM MANUTENÇÃO",  "0", COLORS["warn"])
        self.kpi_crit = self._kpi_badge(kpi_frame, "FALHAS CRÍTICAS","0", COLORS["danger"])

        for w in [self.kpi_ok, self.kpi_warn, self.kpi_crit]:
            w.pack(side="left", padx=12)

        right_frame = ctk.CTkFrame(bar, fg_color="transparent")
        right_frame.grid(row=0, column=2, padx=25, sticky="e")

        self.lbl_hora = ctk.CTkLabel(right_frame, text="--:--:--",
                                     font=(*FONT_MONO, 20, "bold"),
                                     text_color=COLORS["accent"])
        self.lbl_hora.pack(anchor="e")

        self.lbl_uptime = ctk.CTkLabel(right_frame, text="UPTIME: 00:00:00",
                                       font=(*FONT_MONO, 10),
                                       text_color=COLORS["text_dim"])
        self.lbl_uptime.pack(anchor="e")

        ctk.CTkLabel(right_frame,
                     text=f"SNOC v{self.VERSION}  •  BRASIL",
                     font=(*FONT_MONO, 10),
                     text_color=COLORS["text_muted"]).pack(anchor="e", pady=(2, 0))

        self.after(0, self._tick_clock)

    _KPI_BORDER = {
        "#00E676": "#005A30",
        "#FFB300": "#5A3E00",
        "#FF1744": "#5A0018",
    }

    def _kpi_badge(self, parent, label, value, color):
        border = self._KPI_BORDER.get(color, COLORS["border"])
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"],
                             corner_radius=8,
                             border_width=1, border_color=border)
        ctk.CTkLabel(frame, text=label, font=(*FONT_MONO, 9),
                     text_color=COLORS["text_dim"]).pack(padx=18, pady=(10, 0))
        val_lbl = ctk.CTkLabel(frame, text=value, font=(*FONT_MONO, 28, "bold"),
                               text_color=color)
        val_lbl.pack(padx=18, pady=(0, 10))
        frame._val_lbl = val_lbl
        return frame

    def _update_kpi(self, widget, value: str):
        widget._val_lbl.configure(text=value)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0,
                                    fg_color=COLORS["bg_panel"],
                                    border_width=1, border_color=COLORS["border"])
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        hdr = ctk.CTkFrame(self.sidebar, fg_color=COLORS["bg_card"],
                           corner_radius=0, height=50,
                           border_width=1, border_color=COLORS["border"])
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="◈  HIERARQUIA NACIONAL",
                     font=(*FONT_MONO, 11, "bold"),
                     text_color=COLORS["accent_dim"]).pack(side="left", padx=15)

        self.lbl_loading = ctk.CTkLabel(self.sidebar,
                                        text="⟳  INICIALIZANDO...",
                                        font=(*FONT_MONO, 10),
                                        text_color=COLORS["warn"])
        self.lbl_loading.pack(pady=6)

        search_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filtrar_tree)

        ctk.CTkEntry(search_frame,
                     textvariable=self.search_var,
                     placeholder_text="🔍  Buscar cidade ou UF...",
                     fg_color=COLORS["bg_card"],
                     border_color=COLORS["border"],
                     text_color=COLORS["text_primary"],
                     font=(*FONT_MONO, 11)).pack(fill="x")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("SNOC.Treeview",
                        background=COLORS["bg_panel"],
                        foreground=COLORS["accent_dim"],
                        fieldbackground=COLORS["bg_panel"],
                        borderwidth=0,
                        font=(*FONT_MONO, 10),
                        rowheight=22)
        style.configure("SNOC.Treeview.Heading",
                        background=COLORS["bg_card"],
                        foreground=COLORS["text_dim"],
                        borderwidth=0)
        style.map("SNOC.Treeview",
                  background=[("selected", COLORS["accent_dark"])],
                  foreground=[("selected", COLORS["accent"])])

        tree_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=6, pady=(0, 10))

        self.tree = ttk.Treeview(tree_frame, show="tree", style="SNOC.Treeview")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.lbl_node_count = ctk.CTkLabel(self.sidebar,
                                            text="0 unidades monitoradas",
                                            font=(*FONT_MONO, 9),
                                            text_color=COLORS["text_muted"])
        self.lbl_node_count.pack(pady=(0, 8))

    def _build_main(self):
        self.main_view = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_deep"],
            corner_radius=0,
            scrollbar_button_color=COLORS["accent_dark"],
            scrollbar_button_hover_color=COLORS["accent_dim"]
        )
        self.main_view.grid(row=1, column=1, sticky="nsew")
        self._show_welcome()

    def _show_welcome(self):
        f = ctk.CTkFrame(self.main_view, fg_color="transparent")
        f.pack(expand=True, fill="both", pady=200)

        ctk.CTkLabel(f,
                     text="SNOC",
                     font=(*FONT_TITLE, 80, "bold"),
                     text_color=COLORS["accent_dark"]).pack()
        ctk.CTkLabel(f,
                     text="SentinelaNet Operations Center",
                     font=(*FONT_MONO, 18),
                     text_color=COLORS["text_muted"]).pack()
        ctk.CTkLabel(f,
                     text="◄  Selecione um estado e cidade para iniciar o monitoramento",
                     font=(*FONT_MONO, 13),
                     text_color=COLORS["text_dim"]).pack(pady=30)

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=28, corner_radius=0,
                           fg_color=COLORS["bg_panel"],
                           border_width=1, border_color=COLORS["border"])
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)

        self.lbl_status_msg = ctk.CTkLabel(bar,
                                           text="●  SISTEMA ONLINE  |  Aguardando seleção",
                                           font=(*FONT_MONO, 10),
                                           text_color=COLORS["accent_dim"])
        self.lbl_status_msg.pack(side="left", padx=15)

        self.lbl_alertas_total = ctk.CTkLabel(bar,
                                              text="ALERTAS ENVIADOS: 0",
                                              font=(*FONT_MONO, 10),
                                              text_color=COLORS["text_dim"])
        self.lbl_alertas_total.pack(side="right", padx=15)

    def _tick_clock(self):
        if self.running:
            now = datetime.datetime.now()
            self.lbl_hora.configure(text=now.strftime("%H:%M:%S"))
            self.after(1000, self._tick_clock)

    def _uptime_ticker(self):
        while self.running:
            delta = datetime.datetime.now() - self.uptime_start
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m, s   = divmod(rem, 60)
            self.after(0, lambda t=f"{h:02d}:{m:02d}:{s:02d}":
                       self.lbl_uptime.configure(text=f"UPTIME: {t}"))
            time.sleep(1)

    def _init_system(self):
        if os.path.exists(self.config_file):
            self._set_loading("⟳  CARREGANDO BANCO DE DADOS LOCAL...")
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.infra = json.load(f)
                log.info("Banco de dados carregado do cache.")
            except Exception as e:
                log.warning(f"Cache corrompido: {e}. Rebuscando IBGE...")
                self.infra = self._fetch_ibge()
        else:
            self.infra = self._fetch_ibge()

        self.after(0, self._popular_tree)
        threading.Thread(target=self._engine_status, daemon=True).start()

    def _fetch_ibge(self) -> dict:
        base = {"BRASIL": {}}
        nomes_unidades = [
            "UNIDADE CENTRAL", "POSTO LOGÍSTICO", "CENTRO DE DADOS",
            "ALMOXARIFADO REGIONAL", "SUPORTE TÉCNICO", "FARMÁCIA CENTRAL",
            "TERMINAL ALPHA", "BASE OPERACIONAL", "HUB DE REDE", "GERÊNCIA REGIONAL"
        ]
        try:
            self._set_loading("⟳  CONECTANDO AO IBGE...")
            r = requests.get(
                "https://servicodados.ibge.gov.br/api/v1/localidades/estados",
                timeout=15
            )
            estados = sorted(r.json(), key=lambda x: x["nome"])

            for est in estados:
                uf_nome = est["nome"].upper()
                sigla   = est["sigla"]
                self._set_loading(f"⟳  SINCRONIZANDO {uf_nome}...")
                log.info(f"Carregando municípios de {uf_nome}")

                r2 = requests.get(
                    f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{sigla}/municipios",
                    timeout=15
                )
                cidades = sorted(r2.json(), key=lambda x: x["nome"])
                base["BRASIL"][uf_nome] = {}

                for c in cidades:
                    nome_cid = c["nome"].upper()
                    base["BRASIL"][uf_nome][nome_cid] = [
                        {
                            "unidade": nomes_unidades[j],
                            "endereco": f"AV. PRINCIPAL, {random.randint(100, 9999)} — {nome_cid}/{sigla}",
                            "cidade":   nome_cid,
                            "uf":       sigla
                        }
                        for j in range(10)
                    ]

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(base, f, indent=2, ensure_ascii=False)
            log.info("Banco de dados salvo com sucesso.")
        except Exception as e:
            log.error(f"Falha ao buscar IBGE: {e}")
            self._set_loading("✖  MODO DE CONTINGÊNCIA ATIVO")
            base = {"BRASIL": {"ERRO DE CONEXÃO": {"SEM DADOS": []}}}
        return base

    def _popular_tree(self):
        self._set_loading("●  MONITORAMENTO ONLINE")
        self.lbl_loading.configure(text_color=COLORS["accent"])

        total = 0
        root = self.tree.insert("", "end", text="🇧🇷  BRASIL", open=False)
        for uf in sorted(self.infra["BRASIL"].keys()):
            id_uf = self.tree.insert(root, "end", text=f"  {uf}", open=False)
            for cid in sorted(self.infra["BRASIL"][uf].keys()):
                self.tree.insert(id_uf, "end", text=f"    {cid}")
                total += 10

        self.lbl_node_count.configure(text=f"{total:,} unidades monitoradas")
        self._set_status(f"●  SISTEMA ONLINE  |  {len(self.infra['BRASIL'])} estados carregados")

    def _filtrar_tree(self, *_):
        termo = self.search_var.get().strip().upper()
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not termo:
            self._popular_tree()
            return

        root = self.tree.insert("", "end", text="🇧🇷  BRASIL", open=True)
        for uf in sorted(self.infra["BRASIL"].keys()):
            resultados = [c for c in self.infra["BRASIL"][uf] if termo in c or termo in uf]
            if resultados:
                id_uf = self.tree.insert(root, "end", text=f"  {uf}", open=True)
                for cid in sorted(resultados):
                    self.tree.insert(id_uf, "end", text=f"    {cid}")

    def _ao_selecionar(self, _event):
        try:
            item  = self.tree.selection()[0]
            texto = self.tree.item(item, "text").strip().lstrip("🇧🇷").strip()
            pai   = self.tree.parent(item)
            avo   = self.tree.parent(pai) if pai else None
            if pai and avo:
                uf = self.tree.item(pai, "text").strip()
                if texto in self.infra["BRASIL"].get(uf, {}):
                    self.cidade_atual = (uf, texto)
                    self._renderizar_cidade()
        except Exception as e:
            log.debug(f"Seleção ignorada: {e}")

    def _engine_status(self):
        while self.running:
            try:
                if self.cidade_atual:
                    uf, cidade = self.cidade_atual
                    lojas = self.infra["BRASIL"].get(uf, {}).get(cidade, [])
                    ok = mnt = crit = 0

                    for loja in lojas:
                        key = f"{cidade}|{loja['unidade']}"

                        if key in self.lock_status:
                            self.status_cache[key] = {
                                "status": "QUEDA CRÍTICA — INTERVENÇÃO FÍSICA NECESSÁRIA",
                                "nivel":  "CRITICO"
                            }
                            crit += 1
                        else:
                            rnd = random.random()
                            if rnd < 0.03:
                                self.lock_status.add(key)
                                self._send_telegram(loja["unidade"], cidade, uf)
                                crit += 1
                            elif rnd < 0.12:
                                self.status_cache[key] = {
                                    "status": "EM MANUTENÇÃO PREVENTIVA",
                                    "nivel":  "AVISO"
                                }
                                mnt += 1
                            else:
                                self.status_cache[key] = {
                                    "status": "OPERACIONAL",
                                    "nivel":  "OK"
                                }
                                ok += 1

                    self.total_estavel    = ok
                    self.total_manutencao = mnt
                    self.total_alertas    = crit
                    self.after(0, self._atualizar_kpis)
                    self.after(0, self._renderizar_cidade)

            except Exception as e:
                log.warning(f"Engine de status: {e}")
            time.sleep(5)

    def _atualizar_kpis(self):
        self._update_kpi(self.kpi_ok,   str(self.total_estavel))
        self._update_kpi(self.kpi_warn, str(self.total_manutencao))
        self._update_kpi(self.kpi_crit, str(self.total_alertas))

    def _renderizar_cidade(self):
        if not self.cidade_atual:
            return
        uf, cidade = self.cidade_atual
        lojas = self.infra["BRASIL"].get(uf, {}).get(cidade, [])

        for w in self.main_view.winfo_children():
            w.destroy()

        hdr = ctk.CTkFrame(self.main_view, fg_color=COLORS["bg_card"],
                           corner_radius=8,
                           border_width=1, border_color=COLORS["border"])
        hdr.pack(fill="x", padx=20, pady=(20, 10))

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=20, pady=15)

        ctk.CTkLabel(left,
                     text=f"// TERMINAL: {cidade}",
                     font=(*FONT_TITLE, 22, "bold"),
                     text_color=COLORS["accent"]).pack(anchor="w")
        ctk.CTkLabel(left,
                     text=f"Estado: {uf}  |  {len(lojas)} unidades  |  Atualização a cada 5s",
                     font=(*FONT_MONO, 10),
                     text_color=COLORS["text_dim"]).pack(anchor="w")

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=20)

        ctk.CTkButton(right,
                      text="⬇  EXPORTAR LOG DE ERROS",
                      fg_color=COLORS["danger_dark"],
                      hover_color="#5a0018",
                      text_color=COLORS["danger"],
                      font=(*FONT_MONO, 11, "bold"),
                      corner_radius=6,
                      command=self._exportar_log).pack(pady=5)

        ctk.CTkButton(right,
                      text="⟳  FORÇAR ATUALIZAÇÃO",
                      fg_color=COLORS["accent_dark"],
                      hover_color="#004D30",
                      text_color=COLORS["accent"],
                      font=(*FONT_MONO, 11, "bold"),
                      corner_radius=6,
                      command=self._renderizar_cidade).pack()

        grid = ctk.CTkFrame(self.main_view, fg_color="transparent")
        grid.pack(fill="both", padx=20, pady=5)
        grid.grid_columnconfigure((0, 1), weight=1)

        for i, loja in enumerate(lojas):
            key = f"{cidade}|{loja['unidade']}"
            st  = self.status_cache.get(key, {"status": "INICIALIZANDO...", "nivel": "OK"})
            self._card_unidade(grid, loja, st, i // 2, i % 2)

    def _card_unidade(self, parent, loja, st, row, col):
        nivel = st.get("nivel", "OK")
        cor_map = {
            "OK":      (COLORS["accent"],  COLORS["bg_card"],    COLORS["border"]),
            "AVISO":   (COLORS["warn"],    "#141000",             "#3D2E00"),
            "CRITICO": (COLORS["danger"],  COLORS["danger_dark"], "#5A0018"),
        }
        cor_text, cor_bg, cor_border = cor_map.get(nivel, cor_map["OK"])

        icon_map = {"OK": "●", "AVISO": "▲", "CRITICO": "✖"}
        icon = icon_map.get(nivel, "●")

        card = ctk.CTkFrame(parent,
                            fg_color=cor_bg,
                            corner_radius=8,
                            border_width=1,
                            border_color=cor_border)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="ew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(top,
                     text=f"{icon}  {loja['unidade']}",
                     font=(*FONT_MONO, 13, "bold"),
                     text_color=cor_text,
                     anchor="w").pack(side="left")

        ctk.CTkLabel(top,
                     text=f" {nivel} ",
                     font=(*FONT_MONO, 9, "bold"),
                     fg_color=cor_border,
                     text_color=cor_text,
                     corner_radius=4).pack(side="right")

        ctk.CTkFrame(inner, height=1, fg_color=cor_border).pack(fill="x", pady=(8, 8))

        ctk.CTkLabel(inner,
                     text=f"📍  {loja['endereco']}",
                     font=(*FONT_MONO, 10),
                     text_color=COLORS["text_dim"],
                     anchor="w").pack(fill="x")

        ctk.CTkLabel(inner,
                     text=f"⚡  {st['status']}",
                     font=(*FONT_MONO, 11, "bold"),
                     text_color=cor_text,
                     anchor="w").pack(fill="x", pady=(4, 0))

    def _send_telegram(self, unidade: str, cidade: str, uf: str):
        if not self.bot:
            return
        try:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(
                "✅  CONFIRMAR REPARO E REATIVAR",
                callback_data=f"fix|{cidade}|{unidade}"
            ))
            markup.add(InlineKeyboardButton(
                "📋  ABRIR CHAMADO TÉCNICO",
                callback_data=f"ticket|{cidade}|{unidade}"
            ))

            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            msg = (
                f"🚨 *ALERTA CRÍTICO — SNOC*\n"
                f"{'─' * 30}\n"
                f"🏢 *Unidade:* `{unidade}`\n"
                f"🏙️ *Município:* `{cidade} / {uf}`\n"
                f"❌ *Status:* QUEDA TOTAL DE HARDWARE\n"
                f"🕐 *Hora:* `{now}`\n"
                f"{'─' * 30}\n"
                f"⚠️ _Reparo via software impossível._\n"
                f"_Intervenção física obrigatória._"
            )
            self.bot.send_message(self.chat_id, msg,
                                  parse_mode="Markdown",
                                  reply_markup=markup)
            log.info(f"Alerta Telegram enviado: {unidade} / {cidade}")

            self._total_enviados += 1
            self.after(0, lambda n=self._total_enviados:
                       self.lbl_alertas_total.configure(text=f"ALERTAS ENVIADOS: {n}"))

        except Exception as e:
            log.error(f"Falha ao enviar Telegram: {e}")

    def _bot_watchdog(self):
        while self.running:
            try:
                self._ouvir_bot()
            except Exception as e:
                log.warning(f"Bot polling caiu: {e}. Reconectando em 5s...")
                time.sleep(5)

    def _ouvir_bot(self):
        if not self.bot:
            return

        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("fix|"))
        def cb_fix(call):
            try:
                _, cidade, unidade = call.data.split("|")
                key = f"{cidade}|{unidade}"
                if key in self.lock_status:
                    self.lock_status.discard(key)
                    self.status_cache[key] = {"status": "OPERACIONAL", "nivel": "OK"}
                    self.bot.answer_callback_query(call.id, "✅ Unidade reativada com sucesso!")
                    self.bot.edit_message_text(
                        f"✅ *UNIDADE REATIVADA*\n`{unidade}` — `{cidade}`\n_Reparo confirmado pelo técnico._",
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        parse_mode="Markdown"
                    )
                    self.after(0, self._renderizar_cidade)
                    log.info(f"Unidade reativada via Telegram: {unidade} / {cidade}")
            except Exception as e:
                log.error(f"Callback fix: {e}")

        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("ticket|"))
        def cb_ticket(call):
            try:
                _, cidade, unidade = call.data.split("|")
                self.bot.answer_callback_query(call.id, "📋 Chamado registrado!")
                self.bot.send_message(
                    call.message.chat.id,
                    f"📋 *CHAMADO TÉCNICO ABERTO*\n"
                    f"Unidade: `{unidade}`\nCidade: `{cidade}`\n"
                    f"Status: _Aguardando atribuição de técnico._",
                    parse_mode="Markdown"
                )
            except Exception as e:
                log.error(f"Callback ticket: {e}")

        self.bot.polling(none_stop=True, timeout=60)

    def _exportar_log(self):
        if not self.cidade_atual:
            return
        uf, cidade = self.cidade_atual
        agora = datetime.datetime.now()

        os.makedirs(self.LOG_DIR, exist_ok=True)

        timestamp_nome    = agora.strftime("%d-%m-%Y_%H-%M")
        timestamp_interno = agora.strftime("%d/%m/%Y %H:%M:%S")
        cidade_safe        = cidade.replace(" ", "_").replace("/", "-")
        nome_arquivo      = f"{timestamp_nome} - {cidade_safe}.txt"
        caminho_completo  = os.path.join(self.LOG_DIR, nome_arquivo)

        try:
            falhas = mnt = 0
            linhas_falha = []
            for k, v in self.status_cache.items():
                if cidade in k and v.get("nivel") in ("CRITICO", "AVISO"):
                    tag = f"[{v['nivel']}]"
                    linhas_falha.append(f"{tag} Unidade: {k.split('|')[1]} - Status: {v['status']}")
                    if v["nivel"] == "CRITICO":
                        falhas += 1
                    else:
                        mnt += 1

            with open(caminho_completo, "w", encoding="utf-8") as f:
                f.write(f"RELATÓRIO SNOC - {timestamp_interno}\n")
                f.write(f"TERMINAL: {cidade} / {uf}\n")
                f.write(f"{'='*40}\n")
                f.write(f"RESUMO: {falhas} falhas críticas | {mnt} em manutenção\n\n")
                f.write("\n".join(linhas_falha) if linhas_falha else "Nenhuma irregularidade detectada.")

            messagebox.showinfo("Sucesso", f"Log exportado para:\n{caminho_completo}")
        except Exception as e:
            log.error(f"Erro ao exportar log: {e}")
            messagebox.showerror("Erro", "Não foi possível salvar o arquivo de log.")

    def _set_loading(self, msg):
        self.lbl_loading.configure(text=msg)

    def _set_status(self, msg):
        self.lbl_status_msg.configure(text=msg)

    def _on_close(self):
        self.running = False
        self.destroy()

if __name__ == "__main__":
    app = SNOC()
    app.mainloop()
