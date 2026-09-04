import os
from typing import List
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv

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

@app.get("/")
def inicio():
    return {"mensagem": "Proposta AI esta funcionando com Banco de Dados!"}

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

# ROTA 4: Deletar uma proposta por ID
@app.delete("/proposta/{proposta_id}")
def deletar_proposta(proposta_id: int, db: Session = Depends(get_db)):
    proposta = db.query(PropostaDB).filter(PropostaDB.id == proposta_id).first()
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    db.delete(proposta)
    db.commit()
    return {"mensagem": f"Proposta {proposta_id} removida com sucesso!"}