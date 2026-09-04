import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv

# Carrega a chave de API salva no .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

app = FastAPI()

class PropostaRequest(BaseModel):
    cliente: str
    servico: str
    orcamento: float
    detalhes: str

@app.get("/")
def inicio():
    return {"mensagem": "Proposta AI esta funcionando!"}

@app.post("/proposta")
def criar_proposta(dados: PropostaRequest):
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
        
        return {
            "status": "Proposta gerada com IA!",
            "cliente": dados.cliente,
            "proposta_texto": resposta.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao chamar Gemini API: {str(e)}")