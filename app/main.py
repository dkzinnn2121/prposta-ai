import os
import re
from typing import List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv
from fpdf import FPDF

from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Configuração do SQLite
DATABASE_URL = "sqlite:///./propostas.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PropostaDB(Base):
    __tablename__ = "propostas"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(String)
    servico = Column(String)
    orcamento = Column(Float)
    detalhes = Column(String)
    proposta_texto = Column(Text)

Base.metadata.create_all(bind=engine)

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class PropostaRequest(BaseModel):
    cliente: str
    servico: str
    orcamento: float
    detalhes: str

class PropostaResponse(BaseModel):
    id: int
    cliente: str
    servico: str
    orcamento: float
    detalhes: str
    proposta_texto: str

    class Config:
        from_attributes = True

# Helper para formatação do PDF
class PDFProposta(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(15, 23, 42)
        self.cell(0, 10, 'PROPOSTA COMERCIAL - PROPOSTA AI', ln=True, align='C')
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Pagina {self.page_no()}', align='C')

def sanitizar_texto(texto: str) -> str:
    """ Remove emojis, caracteres não compatíveis e limpa sintaxe LaTeX/Math """
    # Remove cifrões soltos de expressões como $24/7$ -> 24/7
    texto = re.sub(r'\$([^$]+)\$', r'\1', texto)
    texto = texto.replace('$', '')
    
    # Filtra mantendo apenas caracteres suportados pela codificação latin-1 (remove emojis)
    texto_limpo = []
    for char in texto:
        try:
            char.encode('latin-1')
            texto_limpo.append(char)
        except UnicodeEncodeError:
            continue
    return "".join(texto_limpo)

def processar_markdown_para_pdf(pdf: FPDF, texto: str):
    linhas = texto.split('\n')
    for linha in linhas:
        linha_limpa = sanitizar_texto(linha.strip())
        if not linha_limpa:
            pdf.ln(2)
            continue

        if linha_limpa.startswith('```'):
            continue

        pdf.set_x(pdf.l_margin)

        # Títulos (#)
        if linha_limpa.startswith('#'):
            pdf.ln(2)
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(15, 23, 42)
            titulo = re.sub(r'#+\s*', '', linha_limpa).replace('**', '').replace('`', '')
            pdf.multi_cell(0, 6, titulo.encode('latin-1', 'replace').decode('latin-1'))
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(51, 65, 85)
            pdf.ln(1)
        # Listas (* - +)
        elif linha_limpa.startswith('* ') or linha_limpa.startswith('- ') or linha_limpa.startswith('+ '):
            item = linha_limpa[2:].replace('**', '').replace('`', '')
            texto_formatado = f"- {item}"
            pdf.multi_cell(0, 6, texto_formatado.encode('latin-1', 'replace').decode('latin-1'))
        # Parágrafos comuns
        else:
            texto_formatado = linha_limpa.replace('**', '').replace('`', '')
            pdf.multi_cell(0, 6, texto_formatado.encode('latin-1', 'replace').decode('latin-1'))

# ROTA PRINCIPAL: Abre o site
@app.get("/")
def abrir_site():
    return FileResponse("app/static/index.html")

# ROTA 1: Criar proposta com IA
@app.post("/proposta", response_model=PropostaResponse)
def criar_proposta(dados: PropostaRequest, db: Session = Depends(get_db)):
    if not client:
        raise HTTPException(
            status_code=500, 
            detail="Chave GEMINI_API_KEY não configurada no arquivo .env"
        )
    
    prompt = f"""
    Atue como um diretor jurídico e comercial sênior.
    Elabore uma proposta comercial estritamente formal, executiva e contratual para o cliente '{dados.cliente}'.

    REGRAS RÍGIDAS DE FORMATAÇÃO E TOM:
    - NUNCA utilize emojis, ícones ou qualquer caractere gráfico em nenhuma hipótese.
    - NUNCA utilize cifrões para isolar termos ou horários (exemplo incorreto: $24/7$; correto: 24 horas por dia).
    - Utilize tom formal, corporativo, direto e sóbrio.

    Dados do Projeto:
    - Serviço: {dados.servico}
    - Orçamento estimado: R$ {dados.orcamento:.2f}
    - Detalhes e escopo: {dados.detalhes}

    Estrutura da Proposta:
    1. Apresentação Executiva
    2. Escopo Técnico dos Serviços
    3. Cronograma de Execução
    4. Condições Financeiras e Investimento
    5. Termos de Aceite e Próximos Passos
    """

    try:
        resposta = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )
        texto_gerado = resposta.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao chamar Gemini API: {str(e)}")

    nova_proposta = PropostaDB(
        cliente=dados.cliente,
        servico=dados.servico,
        orcamento=dados.orcamento,
        detalhes=dados.detalhes,
        proposta_texto=texto_gerado
    )
    db.add(nova_proposta)
    db.commit()
    db.refresh(nova_proposta)

    return nova_proposta

# ROTA 2: Listar todas as propostas
@app.get("/propostas", response_model=List[PropostaResponse])
def listar_propostas(db: Session = Depends(get_db)):
    return db.query(PropostaDB).all()

# ROTA 3: Buscar uma proposta por ID
@app.get("/proposta/{proposta_id}", response_model=PropostaResponse)
def obter_proposta(proposta_id: int, db: Session = Depends(get_db)):
    proposta = db.query(PropostaDB).filter(PropostaDB.id == proposta_id).first()
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    return proposta

# ROTA 4: Exportar PDF Formatado
@app.get("/proposta/{proposta_id}/pdf")
def baixar_proposta_pdf(proposta_id: int, db: Session = Depends(get_db)):
    proposta = db.query(PropostaDB).filter(PropostaDB.id == proposta_id).first()
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")

    pdf = PDFProposta()
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, f"Cliente: {proposta.cliente}", ln=True)
    pdf.cell(0, 6, f"Servico: {proposta.servico}", ln=True)
    pdf.cell(0, 6, f"Orcamento: R$ {proposta.orcamento:.2f}", ln=True)
    pdf.ln(4)
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(51, 65, 85)
    processar_markdown_para_pdf(pdf, proposta.proposta_texto)

    pdf_bytes = bytes(pdf.output())

    headers = {
        'Content-Disposition': f'attachment; filename="proposta_{proposta_id}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

# ROTA 5: Deletar uma proposta
@app.delete("/proposta/{proposta_id}")
def deletar_proposta(proposta_id: int, db: Session = Depends(get_db)):
    proposta = db.query(PropostaDB).filter(PropostaDB.id == proposta_id).first()
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    db.delete(proposta)
    db.commit()
    return {"mensagem": f"Proposta {proposta_id} removida com sucesso!"}