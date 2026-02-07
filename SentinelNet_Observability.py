import customtkinter as ctk
import requests
import threading
import time
import random
import json
from datetime import datetime

# --- CONFIGURAÇÃO VISUAL ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SentinelLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- DADOS DO SISTEMA ---
        self.sistema_nome = "SENTINEL NET"
        self.token = "7680348560:AAEg3ddNMjgHPFMvfuXrENEgyJZMR1nus_Y"
        self.chat_id = "7694564020"
        self.lojas_bloqueadas = set()
        
        self.regioes = {
            "RIO BRANCO": ["Centro", "Bosque", "Vila Ivonete", "Estação Experimental", "Tucumã"],
            "BRASILÉIA": ["Setor Comercial", "Fronteira", "Av. Internacional", "Km 1", "Km 4"],
            "BUJARI": ["Av. Principal", "Bairro Novo", "Vila do Incra", "Centro-SUL", "Área Industrial"]
        }

        self.title(f"{self.sistema_nome} | Monitoramento Independente")
        self.geometry("1150x750")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Barra Lateral
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo = ctk.CTkLabel(self.sidebar, text=self.sistema_nome, font=ctk.CTkFont(size=22, weight="bold"))
        self.logo.pack(padx=20, pady=(30, 10))
        
        self.status_box = ctk.CTkFrame(self.sidebar, fg_color="#1a1a1a")
        self.status_box.pack(padx=10, pady=10, fill="x")
        self.status_dot = ctk.CTkLabel(self.status_box, text="● SISTEMA ATIVO", text_color="#2ecc71", font=ctk.CTkFont(weight="bold"))
        self.status_dot.pack(pady=10)

        self.btn_reset = ctk.CTkButton(self.sidebar, text="REATIVAR TODAS UNIDADES", 
                                       fg_color="#2c3e50", hover_color="#c0392b",
                                       command=self.reativar_todas)
        self.btn_reset.pack(side="bottom", pady=20, padx=20)

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Status das Unidades em Tempo Real")
        self.scroll_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.scroll_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.cards = {}
        self.renderizar_lojas()

        threading.Thread(target=self.loop_monitoramento, daemon=True).start()

    def renderizar_lojas(self):
        row, col = 0, 0
        for regiao, locais in self.regioes.items():
            for local in locais:
                loja_id = f"{regiao} - {local}"
                card = ctk.CTkFrame(self.scroll_frame, width=250, height=120, corner_radius=10)
                card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                card.grid_propagate(False) 
                
                lbl_nome = ctk.CTkLabel(card, text=local, font=ctk.CTkFont(size=14, weight="bold"))
                lbl_nome.pack(pady=(10, 0))
                lbl_status = ctk.CTkLabel(card, text="🟢 ONLINE", text_color="#2ecc71")
                lbl_status.pack(pady=5)

                btn_fix = ctk.CTkButton(card, text="REATIVAR", height=20, width=80, 
                                        fg_color="transparent", border_width=1,
                                        command=lambda lid=loja_id: self.reativar_loja(lid))
                btn_fix.pack(pady=5)
                btn_fix.configure(state="disabled")

                self.cards[loja_id] = {"frame": card, "status": lbl_status, "btn": btn_fix, "regiao": regiao, "local": local}
                col += 1
                if col > 2: col = 0; row += 1

    def enviar_telegram(self, mensagem, botoes=None):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": mensagem, "parse_mode": "Markdown"}
        if botoes:
            payload["reply_markup"] = json.dumps({"inline_keyboard": botoes})
        try:
            requests.post(url, data=payload, timeout=5)
        except:
            pass

    def alerta_sucesso_auto(self, loja_id):
        info = self.cards[loja_id]
        agora = datetime.now().strftime("%H:%M:%S")
        msg = f"✅ **REPARO BEM SUCEDIDO - SENTINEL NET**\n\n🏢 **Loja:** {info['local']}\n📍 **Status:** Restabelecido via Software\n⏰ **Horário:** {agora}\n\n🛡️ O sistema detectou uma instabilidade e aplicou protocolos de correção automática. **Não é necessário deslocamento físico.**"
        self.enviar_telegram(msg)

    def alerta_falha_fisica(self, loja_id):
        info = self.cards[loja_id]
        agora = datetime.now().strftime("%H:%M:%S")
        mensagem = f"""⚠️ **ALERTA DE QUEDA DETECTADA** ⚠️

🏢 **Loja:** {info['local']}
📍 **Região:** {info['regiao']}
⏰ **Início:** {agora}

3 analise e tentativas de religar o sistemas falhadas
nao detetcado problemas no sistema
falha fisica (queda de luz, fio cortado, etc)

🔍 **STATUS:** Aguardando manutenção física."""
        
        botoes = [[{"text": "✅ SISTEMA RESTABELECIDO (TI)", "callback_data": f"resolver_{loja_id}"}]]
        self.enviar_telegram(mensagem, botoes)

    def reativar_loja(self, loja_id):
        if loja_id in self.lojas_bloqueadas:
            self.lojas_bloqueadas.remove(loja_id)
            self.cards[loja_id]["status"].configure(text="🟢 ONLINE", text_color="#2ecc71")
            self.cards[loja_id]["frame"].configure(fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
            self.cards[loja_id]["btn"].configure(state="disabled", fg_color="transparent")

    def reativar_todas(self):
        for lid in list(self.lojas_bloqueadas): self.reativar_loja(lid)

    def loop_monitoramento(self):
        while True:
            for loja_id in self.cards.keys():
                if loja_id not in self.lojas_bloqueadas:
                    if random.random() < 0.01: # Simula queda
                        self.lojas_bloqueadas.add(loja_id)
                        self.after(0, self.atualizar_visual_queda, loja_id)
                        
                        # TENTATIVA DE AUTO-REPARO (Simulação de 3 tentativas)
                        print(f"Tentando auto-reparo em {loja_id}...")
                        time.sleep(2) 
                        
                        if random.random() < 0.7: # 70% de chance de o software resolver sozinho
                            self.after(0, self.reativar_loja, loja_id)
                            self.alerta_sucesso_auto(loja_id)
                        else:
                            self.alerta_falha_fisica(loja_id)
            time.sleep(5)

    def atualizar_visual_queda(self, loja_id):
        self.cards[loja_id]["status"].configure(text="🔴 OFFLINE", text_color="#e74c3c")
        self.cards[loja_id]["frame"].configure(fg_color="#442222")
        self.cards[loja_id]["btn"].configure(state="normal", fg_color="#e74c3c")

if __name__ == "__main__":
    app = SentinelLauncher()
    app.mainloop()