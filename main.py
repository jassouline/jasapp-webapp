from typing import List
import tempfile
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

# Importations corrigées depuis le package jasapp installé
from jasapp.linter import Linter
from jasapp.parser.dockerfile import DockerfileParser
from jasapp.rules import all_rules
from jasapp.scorer import Scorer

app = FastAPI()

# Configure static file serving
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# Initialize rules for Dockerfiles
dockerfile_rules = [rule() for rule_name, rule in all_rules.items() if rule.rule_type == "dockerfile"]


class LintingError(BaseModel):
    line: int = Field(..., example=1)
    rule: str = Field(..., example="STX0001")
    message: str = Field(..., example="WORKDIR must use an absolute path")
    severity: str = Field(..., example="error")
    doc_link: str = Field(..., example="https://example.com/docs/STX0001")


class LintingResult(BaseModel):
    errors: List[LintingError]


class LintingRequest(BaseModel):
    dockerfile_content: str = Field(..., example="FROM ubuntu:latest\nRUN apt-get update")


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/lint/dockerfile", response_model=LintingResult)
async def lint_dockerfile(request: LintingRequest):
    """
    Lints a Dockerfile from a string content.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.Dockerfile') as tmp_dockerfile:
        tmp_dockerfile.write(request.dockerfile_content)
        tmp_dockerfile_path = tmp_dockerfile.name

    # Analyse du Dockerfile avec le parser
    parser = DockerfileParser(tmp_dockerfile_path)
    try:
        instructions = parser.parse()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing Dockerfile: {e}")
    finally:
        # Nettoyage du fichier temporaire
        os.unlink(tmp_dockerfile_path)

    # Exécution du linter
    linter = Linter(dockerfile_rules)
    errors = linter.run(instructions)

    # Formatage des résultats pour l'API
    formatted_errors = []
    for error in errors:
        formatted_errors.append({
            'line': error.get('line', 'N/A'),
            'rule': error['rule'],
            'message': error['message'],
            'severity': error['severity'],
            'doc_link': error.get('doc_link', '')  # Inclure le lien de documentation
        })

    return {"errors": formatted_errors}


@app.post("/score", response_model=dict)
async def get_score(request: LintingRequest):
    """
    Calculates and returns the quality score of a Dockerfile.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.Dockerfile') as tmp_dockerfile:
        tmp_dockerfile.write(request.dockerfile_content)
        tmp_dockerfile_path = tmp_dockerfile.name

    try:
        # Analyze the Dockerfile with the parser
        parser = DockerfileParser(tmp_dockerfile_path)
        instructions = parser.parse()

        # Run the linter
        linter = Linter(dockerfile_rules)
        errors = linter.run(instructions)

        # Calculate the score
        scorer = Scorer()
        score = scorer.calculate(errors, len(dockerfile_rules))

        return {"score": score}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating score: {e}")
    finally:
        os.unlink(tmp_dockerfile_path)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
