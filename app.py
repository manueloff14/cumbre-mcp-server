import requests
from pydantic import BaseModel, Field
import sys
import uvicorn
from fastapi import FastAPI
import os
from dotenv import load_dotenv
from urllib.parse import quote

# Carga las variables de entorno desde un archivo .env
load_dotenv()

# Importación de la clase FastMCP
from mcp.server.fastmcp import FastMCP

def generar_consultas(consulta_inicial: str) -> list[str]:
    """Genera una lista de consultas a partir de una consulta inicial."""
    consulta_limpia = consulta_inicial.strip()
    if not consulta_limpia:
        return []
    # Crea un conjunto para evitar duplicados y añade la versión "remoto"
    consultas = {consulta_limpia, f"{consulta_limpia} remoto"}
    return list(consultas)

# Configuración de la aplicación MCP
mcp_app = FastMCP(
    name="mcp_tools_cumbre",
    instructions="Un servidor de herramientas MCP para Cumbre.",
    stateless_http=True
)

class BusquedaInput(BaseModel):
    """
    Define la estructura del input para la herramienta.
    El modelo de lenguaje debe unificar la consulta (puesto y ciudad) en este único campo.
    """
    consulta: str = Field(
        ...,
        description="La consulta de búsqueda EXACTA y unificada, incluyendo puesto y/o ciudad. Ejemplos: 'vendedor Cúcuta', 'desarrollador remoto'."
    )


@mcp_app.tool(
    name="buscar_empleos",
    description="Busca ofertas de empleo en Colombia. Devuelve las vacantes encontradas."
)
def buscar_empleos(params: BusquedaInput) -> dict:
    """
    Herramienta que busca empleos a partir de una única consulta.
    
    Args:
        params (BusquedaInput): Un objeto de forma {"consulta": "<consulta>"} que contiene la consulta de búsqueda incluyendo el lugar, ejemplo: "vendedor Cúcuta".
    
    Returns:
        dict: Un diccionario que contiene las vacantes encontradas.
    """
    consulta_inicial = params.consulta
    print(f"--- Petición a Herramienta ---\nConsulta: '{consulta_inicial}'", file=sys.stderr)

    # BUSCAR EMPLEOS
    consultas_a_realizar = generar_consultas(consulta_inicial)
    todas_las_vacantes = {}
    
    for consulta in consultas_a_realizar:
        encoded_consulta = quote(consulta) # Codifica la consulta para la URL
        api_url = f"https://api-search.cumbre.icu/search/{encoded_consulta}?limit=10&page=0"
        print(f"Buscando en: {api_url}", file=sys.stderr)
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status() # Lanza un error si la petición falla
            data = response.json()
            vacancies = data.get("vacancies", [])
            for vacante in vacancies:
                # Usa el ID como clave para evitar duplicados
                todas_las_vacantes[vacante["id"]] = vacante
        except requests.exceptions.RequestException as e:
            print(f"Error menor en API de empleos para '{consulta}': {e}", file=sys.stderr)
            pass
    
    lista_final_vacantes = list(todas_las_vacantes.values())
    print(f"Se encontraron {len(lista_final_vacantes)} vacantes únicas.", file=sys.stderr)

    # DEVOLVER RESULTADOS
    print(f"--- Fin de Petición ---", file=sys.stderr)
    return {
        "consultas_realizadas": consultas_a_realizar,
        "vacantes_encontradas": lista_final_vacantes
    }

@mcp_app.tool(
    name="buscar_google",
    description="Realiza búsquedas en Google usando la API de Serper. Devuelve resultados de búsqueda web."
)
def buscar_google(q: str) -> dict:
    """
    Herramienta que realiza búsquedas en Google usando la API de Serper.

    Args:
        q (str): La consulta de búsqueda para Google, por ejemplo: "noticias de hoy".

    Returns:
        dict: Un diccionario que contiene los resultados de la búsqueda.
    """
    consulta_inicial = q
    print(f"--- Petición a Herramienta ---\nConsulta: '{consulta_inicial}'", file=sys.stderr)

    # BUSCAR EN GOOGLE
    encoded_consulta = quote(consulta_inicial) # Codifica la consulta para la URL
    api_url = f"https://google.serper.dev/search"

    print(f"Buscando en: {api_url}", file=sys.stderr)
    try:
        payload = {
            "q": encoded_consulta
        }
        headers = {
            'X-API-KEY': os.getenv('SERPER_API_KEY', 'da407f1177ea4308fadd385daf98eb7ab68e6bb3'),
            'Content-Type': 'application/json'
        }
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status() # Lanza un error si la petición falla
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error en API de Serper para '{consulta_inicial}': {e}", file=sys.stderr)
        return {
            "error": f"Error en la búsqueda: {e}",
            "resultados_encontrados": []
        }

    # Procesar resultados
    organic_results = data.get("organic", [])
    answer_box = data.get("answerBox", {})
    knowledge_graph = data.get("knowledgeGraph", {})

    # Crear un resumen legible
    resumen = f"Resultados de búsqueda para '{consulta_inicial}':\n\n"

    if answer_box:
        resumen += f"Respuesta destacada: {answer_box.get('answer', 'N/A')}\n\n"

    if knowledge_graph:
        title = knowledge_graph.get('title', '')
        description = knowledge_graph.get('description', '')
        if title or description:
            resumen += f"Información clave: {title} - {description}\n\n"

    if organic_results:
        resumen += "Resultados orgánicos:\n"
        for i, result in enumerate(organic_results[:5], 1):  # Limitar a 5 resultados
            title = result.get('title', 'Sin título')
            link = result.get('link', '')
            snippet = result.get('snippet', '')
            resumen += f"{i}. {title}\n   {snippet}\n   Enlace: {link}\n\n"

    print(f"Se procesaron los resultados de búsqueda.", file=sys.stderr)

    # DEVOLVER RESULTADOS
    print(f"--- Fin de Petición ---", file=sys.stderr)
    return {
        "consulta": consulta_inicial,
        "resumen": resumen
    }

# --- MONTAJE Y EJECUCIÓN DEL SERVIDOR ---
app = FastAPI(
    title="Servidor MCP Tools Cumbre",
    description="Expone herramientas MCP para Cumbre.",
    version="3.0.0",
    lifespan=lambda app: mcp_app.session_manager.run()
)

@app.get("/", summary="Verificación de estado", tags=["Health"])
def read_root():
    """Endpoint para verificar que el servidor está funcionando."""
    return {"status": "Servidor MCP Tools Cumbre está en línea"}

# Monta la aplicación MCP en la ruta /api/jobs
app.mount("/api/jobs", mcp_app.streamable_http_app())

if __name__ == "__main__":
    print("Iniciando Servidor MCP Tools Cumbre...")
    uvicorn.run(app, host="127.0.0.1", port=8001)