from typing import List
import tempfile
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from importlib.metadata import version

# Imports jasapp
from jasapp.linter import Linter
from jasapp.parser.dockerfile import DockerfileParser
from jasapp.parser.kubernetes import KubernetesParser
from jasapp.rules import all_rules
from jasapp.scorer import Scorer
from jasapp.gemini_integration import generate_corrected_code

from google.cloud import secretmanager

from typing import Union

app = FastAPI()

# Configure static file serving
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

JASAPP_VERSION = version('jasapp')

# Règles Dockerfile (filtrées sur rule_type="dockerfile")
dockerfile_rules = [
    rule() for rule_name, rule in all_rules.items()
    if rule.rule_type == "dockerfile"
]

# Règles K8s (filtrées sur rule_type="k8s") - À adapter si besoin
k8s_rules = [
    rule() for rule_name, rule in all_rules.items()
    if rule.rule_type == "kubernetes"
]

try:
    # Import Secret
    client = secretmanager.SecretManagerServiceClient()

    name = "projects/jasapp/secrets/GEMINI_API_KEY/versions/latest"  # Remplacez "GEMINI_API_KEY" par le nom de votre secret

    # Récupérer le secret.
    response = client.access_secret_version(name=name)
    secret_string = response.payload.data.decode("UTF-8")

    # Définir la variable d'environnement.
    os.environ["GEMINI_API_KEY"] = secret_string

except Exception as e:
    gemini_api_key = os.getenv("GEMINI_API_KEY", "CHANGE_ME")
    print("Error when authentication with GCP", {e})

# ---------------------
# Modèles Pydantic
# ---------------------


class LintingError(BaseModel):
    line: Union[int, str] = Field(..., example=1)
    rule: str = Field(..., example="STX0001")
    message: str = Field(..., example="WORKDIR must use an absolute path")
    severity: str = Field(..., example="error")
    doc_link: str = Field(..., example="https://example.com/docs/STX0001")


class LintingResult(BaseModel):
    errors: List[LintingError]


# Requête Dockerfile
class DockerfileLintingRequest(BaseModel):
    dockerfile_content: str = Field(
        ...,
        example="FROM ubuntu:latest\nRUN apt-get update"
    )


# Requête K8s
class K8sLintingRequest(BaseModel):
    k8s_manifest: str = Field(
        ...,
        example="""apiVersion: v1
kind: Pod
metadata:
  name: mypod
spec:
  containers:
  - name: mycontainer
    image: nginx:latest
"""
    )


# ---------------------
# Routes
# ---------------------

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "jasapp_version": JASAPP_VERSION}
    )


# --- Dockerfile endpoints ---
@app.post("/lint/dockerfile", response_model=LintingResult)
async def lint_dockerfile(request: DockerfileLintingRequest):
    """
    Lints a Dockerfile from a string content.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.Dockerfile') as tmp_dockerfile:
        tmp_dockerfile.write(request.dockerfile_content)
        tmp_dockerfile_path = tmp_dockerfile.name

    try:
        # Analyse du Dockerfile
        parser = DockerfileParser(tmp_dockerfile_path)
        instructions = parser.parse()
        print("Instructions parsed:", instructions)

        # Exécution du linter
        linter = Linter(dockerfile_rules)
        errors = linter.run(instructions)
        print("Errors found by linter:", errors)

        # Formatage des résultats
        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                'line': error.get('line', 'N/A'),
                'rule': error['rule'],
                'message': error['message'],
                'severity': error['severity'],
                'doc_link': error.get('doc_link', '')
            })

        return {"errors": formatted_errors}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing Dockerfile: {e}")
    finally:
        os.unlink(tmp_dockerfile_path)


@app.post("/score", response_model=dict)
async def get_score(request: DockerfileLintingRequest):
    """
    Calculates and returns the quality score of a Dockerfile.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.Dockerfile') as tmp_dockerfile:
        tmp_dockerfile.write(request.dockerfile_content)
        tmp_dockerfile_path = tmp_dockerfile.name

    try:
        parser = DockerfileParser(tmp_dockerfile_path)
        instructions = parser.parse()

        linter = Linter(dockerfile_rules)
        errors = linter.run(instructions)

        # Calcul du score
        scorer = Scorer()
        score = scorer.calculate(errors, len(dockerfile_rules))
        return {"score": score}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating score: {e}")
    finally:
        os.unlink(tmp_dockerfile_path)


