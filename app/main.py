import os
from typing import List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import Response
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

# Helper para formatação de PDF
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

@app.get("/")
def inicio():
    return {"mensagem": "Proposta AI esta funcionando com Banco de Dados e Exportacao PDF!"}

# ROTA 1: Criar proposta com IA e salvar no Banco
@app.post("/proposta", response_model=PropostaResponse)
def criar_proposta(dados: PropostaRequest, db: Session = Depends(get_db)):
    if not client:
        raise HTTPException(
            status_code=500, 
            detail="Chave GEMINI_API_KEY não configurada no arquivo .env"
        )
    
    prompt = f"""
    Atue como um especialista em vendas e negociações comerciais.
    Crie uma proposta comercial formal, persuasiva e profissional para o cliente '{dados.cliente}'.

    Dados do Projeto:
    - Serviço: {dados.servico}
    - Orçamento estimado: R$ {dados.orcamento:.2f}
    - Detalhes e escopo: {dados.detalhes}

    Estrutura desejada na proposta:
    1. Introdução / Apresentação
    2. Escopo dos Serviços
    3. Cronograma sugerido
    4. Investimento e Condições de Pagamento
    5. Próximos Passos
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

# ROTA 3: Buscar uma proposta específica por ID
@app.get("/proposta/{proposta_id}", response_model=PropostaResponse)
def obter_proposta(proposta_id: int, db: Session = Depends(get_db)):
    proposta = db.query(PropostaDB).filter(PropostaDB.id == proposta_id).first()
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    return proposta

# ROTA 4: Exportar Proposta em arquivo PDF para Download
@app.get("/proposta/{proposta_id}/pdf")
def baixar_proposta_pdf(proposta_id: int, db: Session = Depends(get_db)):
    proposta = db.query(PropostaDB).filter(PropostaDB.id == proposta_id).first()
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")

    pdf = PDFProposta()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 7, f"Cliente: {proposta.cliente}", ln=True)
    pdf.cell(0, 7, f"Servico: {proposta.servico}", ln=True)
    pdf.cell(0, 7, f"Orcamento: R$ {proposta.orcamento:.2f}", ln=True)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', '', 10)
    # Limpa caracteres especiais não suportados no padrão do FPDF
    texto_limpo = proposta.proposta_texto.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, texto_limpo)

    pdf_bytes = bytes(pdf.output())

    headers = {
        'Content-Disposition': f'attachment; filename="proposta_{proposta_id}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

# ROTA 5: Deletar uma proposta por ID
@app.delete("/proposta/{proposta_id}")
def deletar_proposta(proposta_id: int, db: Session = Depends(get_db)):
    proposta = db.query(PropostaDB).filter(PropostaDB.id == proposta_id).first()
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    db.delete(proposta)
    db.commit()
    return {"mensagem": f"Proposta {proposta_id} removida com sucesso!"}