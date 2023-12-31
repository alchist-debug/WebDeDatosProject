import os
import re
from flask import Flask, render_template, request
from rdflib import Graph
from rdflib.plugins.parsers.notation3 import N3Parser
from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib.plugins.sparql import prepareQuery

app = Flask(__name__, static_url_path='/static')


rdf_graph = Graph()

def extract_rdf(file_path):
    with open(file_path, 'r') as file:
        rdf_content = file.read()
    return rdf_content

@app.route('/')
def index():
    file_path = os.path.join(app.root_path, 'data.ttl')

    if os.path.exists(file_path):
        rdf_content = extract_rdf(file_path)

        return render_template('index.html', rdf_content=rdf_content)
    else:
        return render_template('index.html', error='El archivo no existe')

def extract_rdf(file):
    global rdf_graph  
    try:
        rdf_graph.parse(file, format='n3')
        rdf_content = rdf_graph.serialize(format='turtle')
        return rdf_content
    except Exception as e:
        return f'Error al procesar el archivo TTL: {str(e)}'

@app.route('/query', methods=['POST'])
def query():
    # Obtener la lista de síntomas seleccionados desde el formulario
    selected_symptoms = request.form.getlist('symptoms')
    total_symptoms = len(selected_symptoms)
    # Construir la consulta SPARQL
    sparql_query = f"""
        SELECT ?disease (COUNT(?symptom) as ?coincidences)
        WHERE {{
            ?disease <http://ex.org/hasSymptom> ?symptom .
            VALUES ?symptom {{ {' '.join(f'<{symptom}>' for symptom in selected_symptoms)} }}
        }}
        GROUP BY ?disease
        ORDER BY DESC(?coincidences)
        LIMIT 10
    """

    query = prepareQuery(sparql_query)
    results = rdf_graph.query(query)
    dbpedia_results = []

    # Printeamos la lista de enfermedades encontradas
    for row in results:
        disease_uri_prev = row[0].n3()
        symptoms_coincidences = row[1].n3()
        number_coincidences = extraer_entero(symptoms_coincidences)
        symptoms = get_symptoms(disease_uri_prev)
        disease_uri = get_disease_name(disease_uri_prev)
        dbpedia_link = generate_dbpedia_url(disease_uri)
        dbpedia_summary = query_dbpedia_abstract(get_disease_name2(disease_uri_prev))
        disease_uri = get_disease_name2(disease_uri_prev)
        dbpedia_results.append((disease_uri, number_coincidences, total_symptoms, dbpedia_link, dbpedia_summary, symptoms))

    return render_template('index.html', dbpedia_results=dbpedia_results, get_disease_name=get_disease_name)

def get_symptoms(disease_uri):
    sparql_query2 = f"""
        SELECT ?symptom
        WHERE {{
            {disease_uri} <http://ex.org/hasSymptom> ?symptom .
        }}
    """

    query2 = prepareQuery(sparql_query2)
    results = rdf_graph.query(query2)
    symptoms = []
    for row in results:
        symptoms_name = get_disease_name(row[0].n3())
        symptoms.append(symptoms_name)
    return symptoms

def generate_dbpedia_url(disease_name):    
    # Construye la URL de dbpedia.org
    dbpedia_url = f"https://dbpedia.org/page/{disease_name}"
    
    return dbpedia_url

def extraer_entero(cadena):
    match = re.search(r'"(-?\d+)"\^\^<http://www.w3.org/2001/XMLSchema#integer>', cadena)
    
    if match:
        entero = int(match.group(1))
        return entero
    else:
        print("No se encontró un entero en el formato esperado.")
        return None


def get_disease_name(disease_uri):
    name = disease_uri.split('/')[-1]

    if name == "Alzheimers_disease>":
        name = "Alzheimer's_disease"

    if name == "Cushings_disease>":
        name = "Cushing's_disease"

    return name.rstrip('>')

def get_disease_name2(disease_uri):
    name = disease_uri.split('/')[-1].replace('_', ' ')

    if name == "Alzheimers disease>":
        name = "Alzheimer's disease"

    if name == "Cushings disease>":
        name = "Cushing's disease"
    
    return name.rstrip('>')

def query_dbpedia_abstract(disease_name):
    # Construir la consulta SPARQL para obtener el resumen de DBpedia
    dbpedia_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX yago: <http://dbpedia.org/class/yago/>

        SELECT ?summary
        WHERE {{
            ?disease rdf:type dbo:Disease ;
                     rdfs:label "{disease_name}"@en ;
                     dbo:abstract ?summary .
            FILTER (LANG(?summary) = 'en')
        }}
    """

    # Configurar SPARQLWrapper para DBpedia
    sparql = SPARQLWrapper("http://dbpedia.org/sparql")
    sparql.setQuery(dbpedia_query)
    sparql.setReturnFormat(JSON)

    results = sparql.query().convert()

    if results["results"]["bindings"]:
        return results["results"]["bindings"][0]["summary"]["value"]
    else:
        return f"No se encontró un resumen para {disease_name} en DBpedia."


if __name__ == '__main__':
    app.run(debug=True)