# --- K8s endpoints ---
@app.post("/lint/k8s", response_model=LintingResult)
async def lint_k8s(request: K8sLintingRequest):
    try:
        parser = KubernetesParser(file_path="")
        resources = parser.parse_from_string(request.k8s_manifest)
        print("Resources parsed:", resources)

        linter = Linter(k8s_rules)
        errors = linter.run(resources)
        print("Errors found by linter:", errors)

        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                'line': error.get('line', 'N/A'),
                'rule': error['rule'],
                'message': error['message'],
                'severity': error['severity'],
                'doc_link': error.get('doc_link', '')
            })

        return {"errors": formatted_errors}

    except Exception as e:
        print("Exception occurred:", e)  # Log l'exception
        # 400 ou 500 selon votre logique
        raise HTTPException(status_code=500, detail=f"Internal Error: {e}")


@app.post("/score/k8s", response_model=dict)
async def get_score_k8s(request: K8sLintingRequest):
    """
    Calculates and returns the quality score of a Kubernetes manifest.
    """
    parser = KubernetesParser(file_path="")
    try:
        resources = parser.parse_from_string(request.k8s_manifest)

        linter = Linter(k8s_rules)
        errors = linter.run(resources)

        # Calcul du score
        scorer = Scorer()
        score = scorer.calculate(errors, len(k8s_rules))
        return {"score": score}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating K8s score: {e}")


@app.post("/ask/gemini/dockerfile")
async def ask_gemini_dockerfile(request: DockerfileLintingRequest):
    """
    Uses the Gemini API to generate a corrected Dockerfile
    based on the lint errors found.
    """
    # 1) Créer un fichier temporaire avec le contenu Dockerfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.Dockerfile') as tmp_dockerfile:
        tmp_dockerfile.write(request.dockerfile_content)
        tmp_dockerfile_path = tmp_dockerfile.name

    try:
        # 2) Parser le Dockerfile et exécuter le linter
        parser = DockerfileParser(tmp_dockerfile_path)
        instructions = parser.parse()

        linter = Linter(dockerfile_rules)
        errors = linter.run(instructions)

        # On formate les erreurs sous forme de dict
        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                'line': error.get('line', 'N/A'),
                'message': error['message'],
            })

        # 3) Appel à l’API Gemini pour correction
        gemini_api_key = os.getenv("GEMINI_API_KEY", "CHANGE_ME")
        corrected_code = generate_corrected_code(
            file_type="dockerfile",
            file_content=request.dockerfile_content,
            errors=formatted_errors,
            api_key=gemini_api_key,
            detailed=False
        )

        if corrected_code is None:
            raise HTTPException(status_code=500, detail="Too many requests to Gemini API... Wait 1 minute and try again.")

        return {"corrected_code": corrected_code}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini Dockerfile error: {e}")
    finally:
        # Nettoyage du fichier temporaire
        os.unlink(tmp_dockerfile_path)


@app.post("/ask/gemini/k8s")
async def ask_gemini_k8s(request: K8sLintingRequest):
    """
    Uses the Gemini API to generate a corrected K8s manifest
    based on the lint errors found.
    """
    try:
        # 1) Parser le manifest
        parser = KubernetesParser(file_path="")
        resources = parser.parse_from_string(request.k8s_manifest)

        # 2) Linter
        linter = Linter(k8s_rules)
        errors = linter.run(resources)

        # On formate les erreurs
        formatted_errors = []
        for error in errors:
            formatted_errors.append({
                'line': error.get('line', 'N/A'),
                'message': error['message'],
            })

        # 3) Appel à l’API Gemini pour correction
        gemini_api_key = os.getenv("GEMINI_API_KEY", "CHANGE_ME")
        corrected_code = generate_corrected_code(
            file_type="kubernetes",
            file_content=request.k8s_manifest,
            errors=formatted_errors,
            api_key=gemini_api_key,
            detailed=False
        )

        if corrected_code is None:
            raise HTTPException(status_code=500, detail="Too many requests to Gemini API... Wait 1 minute and try again.")

        return {"corrected_code": corrected_code}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini K8s error: {e}")


# -- Démarrage en local --
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
