import requests
import sys


def check_health():
    try:
        response = requests.get("http://localhost:8000")
        response.raise_for_status()  # Lève une exception pour les codes d'erreur 4xx ou 5xx
        print("Health check successful!")
        sys.exit(0)  # Succès
    except requests.exceptions.RequestException as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        sys.exit(1)  # Échec


if __name__ == "__main__":
    check_health()
