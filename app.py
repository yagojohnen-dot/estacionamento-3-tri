#!/usr/bin/env python3
"""
Sistema de Estacionamento Pro
Com validação de placa (incluindo motos)
"""

from flask import Flask, request, redirect, url_for, flash, get_flashed_messages
from datetime import datetime
from enum import Enum
import sqlite3
import re

app = Flask(__name__)
app.secret_key = "estacionamento_pro_2026"

DB_NAME = "estacionamento.db"
TOTAL_VAGAS = 30


class TipoVeiculo(Enum):
    CARRO = "carro"
    MOTO = "moto"
    CAMINHAO = "caminhao"


TARIFAS = {
    TipoVeiculo.CARRO: 8.00,
    TipoVeiculo.MOTO: 4.00,
    TipoVeiculo.CAMINHAO: 15.00,
}


# ==================== VALIDAÇÃO DE PLACA ====================

def validar_placa(placa: str, tipo: str = None) -> bool:
    """
    Valida placa brasileira.
    - Carro/Caminhão: formatos oficiais (7 caracteres)
    - Moto: aceita também formatos mais curtos
    """
    placa = placa.upper().strip()

    # Formatos oficiais
    padrao_antigo = r'^[A-Z]{3}[0-9]{4}$'              # ABC1234
    padrao_mercosul = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'  # ABC1D23

    if re.match(padrao_antigo, placa) or re.match(padrao_mercosul, placa):
        return True

    # Formatos extras só para MOTO
    if tipo == "moto":
        # Formato antigo de moto: 3 letras + 3 números (ABC123)
        if re.match(r'^[A-Z]{3}[0-9]{3}$', placa):
            return True
        # Formato curto (ex: DSAD) - 4 a 6 caracteres
        if re.match(r'^[A-Z0-9]{4,6}$', placa):
            return True

    return False


# ==================== BANCO DE DADOS ====================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS veiculos (
            placa TEXT PRIMARY KEY,
            tipo TEXT NOT NULL,
            modelo TEXT,
            cor TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            vaga INTEGER NOT NULL,
            entrada TIMESTAMP NOT NULL,
            saida TIMESTAMP,
            valor_pago REAL DEFAULT 0,
            finalizado INTEGER DEFAULT 0,
            FOREIGN KEY (placa) REFERENCES veiculos(placa)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracao (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    cursor.execute("SELECT valor FROM configuracao WHERE chave = 'total_vagas'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO configuracao (chave, valor) VALUES (?, ?)", ("total_vagas", str(TOTAL_VAGAS)))
    conn.commit()
    conn.close()


def total_vagas():
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracao WHERE chave = 'total_vagas'").fetchone()
    conn.close()
    return int(row["valor"]) if row else TOTAL_VAGAS


def vagas_ocupadas():
    conn = get_db()
    rows = conn.execute("SELECT vaga FROM tickets WHERE finalizado = 0").fetchall()
    conn.close()
    return [r["vaga"] for r in rows]


def encontrar_vaga_livre():
    ocupadas = set(vagas_ocupadas())
    for i in range(1, total_vagas() + 1):
        if i not in ocupadas:
            return i
    return None


def ticket_ativo(placa: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM tickets WHERE placa = ? AND finalizado = 0", (placa.upper(),)).fetchone()
    conn.close()
    return row


def calcular_valor(entrada_str: str, placa: str) -> float:
    conn = get_db()
    veiculo = conn.execute("SELECT tipo FROM veiculos WHERE placa = ?", (placa,)).fetchone()
    conn.close()
    if not veiculo:
        return 0.0
    tipo = TipoVeiculo(veiculo["tipo"])
    entrada = datetime.strptime(entrada_str, "%Y-%m-%d %H:%M:%S")
    minutos = (datetime.now() - entrada).total_seconds() / 60
    horas = max(1, minutos / 60)
    horas_cobradas = max(1, round(horas + 0.49))
    return round(horas_cobradas * TARIFAS[tipo], 2)


# ==================== LAYOUT ====================

def render_page(content: str, aba_ativa: str = "vagas"):
    messages = get_flashed_messages(with_categories=True)
    alerts = ""
    for cat, msg in messages:
        icons = {"success": "check-circle-fill", "danger": "exclamation-triangle-fill",
                 "warning": "exclamation-circle-fill", "info": "info-circle-fill"}
        icon = icons.get(cat, "info-circle-fill")
        alerts += f'''
        <div class="alert alert-{cat} alert-dismissible fade show shadow-sm" role="alert">
            <i class="bi bi-{icon} me-2"></i>{msg}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>'''

    def ativa(nome):
        return "active" if aba_ativa == nome else ""

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estacionamento Pro</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #4f46e5;
            --bg: #f1f5f9;
            --card: #ffffff;
            --text: #1e293b;
            --muted: #64748b;
        }}
        * {{ font-family: 'Inter', system-ui, sans-serif; }}
        body {{ background: var(--bg); color: var(--text); min-height: 100vh; }}
        .navbar {{
            background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
            box-shadow: 0 4px 20px rgba(79, 70, 229, 0.3);
            padding: 0.9rem 1.5rem;
        }}
        .navbar-brand {{ font-weight: 700; font-size: 1.35rem; letter-spacing: -0.5px; }}
        .nav-pills .nav-link {{
            color: var(--muted); font-weight: 600; font-size: 0.9rem;
            border-radius: 12px; padding: 0.65rem 1.2rem; transition: all 0.2s;
        }}
        .nav-pills .nav-link:hover {{ background: #e2e8f0; color: var(--text); }}
        .nav-pills .nav-link.active {{
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            color: white; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
        }}
        .stat-card {{
            border: none; border-radius: 18px; padding: 1.4rem; color: white;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1); transition: transform 0.25s;
        }}
        .stat-card:hover {{ transform: translateY(-5px); }}
        .stat-card .label {{ font-size: 0.8rem; opacity: 0.9; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}
        .stat-card .value {{ font-size: 2.2rem; font-weight: 700; margin-top: 0.3rem; }}
        .stat-card.blue {{ background: linear-gradient(135deg, #3b82f6, #2563eb); }}
        .stat-card.red {{ background: linear-gradient(135deg, #ef4444, #dc2626); }}
        .stat-card.green {{ background: linear-gradient(135deg, #10b981, #059669); }}
        .stat-card.orange {{ background: linear-gradient(135deg, #f59e0b, #d97706); }}
        .main-card {{ border: none; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); background: var(--card); }}
        .main-card .card-header {{ background: transparent; border-bottom: 1px solid #e2e8f0; padding: 1.2rem 1.5rem; font-weight: 600; }}
        .vaga {{
            border-radius: 14px; padding: 14px 8px; text-align: center; height: 120px;
            display: flex; flex-direction: column; justify-content: center; transition: all 0.25s;
        }}
        .vaga.livre {{ background: linear-gradient(145deg, #d1fae5, #a7f3d0); border: 2px solid #34d399; color: #065f46; }}
        .vaga.ocupada {{ background: linear-gradient(145deg, #fee2e2, #fecaca); border: 2px solid #f87171; color: #991b1b; }}
        .vaga:hover {{ transform: scale(1.05); box-shadow: 0 8px 20px rgba(0,0,0,0.12); }}
        .vaga .num {{ font-size: 0.7rem; font-weight: 600; opacity: 0.8; }}
        .vaga .placa {{ font-size: 0.95rem; font-weight: 700; letter-spacing: 0.5px; margin: 2px 0; }}
        .vaga .info {{ font-size: 0.68rem; }}
        .vaga .livre-text {{ font-weight: 700; font-size: 0.95rem; margin-top: 4px; }}
        .form-card {{ border: none; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); max-width: 480px; margin: 0 auto; }}
        .form-card .card-header {{ border-radius: 20px 20px 0 0 !important; padding: 1.2rem 1.5rem; font-weight: 600; }}
        .form-control, .form-select {{ border-radius: 12px; border: 1.5px solid #e2e8f0; padding: 0.7rem 1rem; }}
        .form-control:focus, .form-select:focus {{ border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15); }}
        .btn-modern {{ border-radius: 12px; padding: 0.75rem 1.5rem; font-weight: 600; border: none; transition: all 0.2s; }}
        .btn-modern:hover {{ transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.15); }}
        .btn-success-modern {{ background: linear-gradient(135deg, #10b981, #059669); color: white; }}
        .btn-danger-modern {{ background: linear-gradient(135deg, #ef4444, #dc2626); color: white; }}
        .btn-info-modern {{ background: linear-gradient(135deg, #06b6d4, #0891b2); color: white; }}
        .table thead {{ background: #1e293b; color: white; }}
        .result-box {{ background: linear-gradient(135deg, #eff6ff, #e0f2fe); border-radius: 16px; padding: 1.5rem; border: 1px solid #bfdbfe; margin-top: 1.5rem; }}
        .placa-hint {{ font-size: 0.8rem; color: var(--muted); }}
    </style>
</head>
<body>
    <nav class="navbar navbar-dark">
        <div class="container-fluid">
            <span class="navbar-brand mb-0">
                <i class="bi bi-p-square-fill me-2"></i>Estacionamento Pro
            </span>
        </div>
    </nav>

    <div class="container-fluid py-4 px-4">
        {alerts}
        <ul class="nav nav-pills gap-2 mb-4 flex-wrap">
            <li class="nav-item"><a class="nav-link {ativa('vagas')}" href="/"><i class="bi bi-grid-3x3-gap me-1"></i> Vagas</a></li>
            <li class="nav-item"><a class="nav-link {ativa('entrada')}" href="/entrada"><i class="bi bi-box-arrow-in-right me-1"></i> Entrada</a></li>
            <li class="nav-item"><a class="nav-link {ativa('saida')}" href="/saida"><i class="bi bi-box-arrow-right me-1"></i> Saída</a></li>
            <li class="nav-item"><a class="nav-link {ativa('buscar')}" href="/buscar"><i class="bi bi-search me-1"></i> Buscar</a></li>
            <li class="nav-item"><a class="nav-link {ativa('historico')}" href="/historico"><i class="bi bi-clock-history me-1"></i> Histórico</a></li>
        </ul>
        {content}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


# ==================== ROTAS ====================

@app.route("/")
def index():
    conn = get_db()
    tickets = conn.execute("""
        SELECT t.vaga, t.placa, t.entrada, v.tipo
        FROM tickets t JOIN veiculos v ON v.placa = t.placa
        WHERE t.finalizado = 0 ORDER BY t.vaga
    """).fetchall()

    ocupadas_dict = {t["vaga"]: t for t in tickets}
    total = total_vagas()
    qtd = len(ocupadas_dict)
    livres = total - qtd
    perc = round((qtd / total * 100), 1) if total else 0

    vagas_html = ""
    for i in range(1, total + 1):
        if i in ocupadas_dict:
            t = ocupadas_dict[i]
            entrada = datetime.strptime(t["entrada"], "%Y-%m-%d %H:%M:%S")
            tempo = datetime.now() - entrada
            h, r = divmod(int(tempo.total_seconds()), 3600)
            m = r // 60
            valor = calcular_valor(t["entrada"], t["placa"])
            vagas_html += f"""
            <div class="col-6 col-sm-4 col-md-3 col-xl-2">
                <div class="vaga ocupada">
                    <div class="num">Vaga {i:02d}</div>
                    <div class="placa">{t['placa']}</div>
                    <div class="info">{t['tipo'].capitalize()} · {h:02d}h{m:02d}m</div>
                    <div class="info fw-bold">R$ {valor:.2f}</div>
                </div>
            </div>"""
        else:
            vagas_html += f"""
            <div class="col-6 col-sm-4 col-md-3 col-xl-2">
                <div class="vaga livre">
                    <div class="num">Vaga {i:02d}</div>
                    <div class="livre-text">LIVRE</div>
                </div>
            </div>"""

    hoje = datetime.now().strftime("%Y-%m-%d")
    receita = conn.execute("SELECT COALESCE(SUM(valor_pago),0) as t FROM tickets WHERE finalizado=1 AND date(saida)=?", (hoje,)).fetchone()["t"]
    saidas = conn.execute("SELECT COUNT(*) as t FROM tickets WHERE finalizado=1 AND date(saida)=?", (hoje,)).fetchone()["t"]
    conn.close()

    content = f"""
    <div class="row g-3 mb-4">
        <div class="col-6 col-md-3"><div class="stat-card blue"><div class="label">Total de Vagas</div><div class="value">{total}</div></div></div>
        <div class="col-6 col-md-3"><div class="stat-card red"><div class="label">Ocupadas</div><div class="value">{qtd}</div></div></div>
        <div class="col-6 col-md-3"><div class="stat-card green"><div class="label">Livres</div><div class="value">{livres}</div></div></div>
        <div class="col-6 col-md-3"><div class="stat-card orange"><div class="label">Ocupação</div><div class="value">{perc}%</div></div></div>
    </div>
    <div class="main-card">
        <div class="card-header d-flex justify-content-between align-items-center">
            <span><i class="bi bi-grid-3x3-gap me-2"></i>Mapa de Vagas</span>
            <small class="text-muted">Receita hoje: <strong>R$ {receita:.2f}</strong> · Saídas: {saidas}</small>
        </div>
        <div class="card-body"><div class="row g-2">{vagas_html}</div></div>
    </div>
    """
    return render_page(content, "vagas")


@app.route("/entrada")
def pagina_entrada():
    content = """
    <div class="form-card">
        <div class="card-header bg-success text-white">
            <i class="bi bi-box-arrow-in-right me-2"></i>Entrada de Veículo
        </div>
        <div class="card-body p-4">
            <form method="POST" action="/entrar">
                <div class="mb-3">
                    <label class="form-label fw-semibold">Placa</label>
                    <input type="text" name="placa" class="form-control text-uppercase"
                           placeholder="ABC1234 ou ABC1D23" required maxlength="7">
                    <div class="placa-hint mt-1">
                        Carro/Caminhão: <strong>ABC1234</strong> ou <strong>ABC1D23</strong><br>
                        Moto: também aceita formatos curtos (ex: <strong>DSAD</strong>, <strong>ABC123</strong>)
                    </div>
                </div>
                <div class="mb-3">
                    <label class="form-label fw-semibold">Tipo de Veículo</label>
                    <select name="tipo" class="form-select" required>
                        <option value="">Selecione...</option>
                        <option value="carro">🚗 Carro — R$ 8,00/h</option>
                        <option value="moto">🏍️ Moto — R$ 4,00/h</option>
                        <option value="caminhao">🚚 Caminhão — R$ 15,00/h</option>
                    </select>
                </div>
                <div class="mb-3">
                    <label class="form-label fw-semibold">Modelo <span class="text-muted">(opcional)</span></label>
                    <input type="text" name="modelo" class="form-control" placeholder="Ex: Gol, Civic...">
                </div>
                <div class="mb-4">
                    <label class="form-label fw-semibold">Cor <span class="text-muted">(opcional)</span></label>
                    <input type="text" name="cor" class="form-control" placeholder="Ex: Preto, Branco...">
                </div>
                <button type="submit" class="btn btn-modern btn-success-modern w-100">
                    <i class="bi bi-check-lg me-2"></i>Estacionar Veículo
                </button>
            </form>
        </div>
    </div>
    """
    return render_page(content, "entrada")


@app.route("/saida")
def pagina_saida():
    content = """
    <div class="form-card">
        <div class="card-header bg-danger text-white">
            <i class="bi bi-box-arrow-right me-2"></i>Saída de Veículo
        </div>
        <div class="card-body p-4">
            <form method="POST" action="/sair">
                <div class="mb-4">
                    <label class="form-label fw-semibold">Placa do Veículo</label>
                    <input type="text" name="placa" class="form-control text-uppercase"
                           placeholder="ABC1234 ou ABC1D23" required maxlength="7">
                </div>
                <button type="submit" class="btn btn-modern btn-danger-modern w-100">
                    <i class="bi bi-cash-coin me-2"></i>Registrar Saída e Cobrar
                </button>
            </form>
        </div>
    </div>
    """
    return render_page(content, "saida")


@app.route("/buscar", methods=["GET", "POST"])
def pagina_buscar():
    resultado = ""
    if request.method == "POST":
        placa = request.form.get("placa", "").strip().upper()

        if not validar_placa(placa) and not validar_placa(placa, "moto"):
            flash("Placa inválida! Verifique o formato.", "danger")
        else:
            ticket = ticket_ativo(placa)
            if not ticket:
                flash(f"Veículo {placa} não está estacionado.", "warning")
            else:
                valor = calcular_valor(ticket["entrada"], placa)
                entrada = datetime.strptime(ticket["entrada"], "%Y-%m-%d %H:%M:%S")
                tempo = datetime.now() - entrada
                h, r = divmod(int(tempo.total_seconds()), 3600)
                m = r // 60
                conn = get_db()
                v = conn.execute("SELECT * FROM veiculos WHERE placa = ?", (placa,)).fetchone()
                conn.close()
                resultado = f"""
                <div class="result-box">
                    <h5 class="mb-3"><i class="bi bi-car-front me-2"></i>{placa}</h5>
                    <div class="row">
                        <div class="col-6 mb-2"><span class="text-muted">Tipo</span><br><strong>{v['tipo'].capitalize()}</strong></div>
                        <div class="col-6 mb-2"><span class="text-muted">Vaga</span><br><strong>{ticket['vaga']:02d}</strong></div>
                        <div class="col-6 mb-2"><span class="text-muted">Modelo</span><br><strong>{v['modelo'] or '-'}</strong></div>
                        <div class="col-6 mb-2"><span class="text-muted">Cor</span><br><strong>{v['cor'] or '-'}</strong></div>
                        <div class="col-6 mb-2"><span class="text-muted">Entrada</span><br><strong>{ticket['entrada']}</strong></div>
                        <div class="col-6 mb-2"><span class="text-muted">Tempo</span><br><strong>{h}h {m}min</strong></div>
                    </div>
                    <hr>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="text-muted">Valor atual</span>
                        <span class="fs-3 fw-bold text-success">R$ {valor:.2f}</span>
                    </div>
                </div>
                """

    content = f"""
    <div class="form-card">
        <div class="card-header" style="background:linear-gradient(135deg,#06b6d4,#0891b2);color:white;">
            <i class="bi bi-search me-2"></i>Buscar Veículo
        </div>
        <div class="card-body p-4">
            <form method="POST" action="/buscar">
                <div class="mb-3">
                    <label class="form-label fw-semibold">Placa</label>
                    <input type="text" name="placa" class="form-control text-uppercase"
                           placeholder="Digite a placa" required maxlength="7">
                </div>
                <button type="submit" class="btn btn-modern btn-info-modern w-100">
                    <i class="bi bi-search me-2"></i>Buscar
                </button>
            </form>
            {resultado}
        </div>
    </div>
    """
    return render_page(content, "buscar")


@app.route("/historico")
def historico():
    conn = get_db()
    rows = conn.execute("""
        SELECT t.placa, t.vaga, t.entrada, t.saida, t.valor_pago, v.tipo
        FROM tickets t JOIN veiculos v ON v.placa = t.placa
        WHERE t.finalizado = 1 ORDER BY t.saida DESC LIMIT 50
    """).fetchall()
    conn.close()

    linhas = ""
    if rows:
        for h in rows:
            linhas += f"""
            <tr>
                <td><strong>{h['placa']}</strong></td>
                <td>{h['tipo'].capitalize()}</td>
                <td>{h['vaga']:02d}</td>
                <td>{h['entrada']}</td>
                <td>{h['saida']}</td>
                <td class="fw-bold text-success">R$ {h['valor_pago']:.2f}</td>
            </tr>"""
    else:
        linhas = '<tr><td colspan="6" class="text-center text-muted py-5">Nenhum registro encontrado</td></tr>'

    content = f"""
    <div class="main-card">
        <div class="card-header"><i class="bi bi-clock-history me-2"></i>Histórico de Saídas</div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th class="ps-4">Placa</th>
                            <th>Tipo</th>
                            <th>Vaga</th>
                            <th>Entrada</th>
                            <th>Saída</th>
                            <th>Valor</th>
                        </tr>
                    </thead>
                    <tbody>{linhas}</tbody>
                </table>
            </div>
        </div>
    </div>
    """
    return render_page(content, "historico")


# ==================== AÇÕES ====================

@app.route("/entrar", methods=["POST"])
def entrar():
    placa = request.form.get("placa", "").strip().upper()
    tipo = request.form.get("tipo", "").strip()
    modelo = request.form.get("modelo", "").strip()
    cor = request.form.get("cor", "").strip()

    if not validar_placa(placa, tipo):
        flash("Placa inválida! Use o formato correto para o tipo de veículo.", "danger")
        return redirect(url_for("pagina_entrada"))

    if not tipo:
        flash("Selecione o tipo do veículo.", "danger")
        return redirect(url_for("pagina_entrada"))

    try:
        tipo_enum = TipoVeiculo(tipo)
    except ValueError:
        flash("Tipo de veículo inválido.", "danger")
        return redirect(url_for("pagina_entrada"))

    if ticket_ativo(placa):
        flash(f"O veículo {placa} já está estacionado.", "warning")
        return redirect(url_for("pagina_entrada"))

    vaga = encontrar_vaga_livre()
    if vaga is None:
        flash("Estacionamento lotado!", "danger")
        return redirect(url_for("pagina_entrada"))

    conn = get_db()
    conn.execute("""
        INSERT INTO veiculos (placa, tipo, modelo, cor) VALUES (?, ?, ?, ?)
        ON CONFLICT(placa) DO UPDATE SET tipo=excluded.tipo, modelo=excluded.modelo, cor=excluded.cor
    """, (placa, tipo_enum.value, modelo, cor))
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO tickets (placa, vaga, entrada, finalizado) VALUES (?, ?, ?, 0)",
                 (placa, vaga, agora))
    conn.commit()
    conn.close()

    flash(f"Veículo {placa} estacionado na vaga {vaga:02d}!", "success")
    return redirect(url_for("index"))


@app.route("/sair", methods=["POST"])
def sair():
    placa = request.form.get("placa", "").strip().upper()

    if not validar_placa(placa) and not validar_placa(placa, "moto"):
        flash("Placa inválida! Verifique o formato.", "danger")
        return redirect(url_for("pagina_saida"))

    ticket = ticket_ativo(placa)
    if not ticket:
        flash(f"Veículo {placa} não encontrado.", "warning")
        return redirect(url_for("pagina_saida"))

    valor = calcular_valor(ticket["entrada"], placa)
    saida = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("UPDATE tickets SET saida=?, valor_pago=?, finalizado=1 WHERE id=?",
                 (saida, valor, ticket["id"]))
    conn.commit()
    conn.close()

    flash(f"Saída de {placa} registrada. Valor cobrado: R$ {valor:.2f}", "success")
    return redirect(url_for("index"))


# ==================== INÍCIO ====================

if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("  Sistema de Estacionamento Pro")
    print("  Acesse: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)